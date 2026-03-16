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
INSTALL_DIR="${HOME}/Library/Application Support/local.schedule-to-icloud"
PLIST_PATH="${HOME}/Library/LaunchAgents/${LABEL}.plist"
LOG_DIR="${HOME}/Library/Logs/schedule_to_icloud"

# ------------------------------------------------------------------ #
# アンインストール関数
# ------------------------------------------------------------------ #
do_uninstall() {
    echo "[uninstall] LaunchAgent を停止・削除します..."

    if launchctl list "$LABEL" &>/dev/null; then
        launchctl bootout "gui/$(id -u)/${LABEL}" 2>/dev/null || true
        echo "[uninstall] LaunchAgent を停止しました。"
    else
        echo "[uninstall] LaunchAgent は登録されていません。"
    fi

    if "$SCRIPT_DIR/run.sh" --check-installed 2>/dev/null; then
        echo "[schedule_to_icloud] 永続キューを削除しています..."
        "$SCRIPT_DIR/run.sh" --uninstall || true
    else
        echo "[schedule_to_icloud] 永続キューは存在しません。スキップします。"
    fi

    if [[ -f "$PLIST_PATH" ]]; then
        rm "$PLIST_PATH"
        echo "[uninstall] plist を削除しました: $PLIST_PATH"
    fi

    if [[ -d "$INSTALL_DIR" ]]; then
        rm -rf "$INSTALL_DIR"
        echo "[uninstall] インストールディレクトリを削除しました: $INSTALL_DIR"
    fi

    echo "[uninstall] 完了しました。"
    return 0
}

# ------------------------------------------------------------------ #
# インストール関数
# ------------------------------------------------------------------ #
do_install() {
    # 前提確認
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

    echo "[install] 依存モジュールを確認しています..."
    cd "$SCRIPT_DIR"
    uv sync --quiet

    echo "[install] ${INSTALL_DIR} にファイルをコピーしています..."
    mkdir -p "$INSTALL_DIR"
    rsync -a --delete \
        --exclude='.venv/' \
        --exclude='__pycache__/' \
        --exclude='*.pyc' \
        --exclude='.git/' \
        --exclude='tests/' \
        --exclude='install.sh' \
        "${SCRIPT_DIR}/" "${INSTALL_DIR}/"

    echo "[install] .env の内容を確認してください:"
    echo "---"
    cat "${SCRIPT_DIR}/.env"
    echo "---"
    read -rp "[install] この内容で ${INSTALL_DIR}/.env にコピーしてよいですか？ [y/N] " _answer
    if [[ "$_answer" != "y" && "$_answer" != "Y" ]]; then
        echo "[install] インストールを中止しました。"
        exit 1
    fi
    cp "${SCRIPT_DIR}/.env" "${INSTALL_DIR}/.env"
    mv "${INSTALL_DIR}/run.sh" "${INSTALL_DIR}/schedule-to-icloud"
    chmod +x "${INSTALL_DIR}/schedule-to-icloud"

    echo "[install] uv バイナリをコピーしています..."
    _uv_src="$(command -v uv)"
    cp "$_uv_src" "${INSTALL_DIR}/uv"
    chmod +x "${INSTALL_DIR}/uv"

    # インストール先の run.sh が INSTALL_DIR 内の uv を使うよう書き換え
    sed -i '' "s|^uv sync|\"${INSTALL_DIR}/uv\" sync|" "${INSTALL_DIR}/schedule-to-icloud"
    sed -i '' "s| uv run | \"${INSTALL_DIR}/uv\" run |" "${INSTALL_DIR}/schedule-to-icloud"

    mkdir -p "$LOG_DIR"

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
        <string>${INSTALL_DIR}/schedule-to-icloud</string>
    </array>

    <key>WorkingDirectory</key>
    <string>${INSTALL_DIR}</string>

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

    if "${INSTALL_DIR}/schedule-to-icloud" --check-installed 2>/dev/null; then
        echo "[schedule_to_icloud] 永続キューは既に存在します。スキップします。"
    else
        echo "[schedule_to_icloud] 永続キューを作成しています..."
        "${INSTALL_DIR}/schedule-to-icloud" --install
    fi

    echo "[install] LaunchAgent を登録しています..."

    # 既存の登録を無条件に解除してから再登録
    # （launchctl list に出ない状態でも bootstrap namespace に残っている場合があるため）
    launchctl bootout "gui/$(id -u)/${LABEL}" 2>/dev/null || true
    launchctl bootstrap "gui/$(id -u)" "$PLIST_PATH"

    echo ""
    echo "インストール完了！"
    echo "  ラベル       : ${LABEL}"
    echo "  plist        : ${PLIST_PATH}"
    echo "  インストール : ${INSTALL_DIR}"
    echo "  ログ         : ${LOG_DIR}/"
    echo ""
    echo "操作コマンド:"
    echo "  停止  : launchctl stop ${LABEL}"
    echo "  起動  : launchctl start ${LABEL}"
    echo "  状態  : launchctl list ${LABEL}"
    echo "  削除  : ${SCRIPT_DIR}/install.sh --uninstall"
}

# ------------------------------------------------------------------ #
# エントリポイント
# ------------------------------------------------------------------ #
if [[ "${1:-}" == "--uninstall" ]]; then
    do_uninstall
    exit 0
fi

if launchctl list "$LABEL" &>/dev/null; then
    echo "[install] 既にインストール済みです。一度アンインストールして再インストールします..."
    do_uninstall
fi

do_install
