#!/usr/bin/env bash
#MISE description="systemd timer の操作 (引数: start|stop|status|enable|disable)"
set -euo pipefail

declare -A COMMANDS=(
    ["start:手動で即時実行 (one-shot)"]="sudo systemctl start repo-sync.service"
    ["stop:timer を停止"]="sudo systemctl stop repo-sync.timer"
    ["status:timer の状態を表示"]="systemctl list-timers repo-sync.timer && echo '' && systemctl status repo-sync.timer --no-pager || true"
    ["enable:timer を有効化して開始"]="sudo systemctl enable --now repo-sync.timer"
    ["disable:timer を停止して無効化"]="sudo systemctl stop repo-sync.timer && sudo systemctl disable repo-sync.timer"
)

select_action() {
    if [[ -n "${1:-}" ]]; then
        echo "$1"
        return
    fi
    printf '%s\n' "${!COMMANDS[@]}" | sort | fzf --prompt="service> " | cut -d: -f1
}

ACTION="$(select_action "${1:-}")"
[[ -z "$ACTION" ]] && exit 0

for key in "${!COMMANDS[@]}"; do
    if [[ "$key" == "$ACTION:"* ]]; then
        eval "${COMMANDS[$key]}"
        exit 0
    fi
done

echo "Unknown action: $ACTION (start|stop|status|enable|disable)" >&2
exit 1
