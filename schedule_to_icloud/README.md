# schedule_to_icloud

RabbitMQ から受信したスケジュール・TODO メッセージを、iCloud カレンダーおよびリマインダーに自動登録するデーモンです。
[DropboxAutomation](../README.md) が RabbitMQ に配信したメッセージを受信し、AppleScript 経由で iCloud に書き込みます。

## 動作要件

- **macOS 必須**: AppleScript (`osascript`) を使用して iCloud カレンダー・リマインダーを操作するため、macOS 上でのみ動作します。
- **iCloud 同期が必要**: 対象の Mac が iCloud にサインインしており、カレンダーおよびリマインダーの同期が有効になっている必要があります。
- **Docker 不可**: `osascript` はホスト OS の GUI アプリケーションを操作するため、コンテナ内での実行はできません。Mac 上でプロセスとして直接起動してください。
- Python 3.13 以上

## セットアップ

### 1. uv のインストール

パッケージ管理に [uv](https://github.com/astral-sh/uv) を使用しています。未インストールの場合は以下でインストールしてください。

```bash
brew install uv
```

### 2. 依存モジュールのインストール

```bash
uv sync
```

### 3. 環境変数の設定

`.env.sample` をコピーして `.env` を作成し、各値を設定してください。

| 環境変数 | 必須 | 説明 |
|---|---|---|
| `RABBITMQ_PUBLISH_EXCHANGE` | 必須 | RabbitMQ 接続 URI。書式: `amqp(s)://user:pass@host:port/vhost/exchange` |
| `ICLOUD_REMINDER_LIST` | 任意 | 登録先リマインダーリスト名（デフォルト: `Reminders`） |
| `ICLOUD_CALENDAR_NAME` | 任意 | 登録先カレンダー名（デフォルト: `Calendar`） |
| `TARGET_INDIVIDUAL_REPLACEMENTS` | 任意 | 名前正規化ルール（YAML リスト形式、デフォルト: `[]`） |

`ICLOUD_REMINDER_LIST` と `ICLOUD_CALENDAR_NAME` は、単純な文字列の代わりに YAML 形式の正規表現ルーティング設定を指定することもできます。`target_individuals`（対象者名）に応じて登録先を振り分けたい場合に使用します。

```yaml
- regex: '山田'
  destination: '仕事'
- destination: 'Reminders'   # regex なし → マッチしなかった場合のデフォルト
```

## 使用方法

### 手動起動

`run.sh` を使うと、`uv sync` による依存モジュールの確認を行ってから起動します。

```bash
./run.sh
```

起動すると RabbitMQ への接続を確立し、メッセージの受信を待ち受けます。接続が切断された場合は自動的に再接続を試みます。終了するには `Ctrl+C` を押してください。

### JSON を直接指定して処理

`--json` オプションを使うと、RabbitMQ に接続せず、JSON 文字列を直接渡して処理を実行できます。
[DropboxAutomation](../README.md) のローカルモード（単一 PDF 処理）から呼び出す際に使用します。

```bash
./run.sh --json '{"todo": [], "schedule": [], "target_individuals": ["山田太郎"]}'
```

処理が完了すると即座に終了します（デーモンとしては動作しません）。

ヘルプの表示:

```bash
./run.sh --help
```

### macOS 自動起動（LaunchAgent）

`install.sh` を使うと、macOS ログイン時に自動起動する LaunchAgent として登録されます。
クラッシュした場合も自動的に再起動します。

```bash
./install.sh
```

インストール時に `uv sync` が実行されるため、事前に `uv sync` を手動で行う必要はありません。

ログは `~/Library/Logs/schedule_to_icloud/` に出力されます。

インストール後の操作:

```bash
launchctl stop  local.schedule-to-icloud  # 停止
launchctl start local.schedule-to-icloud  # 起動
launchctl list  local.schedule-to-icloud  # 状態確認
```

アンインストール（LaunchAgent の削除と停止）:

```bash
./install.sh --uninstall
```
