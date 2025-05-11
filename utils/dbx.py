import logging

from dropbox.exceptions import ApiError, AuthError

from dropbox import Dropbox
from settings import DROPBOX_REFRESH_TOKEN, DROPBOX_FOLDER_PATH, DROPBOX_APP_KEY, DROPBOX_APP_SECRET

logger = logging.getLogger(__name__)

def init_dropbox():
    """
    Dropbox クライアントの初期化と認証を実行

    :raises AuthError: 認証情報が無効または期限切れの場合
    :return: 認証済み Dropbox クライアントインスタンス
    """
    try:
        dbx = Dropbox(
            app_key=DROPBOX_APP_KEY,
            app_secret=DROPBOX_APP_SECRET,
            oauth2_refresh_token=DROPBOX_REFRESH_TOKEN,
        )
        account = dbx.users_get_current_account()
        logger.info(f"Connected to Dropbox as {account.name.display_name}")
        return dbx
    except AuthError as e:
        logger.error(f"Invalid Dropbox access token: {e}")
        raise e

def init_dropbox_cursor(dbx: Dropbox) -> str:
    """
    定された Dropbox フォルダの変更監視用カーソルを取得

    :param dbx: 認証済み Dropbox インスタンス
    :raises ApiError: API リクエストが失敗した場合
    :return: フォルダ監視用カーソル文字列
    """
    try:
        result = dbx.files_list_folder(DROPBOX_FOLDER_PATH)
        return result.cursor
    except ApiError as e:
        logger.error(f"Dropbox API error: {e}")
        raise e
