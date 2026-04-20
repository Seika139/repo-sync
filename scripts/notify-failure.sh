#!/usr/bin/env bash
set -euo pipefail

config="${REPO_SYNC_CONFIG:-$HOME/.config/repo-sync/config.yaml}"

if [[ ! -f "$config" ]]; then
  echo "Config not found: $config" >&2
  exit 1
fi

# コメント行を除外してキーを取得
yaml_value() {
  grep -v '^ *#' "$config" | grep -m1 "^ *$1:" | sed 's/^[^:]*:[[:space:]]*//; s/[[:space:]][[:space:]]*#.*$//; s/^"//; s/"$//'
}

webhook_url=$(yaml_value discord_webhook_url)

if [[ -z "$webhook_url" || "$webhook_url" == *"YOUR_"* ]]; then
  echo "No valid webhook URL configured" >&2
  exit 1
fi

bot_username=$(yaml_value bot_username)
bot_username="${bot_username:-repo-sync}"

timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
hostname=$(hostname)

recent_log=$(journalctl -u repo-sync.service -n 20 --no-pager 2>/dev/null | tail -10 || echo "journalctl unavailable")

# JSON エスケープ: バックスラッシュ → ダブルクォート → 改行 → タブ
json_escape() {
  local str="$1"
  str="${str//\\/\\\\}"
  str="${str//\"/\\\"}"
  str="${str//$'\n'/\\n}"
  str="${str//$'\t'/\\t}"
  printf '%s' "$str"
}

escaped_log=$(json_escape "$recent_log")

payload=$(
  cat <<EOF
{
  "username": "$bot_username",
  "embeds": [{
    "title": "repo-sync service failed",
    "color": 15548997,
    "fields": [
      {"name": "Host", "value": "$hostname", "inline": true},
      {"name": "Time", "value": "$timestamp", "inline": true},
      {"name": "Recent logs", "value": "\`\`\`\\n${escaped_log}\\n\`\`\`"}
    ]
  }]
}
EOF
)

curl -sS -H "Content-Type: application/json" -d "$payload" "$webhook_url"
