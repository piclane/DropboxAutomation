import logging
import os
import threading
import uuid
from tempfile import gettempdir
from typing import Optional

import uvicorn
from dropbox.exceptions import ApiError
from dropbox.files import FileMetadata, WriteMode
from fastapi import FastAPI, HTTPException, Response

import settings
from ai import analyze_with_claude
from settings import PORT
from utils.dbx import init_dropbox, init_dropbox_cursor
from utils.pdf import annotate_pdf

logger = logging.getLogger(__name__)

app = FastAPI()

dbx = init_dropbox()
dbx_folder_cursor = init_dropbox_cursor(dbx)

def start_server():
    """
    Uvicorn サーバーを起動し FastAPI アプリケーションを実行
    """
    logger.info(f"Starting application on port {PORT}")
    uvicorn.run(app, host='0.0.0.0', port=int(PORT))

@app.get('/health')
async def health_check():
    """
    ヘルスチェックエンドポイント
    """
    return {"success": True}


@app.get('/webhook')
async def verify_webhook(challenge: Optional[str] = None):
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
    threading.Thread(target=handle_dropbox_notification).start()
    return {"success": True}


def handle_dropbox_notification():
    """
    Dropbox フォルダの変更通知に対する処理

    指定フォルダ内の PDF ファイルに対して以下の処理を実行:
    - BRWDCE で始まる PDF ファイルの検出
    - Claude による分析
    - 分析結果に基づくファイル名変更
    - PDF への注釈追加
    """
    global dbx_folder_cursor

    has_more = True
    while has_more:
        result = dbx.files_list_folder_continue(dbx_folder_cursor)

        for entry in result.entries:
            if not isinstance(entry, FileMetadata):
                continue

            file_entry: FileMetadata = entry
            if not file_entry.name.startswith(settings.FILE_PREFIX) or not file_entry.path_lower.endswith('.pdf'):
                continue

            process_dropbox_file(file_entry.path_lower)

        dbx_folder_cursor = result.cursor
        has_more = result.has_more


def process_dropbox_file(dbx_path: str):
    """
    Dropbox 上の PDF ファイル処理

    :param dbx_path: 処理対象の Dropbox ファイルパス
    :raises ApiError: Dropbox API 呼び出しエラーの場合
    """
    logger.info(f"Processing Dropbox PDF file: {dbx_path}")

    # 一時ファイル
    old_local_path = os.path.join(gettempdir(), f"{uuid.uuid4()}.pdf")
    new_local_path = os.path.join(gettempdir(), f"{uuid.uuid4()}.pdf")

    try:
        # Dropboxからファイルをダウンロード
        try:
            with open(old_local_path, 'wb') as f:
                metadata, res = dbx.files_download(dbx_path)
                f.write(res.content)
            logger.info(f"Downloaded file to: {old_local_path}")
        except ApiError as e:
            logger.error(f"Error downloading file: {e}")
            raise

        # Claudeでファイルを直接分析
        analysis = analyze_with_claude(old_local_path)
        logger.info(f"Analysis result: date={analysis['date']}, title='{analysis['title']}'")

        # 新しいファイル名の生成
        new_file_name = f"{analysis['date']} {analysis['title']}.pdf"
        directory = os.path.dirname(dbx_path)
        new_dbx_path = os.path.join(directory, new_file_name).replace("\\", "/")

        # 要約を PDF に追加
        annotate_pdf(old_local_path, new_local_path, analysis['summary'])

        try:
            # ファイル名を変更
            result = dbx.files_move_v2(
                from_path=dbx_path,
                to_path=new_dbx_path,
                autorename=True
            )

            # 上書き保存
            with open(new_local_path, 'rb') as f:
                result = dbx.files_upload(
                    f=f.read(),
                    path=new_dbx_path,
                    mode=WriteMode.overwrite,
                    mute=True
                )

            actual_new_path = result.metadata.path_display
            logger.info(f"Renamed file to: {actual_new_path}")
        except ApiError as e:
            logger.error(f"Error renaming file: {e}")
            raise e

        logger.info(f"Successfully processed file: {dbx_path}")
    except Exception as e:
        logger.error(f"Error processing file {dbx_path}: {e}")
    finally:
        # 一時ファイルの削除
        try:
            if os.path.exists(old_local_path):
                os.remove(old_local_path)
            if os.path.exists(new_local_path):
                os.remove(new_local_path)
        except Exception as e:
            logger.warning(f"Error cleaning up temp files: {e}")
