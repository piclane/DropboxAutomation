#!/bin/bash
# schedule_to_icloud macOS 自動起動インストーラー
#
# macOS ログイン時に schedule_to_icloud を自動起動する LaunchAgent を登録します。
# アンインストールするには --uninstall オプションを指定してください。
#
# 使用方法:
#   ./install.sh             # インストール
#   ./install.sh --uninstall # アンインストール

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LABEL="local.schedule-to-icloud"
PLIST_PATH="${HOME}/Library/LaunchAgents/${LABEL}.plist"
LOG_DIR="${HOME}/Library/Logs/schedule_to_icloud"

# ------------------------------------------------------------------ #
# アンインストール
# ------------------------------------------------------------------ #
if [[ "${1:-}" == "--uninstall" ]]; then
    echo "[uninstall] LaunchAgent を停止・削除します..."

    if launchctl list | grep -q "$LABEL" 2>/dev/null; then
        launchctl bootout "gui/$(id -u)/${LABEL}" 2>/dev/null || \
            launchctl unload "$PLIST_PATH" 2>/dev/null || true
        echo "[uninstall] LaunchAgent を停止しました。"
    else
        echo "[uninstall] LaunchAgent は登録されていません。"
    fi

    if [[ -f "$PLIST_PATH" ]]; then
        rm "$PLIST_PATH"
        echo "[uninstall] plist を削除しました: $PLIST_PATH"
    fi

    echo "[uninstall] 完了しました。"
    exit 0
fi

# ------------------------------------------------------------------ #
# 前提確認
# ------------------------------------------------------------------ #
if [[ "$(uname)" != "Darwin" ]]; then
    echo "エラー: このスクリプトは macOS 専用です。" >&2
    exit 1
fi

if ! command -v uv &>/dev/null; then
    echo "エラー: uv が見つかりません。先に uv をインストールしてください。" >&2
    echo "  curl -LsSf https://astral.sh/uv/install.sh | sh" >&2
    exit 1
fi

if [[ ! -f "${SCRIPT_DIR}/.env" ]]; then
    echo "エラー: .env ファイルが見つかりません。" >&2
    echo "  ${SCRIPT_DIR}/.env を作成し、RABBITMQ_PUBLISH_EXCHANGE などを設定してください。" >&2
    exit 1
fi

# ------------------------------------------------------------------ #
# インストール
# ------------------------------------------------------------------ #
echo "[install] 依存モジュールを確認しています..."
cd "$SCRIPT_DIR"
uv sync --quiet

mkdir -p "$LOG_DIR"

# run.sh に実行権限を付与
chmod +x "${SCRIPT_DIR}/run.sh"

echo "[install] LaunchAgent plist を生成しています..."
cat > "$PLIST_PATH" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
    "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${LABEL}</string>

    <key>ProgramArguments</key>
    <array>
        <string>${SCRIPT_DIR}/run.sh</string>
    </array>

    <key>WorkingDirectory</key>
    <string>${SCRIPT_DIR}</string>

    <!-- ログイン時に自動起動 -->
    <key>RunAtLoad</key>
    <true/>

    <!-- 終了した場合は自動再起動 -->
    <key>KeepAlive</key>
    <true/>

    <!-- ログ出力先 -->
    <key>StandardOutPath</key>
    <string>${LOG_DIR}/stdout.log</string>
    <key>StandardErrorPath</key>
    <string>${LOG_DIR}/stderr.log</string>
</dict>
</plist>
EOF

echo "[install] LaunchAgent を登録しています..."

# 既に登録済みの場合は一度停止してから再登録
if launchctl list | grep -q "$LABEL" 2>/dev/null; then
    echo "[install] 既存の LaunchAgent を停止します..."
    launchctl bootout "gui/$(id -u)/${LABEL}" 2>/dev/null || \
        launchctl unload "$PLIST_PATH" 2>/dev/null || true
fi

launchctl bootstrap "gui/$(id -u)" "$PLIST_PATH" 2>/dev/null || \
    launchctl load "$PLIST_PATH"

echo ""
echo "インストール完了！"
echo "  ラベル    : ${LABEL}"
echo "  plist     : ${PLIST_PATH}"
echo "  ログ      : ${LOG_DIR}/"
echo ""
echo "操作コマンド:"
echo "  停止  : launchctl stop ${LABEL}"
echo "  起動  : launchctl start ${LABEL}"
echo "  状態  : launchctl list ${LABEL}"
echo "  削除  : ${SCRIPT_DIR}/install.sh --uninstall"
