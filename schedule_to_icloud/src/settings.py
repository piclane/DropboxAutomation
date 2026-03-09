"""
DropboxAutomationのiCloud連携用設定モジュール。
環境変数から設定を読み込み、アプリケーション全体で利用可能な定数を提供します。
"""
import logging
import os

from dotenv import load_dotenv

# ロギングの設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger: logging.Logger = logging.getLogger(__name__)

# .envファイルをロード
load_dotenv()

# RabbitMQの接続先URI
RABBITMQ_PUBLISH_EXCHANGE: str | None = os.environ.get("RABBITMQ_PUBLISH_EXCHANGE")

# iCloudリマインダーのリスト名
ICLOUD_REMINDER_LIST: str = os.environ.get("ICLOUD_REMINDER_LIST", "Reminders")

# iCloudカレンダーのカレンダー名
ICLOUD_CALENDAR_NAME: str = os.environ.get("ICLOUD_CALENDAR_NAME", "Calendar")

# 名前置換用の正規表現と置き換え後の文字列のリスト（YAML形式）
TARGET_INDIVIDUAL_REPLACEMENTS: str = os.environ.get("TARGET_INDIVIDUAL_REPLACEMENTS", "[]")

