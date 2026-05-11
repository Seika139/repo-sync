#!/usr/bin/env bash
# shellcheck disable=SC1091

#MISE description="repo-sync のログを表示 (file|journal|timer)"
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$SCRIPT_DIR/common.sh"

LOG_FILE="/var/log/repo-sync/repo-sync.log"
LOG_WINDOW_MINUTES=60

selected="${1:-}"

if [[ -z "$selected" ]]; then
  selected=$(
    printf "file\njournal\ntimer\n" | fzf --height 7 --border --prompt "logs> " \
      --preview '
        case {} in
          file) printf "直近 60 分のログを表示します\n/var/log/repo-sync/repo-sync.log\n" ;;
          journal) printf "journalctl で直近 50 件を表示します\njournalctl -u repo-sync.service -n 50\n" ;;
          timer) printf "次回実行時刻を確認します\nsystemctl list-timers repo-sync.timer\n" ;;
        esac
      ' --preview-window=right,50%
  )
fi

case "$selected" in
  file)
    print_c cyan "直近 ${LOG_WINDOW_MINUTES} 分のログを表示します"
    # GNU date (Linux / WSL / Git Bash) と BSD date (macOS) で構文が違うので分岐
    case "$(uname -s)" in
      Darwin*)
        cutoff=$(date -v "-${LOG_WINDOW_MINUTES}M" '+%Y-%m-%d %H:%M:%S')
        ;;
      *)
        cutoff=$(date -d "${LOG_WINDOW_MINUTES} minutes ago" '+%Y-%m-%d %H:%M:%S')
        ;;
    esac
    # POSIX 互換のため {N} 量指定子は使わず文字クラスを並べる
    awk -v cutoff="$cutoff" '
      /^[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9] [0-9][0-9]:[0-9][0-9]:[0-9][0-9]/ {
        include = (substr($0, 1, 19) >= cutoff)
      }
      include { print }
    ' "$LOG_FILE"
    ;;
  journal)
    print_c cyan "journalctl で直近 50 件を表示します"
    sudo journalctl -u repo-sync.service -n 50 --no-pager
    ;;
  timer)
    print_c cyan "次回実行時刻を確認します"
    sudo systemctl list-timers repo-sync* --all
    ;;
  *)
    print_c red "無効なオプションです: $selected (file|journal|timer)"
    exit 1
    ;;
esac
