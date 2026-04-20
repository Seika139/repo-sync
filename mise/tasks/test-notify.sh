#!/usr/bin/env bash
# shellcheck disable=SC1091

#MISE description="Discord 通知のテスト送信"
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$SCRIPT_DIR/common.sh"

CONFIG_FILE="${1:-${HOME}/.config/repo-sync/config.yaml}"

if [[ ! -f "$CONFIG_FILE" ]]; then
  print_c red "ERROR: Config file not found: $CONFIG_FILE"
  exit 1
fi

print_c cyan "Sending test notification..."

uv run python "$SCRIPT_DIR/scripts/test_notify.py" "$CONFIG_FILE"
