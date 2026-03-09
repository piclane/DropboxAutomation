import logging
import os
import threading
import uuid
import json
from contextlib import asynccontextmanager
from tempfile import gettempdir
import uvicorn
from dropbox import Dropbox
from dropbox.exceptions import ApiError
from dropbox.files import FileMetadata, WriteMode
from fastapi import FastAPI, HTTPException, Response

import settings
from ai import analyze_with_claude
from settings import PORT
from utils.dbx import init_dropbox, init_dropbox_cursor
from utils.summarizer import summarize_to_html
from utils.rabbitmq_publisher import create_publisher

logger = logging.getLogger(__name__)


class DropboxProcessor:
    def __init__(self):
        self._dbx: Dropbox | None = None
        self._dbx_folder_cursor: str | None = None
        self._fetch_lock = threading.Lock()
        self._active_threads: list[threading.Thread] = []
        self._threads_lock = threading.Lock()

    def startup(self):
        """FastAPI lifespan の起動時に呼ぶ。全リソースを初期化する。"""
        if settings.RABBITMQ_PUBLISH_EXCHANGE:
            logger.info("Verifying RabbitMQ connection")
            with create_publisher(settings.RABBITMQ_PUBLISH_EXCHANGE):
                pass
            logger.info("RabbitMQ connection verified")
        logger.info("Initializing Dropbox client")
        self._dbx = init_dropbox()
        self._dbx_folder_cursor = init_dropbox_cursor(self._dbx)

    def shutdown(self):
        """FastAPI lifespan のシャットダウン時に呼ぶ。スレッド完了後にリソースを解放する。"""
        with self._threads_lock:
            threads = list(self._active_threads)
        for t in threads:
            t.join()
        if self._dbx:
            logger.info("Closing Dropbox client")
            self._dbx.close()

    def on_dropbox_notification(self):
        """Dropbox から変更通知を受けたときに呼ぶ。バックグラウンドで変更処理を開始する。"""
        t = threading.Thread(target=self._thread_worker)
        t.start()

    def _thread_worker(self):
        """スレッドのエントリポイント。スレッドリストへの登録・除去と処理実行を担う。"""
        with self._threads_lock:
            self._active_threads.append(threading.current_thread())
        try:
            self._fetch_and_process_changes()
        finally:
            with self._threads_lock:
                self._active_threads.remove(threading.current_thread())

    def _fetch_and_process_changes(self):
        """Dropbox カーソルで未処理の変更を取得し、対象 PDF ファイルを処理する。
        _fetch_lock でシリアライズし、複数スレッドによる重複処理を防ぐ。"""
        with self._fetch_lock:
            has_more = True
            while has_more:
                result = self._dbx.files_list_folder_continue(self._dbx_folder_cursor)
                for entry in result.entries:
                    if not isinstance(entry, FileMetadata):
                        continue
                    file_entry: FileMetadata = entry
                    if not file_entry.name.startswith(settings.FILE_PREFIX) \
                            or not file_entry.path_lower.endswith('.pdf'):
                        continue
                    self._process_file(file_entry.path_lower)
                self._dbx_folder_cursor = result.cursor
                has_more = result.has_more

    def _process_file(self, dbx_path: str):
        """Dropbox 上の PDF を1件処理する（ダウンロード・Claude 分析・リネーム・HTML アップロード・RabbitMQ publish）。

        :param dbx_path: 処理対象の Dropbox ファイルパス
        :raises ApiError: Dropbox API 呼び出しエラーの場合
        """
        logger.info(f"Processing Dropbox PDF file: {dbx_path}")

        # 一時ファイル
        pdf_local_path = os.path.join(gettempdir(), f"{uuid.uuid4()}.pdf")
        html_local_path = os.path.join(gettempdir(), f"{uuid.uuid4()}.html")

        try:
            # Dropboxからファイルをダウンロード
            try:
                with open(pdf_local_path, 'wb') as f:
                    metadata, res = self._dbx.files_download(dbx_path)
                    f.write(res.content)
                logger.info(f"Downloaded file to: {pdf_local_path}")
            except ApiError as e:
                logger.error(f"Error downloading file: {e}")
                raise

            # Claudeでファイルを直接分析
            analysis = analyze_with_claude(pdf_local_path)
            logger.info(f"Analysis result: date={analysis['date']}, title='{analysis['title']}'")

            # 新しいファイル名の生成
            base_name = f"{analysis['date']} {analysis['title']}"
            new_pdf_name = f"{base_name}.pdf"
            new_html_name = f"{base_name}.html"
            directory = os.path.dirname(dbx_path)
            new_pdf_dbx_path = os.path.join(directory, new_pdf_name).replace("\\", "/")
            new_html_dbx_path = os.path.join(directory, new_html_name).replace("\\", "/")

            # 概要を html に保存
            summarize_to_html(analysis, html_local_path)

            try:
                # PDF ファイル名を変更
                result = self._dbx.files_move_v2(
                    from_path=dbx_path,
                    to_path=new_pdf_dbx_path,
                    autorename=True
                )
                actual_new_pdf_path = result.metadata.path_display
                logger.info(f"Renamed PDF to: {actual_new_pdf_path}")

                # HTML をアップロード
                with open(html_local_path, 'rb') as f:
                    self._dbx.files_upload(
                        f=f.read(),
                        path=new_html_dbx_path,
                        mode=WriteMode.overwrite,
                        mute=True
                    )
                logger.info(f"Uploaded HTML to: {new_html_dbx_path}")

                # RabbitMQ に解析結果を publish
                try:
                    with create_publisher(settings.RABBITMQ_PUBLISH_EXCHANGE) as publisher:
                        publisher.publish(
                            body=json.dumps(analysis, ensure_ascii=False).encode('utf-8'),
                            content_type="application/json"
                        )
                    logger.info("Published analysis to RabbitMQ")
                except Exception as e:
                    logger.error(f"Error publishing to RabbitMQ: {e}")

            except ApiError as e:
                logger.error(f"Error renaming file: {e}")
                raise e

            logger.info(f"Successfully processed file: {dbx_path}")
        except Exception as e:
            logger.error(f"Error processing file {dbx_path}: {e}")
        finally:
            # 一時ファイルの削除
            try:
                if os.path.exists(pdf_local_path):
                    os.remove(pdf_local_path)
                if os.path.exists(html_local_path):
                    os.remove(html_local_path)
            except Exception as e:
                logger.warning(f"Error cleaning up temp files: {e}")


