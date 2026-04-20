#!/usr/bin/env bash
#MISE description="Discord 通知のテスト送信"
set -euo pipefail

CONFIG_FILE="${1:-${HOME}/.config/repo-sync/config.yaml}"

if [[ ! -f "$CONFIG_FILE" ]]; then
    echo "ERROR: Config file not found: $CONFIG_FILE" >&2
    exit 1
fi

echo "Sending test notification..."

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
uv run python "$SCRIPT_DIR/scripts/test_notify.py" "$CONFIG_FILE"
