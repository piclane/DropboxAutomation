"""
RabbitMQ Exchange Publisher

URI フォーマット:
  amqp(s)://user:password@host:port/vhost/exchange

使用例:
  amqp://alice:s3cr3t@rabbitmq.example.com:5672/myapp/order.events
"""

import logging
import pika
import ssl
from abc import ABC, abstractmethod
from urllib.parse import urlparse, unquote

logger = logging.getLogger(__name__)


# ======================================================================
# 共通インターフェイス
# ======================================================================

class AbstractPublisher(ABC):
    """
    パブリッシャーの共通インターフェイスを定義する抽象基底クラス。

    ``RabbitMQPublisher`` および ``NullPublisher`` はこのクラスを継承し、
    すべての抽象メソッドを実装する。
    呼び出し側はこの型でパブリッシャーを受け取ることで、
    具体的な実装を意識せずに利用できる。
    """

    @abstractmethod
    def publish(
            self,
            body: bytes,
            routing_key: str = "",
            content_type: str = "application/octet-stream",
            delivery_mode: int = 2,
    ) -> None:
        """
        バイナリデータをメッセージとして送信する。

        Parameters
        ----------
        body : bytes
            送信するバイナリデータ。
        routing_key : str, optional
            ルーティングキー。デフォルトは ``""``。
        content_type : str, optional
            Content-Type ヘッダ。デフォルトは ``"application/octet-stream"``。
        delivery_mode : int, optional
            配信モード。``1`` = 非永続、``2`` = 永続。デフォルトは ``2``。

        Returns
        -------
        None
        """

    @abstractmethod
    def close(self) -> None:
        """
        パブリッシャーが保持するリソースを解放する。

        Returns
        -------
        None
        """

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


# ======================================================================
# 具体実装
# ======================================================================

class RabbitMQPublisher(AbstractPublisher):
    def __init__(self, uri: str):
        """
        RabbitMQ ブローカーへ接続し、パブリッシャーを初期化する。

        Parameters
        ----------
        uri : str
            接続先を表す URI。
            書式: amqp(s)://ユーザー名:パスワード@ホスト:ポート/vhost/exchange名
            例  : amqp://alice:s3cr3t@rabbitmq.example.com:5672/myapp/order.events

        Raises
        ------
        ValueError
            URI のスキームが 'amqp' / 'amqps' 以外の場合、またはパスに
            vhost と exchange 名が含まれていない場合。
        pika.exceptions.AMQPConnectionError
            ブローカーへの接続に失敗した場合。
        """
        self._uri = uri
        self._exchange, params = self._parse_uri(uri)
        self._connection = pika.BlockingConnection(params)
        self._channel = self._connection.channel()

    # ------------------------------------------------------------------
    # AbstractPublisher の実装
    # ------------------------------------------------------------------

    def publish(
            self,
            body: bytes,
            routing_key: str = "",
            content_type: str = "application/octet-stream",
            delivery_mode: int = 2,
    ) -> None:
        """
        任意のバイナリデータを exchange へ送信する。

        Parameters
        ----------
        body : bytes
            送信するバイナリデータ。
        routing_key : str, optional
            ルーティングキー。topic / direct exchange で宛先の振り分けに使用する。
            fanout exchange の場合は空文字列のままでよい。デフォルトは ``""``。
        content_type : str, optional
            メッセージの Content-Type ヘッダ。デフォルトは ``"application/octet-stream"``。
        delivery_mode : int, optional
            配信モード。``1`` = 非永続（メモリのみ）、``2`` = 永続（ディスク書き込み）。
            デフォルトは ``2``。

        Returns
        -------
        None

        Raises
        ------
        pika.exceptions.AMQPChannelError
            チャネルが閉じられているなど、送信に失敗した場合。
        """
        properties = pika.BasicProperties(
            content_type=content_type,
            delivery_mode=delivery_mode,
        )
        self._channel.basic_publish(
            exchange=self._exchange,
            routing_key=routing_key,
            body=body,
            properties=properties,
        )
        logger.debug(
            "published: exchange=%r  routing_key=%r  %d bytes",
            self._exchange, routing_key, len(body),
        )

    def close(self) -> None:
        """
        ブローカーとの接続を閉じる。

        既に接続が閉じられている場合は何もしない。

        Returns
        -------
        None
        """
        if self._connection and self._connection.is_open:
            self._connection.close()

    # ------------------------------------------------------------------
    # 内部ヘルパー
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_uri(uri: str):
        """
        URI をパースして exchange 名と接続パラメータを返す。

        Parameters
        ----------
        uri : str
            amqp(s)://ユーザー名:パスワード@ホスト:ポート/vhost/exchange名 形式の URI。

        Returns
        -------
        tuple[str, pika.ConnectionParameters]
            - [0] exchange 名 (str)
            - [1] pika への接続パラメータ (pika.ConnectionParameters)

        Raises
        ------
        ValueError
            スキームが 'amqp' / 'amqps' 以外の場合、パスセグメントが不足している場合、
            または exchange 名が空文字列の場合。
        """
        parsed = urlparse(uri)

        scheme = parsed.scheme.lower()
        if scheme not in ("amqp", "amqps"):
            raise ValueError(f"Unsupported scheme: {scheme!r}  (expected 'amqp' or 'amqps')")

        user     = unquote(parsed.username or "guest")
        password = unquote(parsed.password or "guest")
        host     = parsed.hostname or "localhost"
        port     = parsed.port or (5671 if scheme == "amqps" else 5672)

        # path = /vhost/exchange  →  parts[1]=vhost, parts[2]=exchange
        path_parts = parsed.path.split("/")          # ['', 'vhost', 'exchange']
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


