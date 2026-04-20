#!/usr/bin/env bash

# shellcheck disable=SC1091
#MISE description="config.yaml をサンプルから作成"
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$SCRIPT_DIR/common.sh"

CONFIG_DIR="${HOME}/.config/repo-sync"
CONFIG_FILE="${CONFIG_DIR}/config.yaml"
SAMPLE_FILE="config.sample.yaml"

if [[ -f "$CONFIG_FILE" ]]; then
  print_c yellow "config.yaml already exists: $CONFIG_FILE"
  print_c yellow "To recreate, delete the existing file first."
  exit 0
fi

if [[ ! -f "$SAMPLE_FILE" ]]; then
  print_c red "ERROR: $SAMPLE_FILE not found in $(pwd)"
  exit 1
fi

mkdir -p "$CONFIG_DIR"
cp "$SAMPLE_FILE" "$CONFIG_FILE"
chmod 600 "$CONFIG_FILE"

print_c green "Created: $CONFIG_FILE (mode 600)"
print_c cyan "Edit the file to set your Discord webhook URL and repos."
echo ""
print_c cyan "  \$EDITOR $CONFIG_FILE"
