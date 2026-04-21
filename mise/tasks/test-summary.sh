#!/usr/bin/env bash
# shellcheck disable=SC1091

#MISE description="週次サマリーの手動実行テスト"
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$SCRIPT_DIR/common.sh"

print_c cyan "週次サマリーを送信します..."

uv run python -m repo_sync.weekly_summary