processor = DropboxProcessor()


@asynccontextmanager
async def lifespan(app: FastAPI):
    processor.startup()
    yield
    processor.shutdown()


class EndpointFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        # ヘルスチェックエンドポイントのアクセスログを除外
        return record.args and len(record.args) >= 3 and record.args[2] != "/health"


app = FastAPI(lifespan=lifespan)


def start_server():
    """
    Uvicorn サーバーを起動し FastAPI アプリケーションを実行
    """
    logger.info(f"Starting application on port {PORT}")
    # uvicorn のアクセスログからヘルスチェックを除外するフィルタを追加
    logging.getLogger("uvicorn.access").addFilter(EndpointFilter())
    uvicorn.run(app, host='0.0.0.0', port=int(PORT))


@app.get('/health')
async def health_check():
    """
    ヘルスチェックエンドポイント
    """
    return {"success": True}


@app.get('/webhook')
async def verify_webhook(challenge: str | None = None):
    """
    Dropbox webhook 検証エンドポイント

    :param challenge: Dropbox からの検証チャレンジ文字列
    :return: チャレンジレスポンス
    :raises HTTPException: challenge パラメータが存在しないの場合
    """
    if challenge:
        logger.info(f"Received webhook verification challenge")
        return Response(
            content=challenge,
            media_type="text/plain",
            headers={"X-Content-Type-Options": "nosniff"}
        )
    raise HTTPException(status_code=400, detail="No challenge provided")


@app.post('/webhook')
async def handle_webhook():
    """
    Dropbox からの更新通知を処理するエンドポイント

    :return: 処理状態を示す辞書オブジェクト
    """
    processor.on_dropbox_notification()
    return {"success": True}
