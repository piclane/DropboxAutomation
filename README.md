# PDF処理自動化アプリケーション

このアプリケーションは、Dropboxに追加されたPDFファイルを自動的に処理し、AIを使って内容を分析してファイル名を変更し、要約を注釈として追加するツールです。

## 機能概要

- **Dropbox連携**: 指定フォルダにアップロードされたPDFファイルを監視・処理
- **AI文書分析**: Claude AIを使用してPDF内容を分析
- **メタデータ抽出**: PDFから日付、タイトル、要約を自動生成
- **ファイル名変更**: 分析結果に基づき「日付 タイトル.pdf」形式にリネーム
- **PDF注釈追加**: 生成された要約をPDFに注釈として追加
- **2つの実行モード**:
  - Webhookモード: Dropboxのフォルダを監視して自動処理
  - ローカルファイルモード: コマンドラインで指定したPDFを直接処理

## 前提条件

- Python 3.9以上
- Dropboxアカウントとリフレッシュトークン
- Anthropic Claude API キー

## Dropbox のリフレッシュトークンの取得方法

1. ブラウザで以下の URL を開きます。{AppKey} は適切に置きかえてください。
   ```
   https://www.dropbox.com/oauth2/authorize?client_id={Appkey}&token_access_type=offline&response_type=code
   ```
   「アクセスコードが生成されました」という表示とアクセスコードが表示されるので、アクセスコードをメモします
2. リフレッシュトークンを取得します。{AppKey} {AppSecret} {AccessCode} などは適切に置きかえてください。
   ```shell
   curl -u '{AppKey}:{AppSecret}' -d 'code={AccessCode}' -d 'grant_type=authorization_code' 'https://api.dropboxapi.com/oauth2/token'
   ```
3. 以下の様な JSON が取得できるので、refresh_token の値をメモしてください。
   ```json
   {
     "access_token": "xxxxxxxxxxxxx",
     "token_type": "bearer",
     "expires_in": 14400,
     "refresh_token": "xxxxxxxxxxxxx",
     "scope": "account_info.read files.content.read files.content.write files.metadata.read files.metadata.write",
     "uid": "123456789",
     "account_id": "xxxxxxxxxxxxx"
   }
   ```

## インストール

1. リポジトリをクローン

```bash
git clone git@github.com:piclane/DropboxAutomation.git
cd dropbox-automation
```

2. uv を使って環境を作成

uv のインストール:
- 公式インストール手順: [https://docs.astral.sh/uv/getting-started/installation/](https://docs.astral.sh/uv/getting-started/installation/)
- Mac の場合: `brew install uv`

環境のセットアップ:
```bash
# プロジェクトの依存関係をインストール
uv sync
```

### 依存パッケージ

このアプリケーションは以下のパッケージに依存しています:

- fastapi>=0.115.12
- uvicorn>=0.34.2
- dropbox>=12.0.2
- anthropic>=0.5.0
- python-dotenv>=0.19.0
- pydantic>=2.0.0
- PyMuPDF>=1.25.5

3. 環境変数の設定

`.env`ファイルを作成して以下の環境変数を設定:

```
# Anthropic Claude API設定（必須）
CLAUDE_API_KEY=your_claude_api_key

# Dropbox設定（Webhookモードの場合必須）
DROPBOX_APP_KEY=your_dropbox_app_key
DROPBOX_APP_SECRET=your_dropbox_app_secret
DROPBOX_REFRESH_TOKEN=your_dropbox_refresh_token
DROPBOX_FOLDER_PATH=/path/to/your/dropbox/folder  # デフォルト: "/監視対象フォルダパス"

# ポート番号（Webhookモードの場合のみ）
PORT=8080
```

**注意**:
- ローカルファイルモード: `CLAUDE_API_KEY`のみが必須です
- Webhookモード: 上記すべての環境変数が必須です

## 使用方法

### ローカルファイルモード

単一のPDFファイルを処理する場合:

```bash
uv run main.py /path/to/your/local/file.pdf
```

処理結果:
- ファイルは「日付 タイトル.pdf」形式にリネームされます
- 生成された要約がPDFに注釈として追加されます
- 分析結果が標準出力に表示されます

### Webhookモード (Dropbox監視)

Dropboxフォルダを監視して自動処理する場合:

```bash
uv run main.py
```

このモードでは:
1. アプリケーションがWebhookサーバーとして起動します（デフォルトポート: 3003）
2. Dropboxからの通知を受け取ります
3. 指定したフォルダに「BRWDCE」で始まるPDFファイルが追加されると自動処理します
4. 処理されたファイルは「日付 タイトル.pdf」形式にリネームされ、要約が追加されます

## DropboxのWebhook設定

1. [Dropbox Developer Console](https://www.dropbox.com/developers/apps)でアプリを作成
2. 以下の権限を有効化:
  - `files.metadata.write`
  - `files.content.write`
  - `files.content.read`
3. OAuth2アクセストークンを生成
4. Webhookを設定（アプリのWebhookエンドポイントURLを指定）

## 技術的詳細

### ファイル構成

- `main.py`: アプリケーションのエントリーポイント、Webhook処理
- `ai.py`: Claude APIを使用したPDF分析ロジック
- `processer_local.py`: ローカルファイル処理
- `processor_dropbox.py`: Dropboxファイル処理
- `utils/`: PDFや Dropbox 操作のユーティリティ関数

### AIによる分析プロセス

PDFファイルは以下の手順で処理されます:

1. OCR処理（必要な場合）: 画像ベースのPDFからテキストを抽出
2. 文書分析:
  - 作成日の特定（YYYYMMDD形式）
  - タイトルの生成（50文字以内）
  - 要約の生成（約500文字）
3. 結果のJSON形式化と検証
4. ファイル名変更と注釈追加

## トラブルシューティング

- **Webhook接続エラー**: ネットワーク設定とDropboxのWebhook設定を確認
- **API認証エラー**: API KEYの正確さとアクセス権限を確認
- **ファイル処理エラー**: ログを確認し、PDFファイルが有効か確認

## 注意事項

- 大量のPDFファイルを処理する際はAPI使用量とコストに注意してください
- 処理時間はPDFのサイズと複雑さによって異なります
- 日本語のPDF処理に最適化されています

## ライセンス

Apache-2.0 license
