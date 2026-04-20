#!/usr/bin/env bash
set -euo pipefail

config="${REPO_SYNC_CONFIG:-$HOME/.config/repo-sync/config.yaml}"

if [[ ! -f "$config" ]]; then
  echo "Config not found: $config" >&2
  exit 1
fi

webhook_url=$(grep -m1 'discord_webhook_url:' "$config" | sed 's/.*: *"\?\([^"]*\)"\?/\1/')

if [[ -z "$webhook_url" || "$webhook_url" == *"YOUR_"* ]]; then
  echo "No valid webhook URL configured" >&2
  exit 1
fi

bot_username=$(grep -m1 'bot_username:' "$config" | sed 's/.*: *"\?\([^"]*\)"\?/\1/')
bot_username="${bot_username:-repo-sync}"

timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
hostname=$(hostname)

recent_log=$(journalctl -u repo-sync.service -n 20 --no-pager 2>/dev/null | tail -10 || echo "journalctl unavailable")

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
      {"name": "Recent logs", "value": "\`\`\`\\n${recent_log//\"/\\\"}\\n\`\`\`"}
    ]
  }]
}
EOF
)

curl -sS -H "Content-Type: application/json" -d "$payload" "$webhook_url"
