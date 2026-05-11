#!/usr/bin/env bash
# shellcheck disable=SC1091

#MISE description="repo-sync のログを tail -f でリアルタイム監視する"
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$SCRIPT_DIR/common.sh"

LOG_FILE="/var/log/repo-sync/repo-sync.log"

print_c cyan "ログをリアルタイム監視します (Ctrl+C で終了)"
print_c yellow "  $LOG_FILE"
tail -f "$LOG_FILE"
