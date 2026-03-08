#!/bin/bash
# schedule_to_icloud 起動スクリプト

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "[schedule_to_icloud] 依存モジュールを確認しています..."
uv sync --quiet

echo "[schedule_to_icloud] 起動します..."
exec env PYTHONPATH=src uv run s2ic "$@"
