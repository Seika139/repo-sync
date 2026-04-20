#!/usr/bin/env bash
#MISE description="repo-sync のログを表示 (引数: file|journal|timer)"
set -euo pipefail

LOG_FILE="/var/log/repo-sync/repo-sync.log"

declare -A COMMANDS=(
    ["file:ログファイルを tail -f"]="tail -f $LOG_FILE"
    ["journal:journalctl で直近 50 件"]="journalctl -u repo-sync.service -n 50 --no-pager"
    ["timer:次回実行時刻を確認"]="systemctl list-timers repo-sync.timer"
)

select_mode() {
    if [[ -n "${1:-}" ]]; then
        echo "$1"
        return
    fi
    printf '%s\n' "${!COMMANDS[@]}" | sort | fzf --prompt="logs> " | cut -d: -f1
}

MODE="$(select_mode "${1:-}")"
[[ -z "$MODE" ]] && exit 0

for key in "${!COMMANDS[@]}"; do
    if [[ "$key" == "$MODE:"* ]]; then
        eval "${COMMANDS[$key]}"
        exit 0
    fi
done

echo "Unknown mode: $MODE (file|journal|timer)" >&2
exit 1
