#!/usr/bin/env bash
# shellcheck disable=SC1091

#MISE description="systemd timer の操作 (status|start|stop|enable|disable)"
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$SCRIPT_DIR/common.sh"

selected="${1:-}"

if [[ -z "$selected" ]]; then
  selected=$(
    printf "status\nstart\nstop\nenable\ndisable\n" | fzf --height 9 --border --prompt "service> " \
      --preview '
        case {} in
          status) printf "timer の状態を表示します\nsystemctl list-timers repo-sync.timer\n" ;;
          start) printf "手動で即時実行します (one-shot)\nsudo systemctl start repo-sync.service\n" ;;
          stop) printf "timer を停止します\nsudo systemctl stop repo-sync.timer\n" ;;
          enable) printf "timer を有効化して開始します\nsudo systemctl enable --now repo-sync.timer\n" ;;
          disable) printf "timer を停止して無効化します\nsudo systemctl stop + disable repo-sync.timer\n" ;;
        esac
      ' --preview-window=right,50%
  )
fi

case "$selected" in
  status)
    print_c cyan "timer の状態を表示します"
    systemctl list-timers repo-sync.timer
    echo ""
    systemctl status repo-sync.timer --no-pager || true
    ;;
  start)
    print_c cyan "手動で即時実行します (one-shot)"
    sudo systemctl start repo-sync.service
    ;;
  stop)
    print_c cyan "timer を停止します"
    sudo systemctl stop repo-sync.timer
    ;;
  enable)
    print_c cyan "timer を有効化して開始します"
    sudo systemctl enable --now repo-sync.timer
    ;;
  disable)
    print_c cyan "timer を停止して無効化します"
    sudo systemctl stop repo-sync.timer
    sudo systemctl disable repo-sync.timer
    ;;
  *)
    print_c red "無効なオプションです: $selected (status|start|stop|enable|disable)"
    exit 1
    ;;
esac
