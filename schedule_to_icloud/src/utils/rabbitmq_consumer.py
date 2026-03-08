import logging
import ssl
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any
from urllib.parse import unquote, urlparse

import pika

logger: logging.Logger = logging.getLogger(__name__)

class AbstractConsumer(ABC):
    """
    RabbitMQ からメッセージを受信するための抽象基底クラス。
    """

    @abstractmethod
    def consume(
        self,
        callback: Callable[[pika.channel.Channel, pika.spec.Basic.Deliver, pika.spec.BasicProperties, bytes], None]
    ) -> None:
        """
        メッセージの受信を開始する。

        Args:
            callback: メッセージ受信時に呼び出されるコールバック関数。
                シグネチャ: callback(ch, method, properties, body)
        """
        pass

    @abstractmethod
    def close(self) -> None:
        """
        接続を閉じる。
        """
        pass

    def __enter__(self) -> "AbstractConsumer":
        """
        コンテキストマネージャの開始。

        Returns:
            AbstractConsumer: 自身を返す。
        """
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """
        コンテキストマネージャの終了時に接続を閉じる。

        Args:
            exc_type: 例外型
            exc_val: 例外値
            exc_tb: トレースバック
        """
        self.close()

class RabbitMQConsumer(AbstractConsumer):
    """
    RabbitMQ からメッセージを受信するための具象クラス。
    """

    def __init__(self, uri: str) -> None:
        """
        RabbitMQ ブローカーへ接続し、コンシューマーを初期化する。

        Args:
            uri: 接続先を表す URI。
                書式: amqp(s)://ユーザー名:パスワード@ホスト:ポート/vhost/exchange名
                例  : amqp://alice:s3cr3t@rabbitmq.example.com:5672/myapp/order.events

        Raises:
            ValueError: URI のスキームが 'amqp' / 'amqps' 以外の場合、またはパスに
                vhost と exchange 名が含まれていない場合。
            pika.exceptions.AMQPConnectionError: ブローカーへの接続に失敗した場合。
        """
        self._uri: str = uri
        self._exchange, self._params = self._parse_uri(uri)
        self._connection: pika.BlockingConnection | None = None
        self._channel: pika.adapters.blocking_connection.BlockingChannel | None = None
        self._queue_name: str | None = None
        self._connect()

    def _connect(self) -> None:
        """
        RabbitMQ ブローカーに接続し、チャンネルとキューをセットアップする。
        """
        self._connection = pika.BlockingConnection(self._params)
        self._channel = self._connection.channel()

        # Exchange の宣言（念のため）
        self._channel.exchange_declare(exchange=self._exchange, exchange_type='fanout', durable=True)

        # 一時的なキューの作成
        result = self._channel.queue_declare(queue='', exclusive=True)
        self._queue_name = result.method.queue

        # キューを Exchange にバインド
        self._channel.queue_bind(exchange=self._exchange, queue=self._queue_name)
        logger.info(f"Connected to RabbitMQ and bound to queue: {self._queue_name}")

    def consume(
        self,
        callback: Callable[[pika.channel.Channel, pika.spec.Basic.Deliver, pika.spec.BasicProperties, bytes], None]
    ) -> None:
        """
        メッセージの受信を開始する。このメソッドはブロックする。
        接続が切断された場合は、自動的に再接続を試みる。

        Args:
            callback: メッセージ受信時に呼び出されるコールバック関数。
                シグネチャ: callback(ch, method, properties, body)
        """
        error_count: int = 0
        while True:
            try:
                if not self._connection or self._connection.is_closed:
                    self._connect()

                logger.info(f"Waiting for messages from exchange: {self._exchange}")
                self._channel.basic_consume(
                    queue=self._queue_name,
                    on_message_callback=callback,
                    auto_ack=False
                )
                self._channel.start_consuming()
                # 正常に終了（あるいはメッセージ処理が再開）した場合はカウントをリセット
                error_count = 0
            except (pika.exceptions.AMQPConnectionError, pika.exceptions.AMQPChannelError) as e:
                logger.warning(f"Connection lost, retrying in 5 seconds... Error: {e}")
                time.sleep(5)
            except Exception as e:
                error_count += 1
                logger.error(f"Unexpected error in consume (Attempt {error_count}/10): {e}")
                if error_count >= 10:
                    logger.critical("Too many unexpected errors, raising exception.")
                    raise
                # 予期せぬエラーでもとりあえず再試行を試みるが、少し待機する
                time.sleep(5)

    def close(self) -> None:
        """
        接続を閉じる。
        """
        if hasattr(self, "_connection") and self._connection and self._connection.is_open:
            self._connection.close()

    @staticmethod
    def _parse_uri(uri: str) -> tuple[str, pika.ConnectionParameters]:
        """
        URI をパースして exchange 名と接続パラメータを返す。
        src/utils/rabbitmq_publisher.py の実装を踏襲。

        Args:
            uri: パース対象の URI。

        Returns:
            tuple[str, pika.ConnectionParameters]: exchange 名と接続パラメータのタプル。

        Raises:
            ValueError: URI のスキームが不正な場合、または exchange 名が含まれない場合。
        """
        parsed = urlparse(uri)

        scheme = parsed.scheme.lower()
        if scheme not in ("amqp", "amqps"):
            raise ValueError(f"Unsupported scheme: {scheme!r}  (expected 'amqp' or 'amqps')")

        user     = unquote(parsed.username or "guest")
        password = unquote(parsed.password or "guest")
        host     = parsed.hostname or "localhost"
        port     = parsed.port or (5671 if scheme == "amqps" else 5672)

        path_parts = parsed.path.split("/")
        if len(path_parts) < 3:
            raise ValueError(
                "URI path must be /{vhost}/{exchange}  "
                f"(got {parsed.path!r})"
            )

        vhost    = unquote(path_parts[1]) or "/"
        exchange = unquote(path_parts[2])

        if not exchange:
            raise ValueError("Exchange name must not be empty.")

        credentials = pika.PlainCredentials(user, password)

        if scheme == "amqps":
            ssl_context = ssl.create_default_context()
            ssl_options = pika.SSLOptions(ssl_context, host)
        else:
            ssl_options = None

        params = pika.ConnectionParameters(
            host=host,
            port=port,
            virtual_host=vhost,
            credentials=credentials,
            ssl_options=ssl_options,
        )

        return exchange, params
