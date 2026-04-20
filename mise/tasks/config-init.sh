#!/usr/bin/env bash
#MISE description="config.yaml をサンプルから作成"
set -euo pipefail

CONFIG_DIR="${HOME}/.config/repo-sync"
CONFIG_FILE="${CONFIG_DIR}/config.yaml"
SAMPLE_FILE="config.sample.yaml"

if [[ -f "$CONFIG_FILE" ]]; then
    echo "config.yaml already exists: $CONFIG_FILE"
    echo "To recreate, delete the existing file first."
    exit 0
fi

if [[ ! -f "$SAMPLE_FILE" ]]; then
    echo "ERROR: $SAMPLE_FILE not found in $(pwd)" >&2
    exit 1
fi

mkdir -p "$CONFIG_DIR"
cp "$SAMPLE_FILE" "$CONFIG_FILE"
chmod 600 "$CONFIG_FILE"

echo "Created: $CONFIG_FILE (mode 600)"
echo "Edit the file to set your Discord webhook URL and repos."
echo ""
echo "  \$EDITOR $CONFIG_FILE"