class NullPublisher(AbstractPublisher):
    """
    何も送信しないヌルオブジェクト実装のパブリッシャー。

    ``RabbitMQPublisher`` と同一のインターフェイスを持つが、
    すべての操作は無害に無視される。URI が未指定の場合など、
    実際には publish しない場合でも呼び出し側のコードを変えずに
    差し替えられることを目的とする（Null Object パターン）。
    """

    def __init__(self) -> None:
        """
        NullPublisher を初期化する。

        引数は不要。接続・チャネルの確立も行わない。
        """

    def publish(
            self,
            body: bytes,
            routing_key: str = "",
            content_type: str = "application/octet-stream",
            delivery_mode: int = 2,
    ) -> None:
        """
        何もしない publish の空実装。

        ``RabbitMQPublisher.publish`` と同じシグネチャを持つが、
        メッセージの送信は行わず、即座に返る。

        Parameters
        ----------
        body : bytes
            送信するバイナリデータ（無視される）。
        routing_key : str, optional
            ルーティングキー（無視される）。デフォルトは ``""``。
        content_type : str, optional
            Content-Type ヘッダ（無視される）。
            デフォルトは ``"application/octet-stream"``。
        delivery_mode : int, optional
            配信モード（無視される）。デフォルトは ``2``。

        Returns
        -------
        None
        """

    def close(self) -> None:
        """
        何もしない close の空実装。

        ``RabbitMQPublisher.close`` と同じシグネチャを持つが、
        閉じるべき接続が存在しないため、即座に返る。

        Returns
        -------
        None
        """


# ======================================================================
# ファクトリ関数
# ======================================================================

def create_publisher(uri: str | None) -> AbstractPublisher:
    """
    URI の有無に応じて適切なパブリッシャーを生成して返す。

    ``uri`` が指定されている場合は ``RabbitMQPublisher``、
    ``None`` または空文字列の場合は ``NullPublisher`` を返す。
    呼び出し側は ``AbstractPublisher`` 型として受け取ることで、
    具体的な実装を意識せずに同じインターフェイスで利用できる。

    Parameters
    ----------
    uri : str | None
        接続先の URI。``None`` または空文字列を渡すと
        ``NullPublisher`` が返される。

    Returns
    -------
    AbstractPublisher
        URI が有効な場合は ``RabbitMQPublisher``、
        それ以外は ``NullPublisher``。

    Examples
    --------
    >>> pub = create_publisher("amqp://alice:s3cr3t@localhost:5672/myapp/logs")
    >>> pub.publish(b"hello")          # RabbitMQ へ送信される

    >>> pub = create_publisher(None)
    >>> pub.publish(b"hello")          # 何も起きない
    """
    if uri:
        return RabbitMQPublisher(uri)
    return NullPublisher()


# ======================================================================
# CLI
# usage: python rabbitmq_publisher.py amqp://alice:s3cr3t@localhost:5672/myapp/logs
# ======================================================================
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <amqp-uri> [routing_key]")
        sys.exit(1)

    target_uri  = sys.argv[1]
    routing_key = sys.argv[2] if len(sys.argv) > 2 else ""

    # stdin からバイナリを読み込んで送信
    payload = sys.stdin.buffer.read()

    with RabbitMQPublisher(target_uri) as pub:
        pub.publish(payload, routing_key=routing_key)
