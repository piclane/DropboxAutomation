import logging
import os

from dotenv import load_dotenv

# ロギングの設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# .envファイルをロード
load_dotenv()

# 環境変数から設定を読み込み
DROPBOX_APP_KEY = os.environ.get("DROPBOX_APP_KEY")
DROPBOX_APP_SECRET = os.environ.get("DROPBOX_APP_SECRET")
DROPBOX_REFRESH_TOKEN = os.environ.get("DROPBOX_REFRESH_TOKEN")
DROPBOX_FOLDER_PATH = os.environ.get("DROPBOX_FOLDER_PATH", "/監視対象フォルダパス")
CLAUDE_API_KEY = os.environ.get("CLAUDE_API_KEY")
PORT = os.environ.get("PORT", "3003")


# 環境変数の検証（ローカルファイル処理の場合はDropbox関連の環境変数は不要）
def validate_env_vars(for_dropbox=True):
    required_env_vars = ["CLAUDE_API_KEY"]

    if for_dropbox:
        required_env_vars.extend([
            "DROPBOX_APP_KEY", "DROPBOX_APP_SECRET", "DROPBOX_REFRESH_TOKEN",
        ])

    missing_vars = [var for var in required_env_vars if not os.environ.get(var)]
    if missing_vars:
        logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        return False
    return True
