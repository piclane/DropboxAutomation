"""
RabbitMQから受信したメッセージを元に、iCloudのリマインダーやカレンダーに
TODOやスケジュールを登録するメインスクリプト。
"""
import argparse
import datetime
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import yaml
from typing import Any

import pika

from settings import (
    ICLOUD_CALENDAR_NAME,
    ICLOUD_REMINDER_LIST,
    RABBITMQ_PUBLISH_EXCHANGE,
    TARGET_INDIVIDUAL_REPLACEMENTS,
    logger,
)
from utils.rabbitmq_consumer import RabbitMQConsumer

def run_applescript(script: str) -> str:
    """
    AppleScriptを実行し、出力を返す。

    Args:
        script: 実行するAppleScriptの文字列。

    Returns:
        str: 標準出力の内容。エラー時は空文字列。
    """
    try:
        process = subprocess.Popen(
            ['osascript', '-e', script],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        stdout, stderr = process.communicate()
        if process.returncode != 0:
            logger.error(f"AppleScript error: {stderr}")
            return ""
        return stdout.strip()
    except Exception as e:
        logger.error(f"Failed to run AppleScript: {e}")
        return ""

def get_destination(config_yaml: str, target_individuals: list[str], default_value: str) -> str:
    """
    target_individualsに基づき、設定YAMLから適切な宛先（カレンダー名/リマインダーリスト名）を決定する。

    Args:
        config_yaml: 設定YAML文字列（正規表現と宛先のリスト、または単一の文字列）。
        target_individuals: 対象者のリスト。
        default_value: デフォルトの宛先。

    Returns:
        str: 決定された宛先。
    """
    try:
        config = yaml.safe_load(config_yaml)
        if not isinstance(config, list):
            # リストでない（単一の文字列など）場合はそのまま返す（デフォルト値も考慮）
            return str(config) if config else default_value

        # target_individuals が空の場合、条件なしの destination を探す
        # もしくは、全ての target_individuals に対してマッチングを行う
        for item in config:
            if not isinstance(item, dict):
                continue
            
            regex = item.get("regex")
            destination = item.get("destination")
            
            if not destination:
                continue
            
            if not regex:
                # regexがない場合はデフォルトの宛先として扱う（最初に見つかったものを採用）
                return destination
            
            for person in target_individuals:
                if re.search(regex, person):
                    return destination
                    
        return default_value
    except Exception as e:
        logger.warning(f"Failed to parse destination config: {e}")
        return default_value

def add_reminder(action: str, deadline: str | None = None, list_name: str = ICLOUD_REMINDER_LIST) -> None:
    """
    iCloudリマインダーにTODOを追加する。

    Args:
        action: 追加するTODOの内容。
        deadline: 期限（YYYY-MM-DD形式）。指定しない場合は期限なし。
        list_name: 追加先のリマインダーリスト名。
    """
    # AppleScript to add reminder
    # deadline is expected to be YYYY-MM-DD
    script = 'tell application "Reminders"\n'
    script += f'    set myList to list "{list_name}"\n'
    if deadline:
        try:
            d = datetime.datetime.strptime(deadline, "%Y-%m-%d")
            # AppleScript recognizes YYYY/MM/DD in most locales when using 'date' string
            date_str = f'"{d.year}/{d.month}/{d.day}"'
            script += f'    make new reminder at myList with properties {{name:"{action}", remind me date:date {date_str}}}\n'
        except ValueError:
            script += f'    make new reminder at myList with properties {{name:"{action}"}}\n'
    else:
        script += f'    make new reminder at myList with properties {{name:"{action}"}}\n'
    script += 'end tell'

    logger.info(f"Adding reminder to {list_name}: {action} (Deadline: {deadline})")
    run_applescript(script)

def add_calendar_event(
    title: str,
    description: str,
    location: str | None,
    start_dt_str: str,
    end_dt_str: str | None,
    is_all_day: bool,
    calendar_name: str = ICLOUD_CALENDAR_NAME
) -> None:
    """
    iCloudカレンダーにスケジュールを追加する。

    Args:
        title: イベントのタイトル。
        description: イベントの説明。
        location: 場所。
        start_dt_str: 開始日時（終日の場合はYYYY-MM-DD、そうでない場合はYYYY-MM-DDTHH:MM:SS）。
        end_dt_str: 終了日時（形式は開始日時と同様）。
        is_all_day: 終日イベントかどうかのフラグ。
        calendar_name: 追加先のカレンダー名。
    """
    # AppleScript to add calendar event
    script = 'tell application "Calendar"\n'
    script += f'    tell calendar "{calendar_name}"\n'

    props = [f'summary:"{title}"', f'description:"{description}"']
    if location:
        props.append(f'location:"{location}"')

    props.append(f'allday event:{"true" if is_all_day else "false"}')

    def format_date(dt_str: str | None, all_day: bool) -> str | None:
        """
        日時文字列をAppleScript用の日付形式に変換する。

        Args:
            dt_str: 日時文字列。
            all_day: 終日かどうか。

        Returns:
            str | None: AppleScript用の日付文字列、またはNone。
        """
        if not dt_str:
            return None
        try:
            if all_day:
                d = datetime.datetime.strptime(dt_str, "%Y-%m-%d")
                return f'"{d.year}/{d.month}/{d.day}"'
            else:
                d = datetime.datetime.strptime(dt_str, "%Y-%m-%dT%H:%M:%S")
                # For timed events, we include time in format YYYY/MM/DD HH:MM:SS
                return f'"{d.year}/{d.month}/{d.day} {d.hour}:{d.minute}:{d.second}"'
        except ValueError:
            return None

    start_date = format_date(start_dt_str, is_all_day)
    if start_date:
        props.append(f'start date:date {start_date}')

    end_date = format_date(end_dt_str, is_all_day)
    if is_all_day and not end_date:
        end_date = start_date
    elif not is_all_day and not end_date:
        # 終日予定ではなく、終了日時が指定されていない場合、開始日時の1時間後を設定
        try:
            d = datetime.datetime.strptime(start_dt_str, "%Y-%m-%dT%H:%M:%S")
            d_end = d + datetime.timedelta(hours=1)
            end_date = f'"{d_end.year}/{d_end.month}/{d_end.day} {d_end.hour}:{d_end.minute}:{d_end.second}"'
        except ValueError:
            pass

    if end_date:
        props.append(f'end date:date {end_date}')

    script += f'        make new event with properties {{{", ".join(props)}}}\n'
    script += '    end tell\n'
    script += 'end tell'

    logger.info(f"Adding calendar event: {title} (Start: {start_dt_str})")
    run_applescript(script)

def process_data(data: dict[str, Any]) -> None:
    """
    メッセージデータを解析し、iCloudリマインダーとカレンダーに登録する。

    Args:
        data: 処理対象のメッセージデータ。
    """
    logger.info(f"Received message: {data.get('title', 'No Title')}")

    # 対象者の名前をタイトルの先頭に付与するための接頭辞を作成
    target_individuals = data.get("target_individuals", [])

    # 名前の置換処理
    try:
        replacements = yaml.safe_load(TARGET_INDIVIDUAL_REPLACEMENTS)
        if isinstance(replacements, list):
            processed_individuals = []
            for name in target_individuals:
                new_name = name
                for item in replacements:
                    if isinstance(item, dict):
                        pattern = item.get("regex")
                        repl = item.get("replacement", "")
                        if pattern:
                            new_name = re.sub(pattern, repl, new_name)
                processed_individuals.append(new_name)
            target_individuals = processed_individuals
    except yaml.YAMLError as e:
        logger.warning(f"Failed to parse TARGET_INDIVIDUAL_REPLACEMENTS (YAML): {e}")

    prefix = ""
    if target_individuals:
        # 空文字になった名前を除外して結合
        filtered_individuals = [n for n in target_individuals if n.strip()]
        if filtered_individuals:
            prefix = ", ".join(filtered_individuals) + " "

    # 宛先リストの決定
    reminder_list = get_destination(ICLOUD_REMINDER_LIST, target_individuals, "Reminders")
    calendar_name = get_destination(ICLOUD_CALENDAR_NAME, target_individuals, "Calendar")

    # TODOを登録
    todos = data.get("todo", [])
    for todo in todos:
        if not isinstance(todo, dict):
            continue
        action = todo.get("action")
        deadline = todo.get("deadline")
        if action:
            add_reminder(f"{prefix}{action}", deadline, reminder_list)

    # スケジュールを登録
    schedules = data.get("schedule", [])
    for sch in schedules:
        if not isinstance(sch, dict):
            continue
        title = sch.get("title")
        description = sch.get("description", "")
        location = sch.get("location")
        start_dt = sch.get("start_datetime")
        end_dt = sch.get("end_datetime")
        is_all_day = sch.get("is_all_day", False)

        if title and start_dt:
            add_calendar_event(
                f"{prefix}{title}", description, location, start_dt, end_dt, is_all_day, calendar_name
            )


def process_message(
    ch: pika.channel.Channel,
    method: pika.spec.Basic.Deliver,
    properties: pika.spec.BasicProperties,
    body: bytes
) -> None:
    """
    RabbitMQからのメッセージを処理するコールバック。

    Args:
        ch: チャンネル。
        method: メソッド。
        properties: プロパティ。
        body: メッセージの本文。
    """
    try:
        body_str = body.decode('utf-8')
        data: dict[str, Any] = json.loads(body_str)
        logger.info(json.dumps(data, ensure_ascii=False, indent=2))
        process_data(data)
        # 正常に処理された場合は確認応答(ACK)を送信
        ch.basic_ack(delivery_tag=method.delivery_tag)

    except json.JSONDecodeError:
        logger.error("Failed to decode JSON message")
        # 形式が不正なメッセージも再度キューに戻さないよう、とりあえずACKを返すか、デッドレターに送るべきだが
        # 現状の設計に合わせてACKを返すように修正
        ch.basic_ack(delivery_tag=method.delivery_tag)
    except Exception as e:
        logger.exception(f"Error processing message: {e}")
        # 例外時も無限ループを避けるためACKを返すが、本来はnackなどの検討が必要
        ch.basic_ack(delivery_tag=method.delivery_tag)

def _check_requirements() -> None:
    """
    動作要件を確認し、満たされていない場合はエラーメッセージを表示して終了する。

    確認項目:
    - macOS 上で実行されているか
    - Docker コンテナ内ではないか
    - osascript コマンドが利用可能か
    - iCloud カレンダー・リマインダーアプリにアクセスできるか
    """
    errors: list[str] = []

    # macOS チェック
    if sys.platform != "darwin":
        errors.append(
            f"macOS が必要です（現在のプラットフォーム: {sys.platform}）。"
            " osascript は macOS 専用コマンドのため、他の OS では動作しません。"
        )

    # Docker コンテナチェック
    if os.path.exists("/.dockerenv"):
        errors.append(
            "Docker コンテナ内での実行は非対応です。"
            " osascript はホスト OS の GUI アプリを操作するため、コンテナ内では使用できません。"
            " iCloud と同期している Mac 上で直接起動してください。"
        )

    # osascript コマンドの存在チェック
    if shutil.which("osascript") is None:
        errors.append(
            "osascript コマンドが見つかりません。"
            " iCloud カレンダー・リマインダーへの登録に osascript が必要です。"
        )

    if errors:
        for msg in errors:
            logger.error(msg)
        sys.exit(1)

    # iCloud アプリへのアクセスチェック
    icloud_errors: list[str] = []
    for app in ("Calendar", "Reminders"):
        result = subprocess.run(
            ["osascript", "-e", f'tell application "{app}" to get name'],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            icloud_errors.append(
                f'iCloud {app} アプリへのアクセスに失敗しました。'
                f" iCloud にサインインし、{app} の同期が有効になっているか確認してください。"
                f"（エラー: {result.stderr.strip()}）"
            )

    if icloud_errors:
        for msg in icloud_errors:
            logger.error(msg)
        sys.exit(1)

    logger.info("動作要件チェック OK")


def main() -> None:
    """
    メインエントリポイント。RabbitMQからのメッセージ受信を開始する。
    """
    parser = argparse.ArgumentParser(
        description=(
            "RabbitMQ からスケジュール/TODO メッセージを受信し、"
            "iCloud カレンダーおよびリマインダーに登録するデーモンです。"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
環境変数:
  RABBITMQ_PUBLISH_EXCHANGE      RabbitMQ 接続 URI（必須）
                                   書式: amqp(s)://user:pass@host:port/vhost/exchange
  ICLOUD_REMINDER_LIST           リマインダーリスト名、または正規表現ルーティング設定（YAML）
                                   デフォルト: Reminders
  ICLOUD_CALENDAR_NAME           カレンダー名、または正規表現ルーティング設定（YAML）
                                   デフォルト: Calendar
  TARGET_INDIVIDUAL_REPLACEMENTS 名前正規化ルール（YAML リスト形式）
                                   書式: [{regex: '...', replacement: '...'}]
                                   デフォルト: []

YAML ルーティング設定例 (ICLOUD_REMINDER_LIST / ICLOUD_CALENDAR_NAME):
  - regex: '山田'
    destination: '仕事リマインダー'
  - destination: 'Reminders'   # regex なし → デフォルト
        """,
    )
    parser.add_argument(
        "--json",
        metavar="JSON",
        dest="json_str",
        help=(
            "処理する JSON 文字列を直接指定します。"
            " このオプションを使用した場合は RabbitMQ に接続せず、処理完了後に終了します。"
        ),
    )
    args = parser.parse_args()

    _check_requirements()

    if args.json_str is not None:
        try:
            data: dict[str, Any] = json.loads(args.json_str)
        except json.JSONDecodeError as e:
            logger.error(f"JSON のパースに失敗しました: {e}")
            sys.exit(1)
        process_data(data)
        return

    if not RABBITMQ_PUBLISH_EXCHANGE:
        logger.error("RABBITMQ_PUBLISH_EXCHANGE is not set in environment variables.")
        return

    logger.info(f"Connecting to RabbitMQ: {RABBITMQ_PUBLISH_EXCHANGE}")
    try:
        with RabbitMQConsumer(RABBITMQ_PUBLISH_EXCHANGE) as consumer:
            consumer.consume(process_message)
    except KeyboardInterrupt:
        logger.info("Interrupted by user, shutting down...")
    except Exception:
        # ログは RabbitMQConsumer.consume 内で出力されるため、ここでは詳細を抑制
        pass

if __name__ == "__main__":
    main()
