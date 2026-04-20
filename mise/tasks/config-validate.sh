#!/usr/bin/env bash
#MISE description="config.yaml を検証"
set -euo pipefail

CONFIG_FILE="${1:-${HOME}/.config/repo-sync/config.yaml}"

if [[ ! -f "$CONFIG_FILE" ]]; then
    echo "ERROR: Config file not found: $CONFIG_FILE" >&2
    echo "Run 'mise run config-init' to create one." >&2
    exit 1
fi

echo "Validating: $CONFIG_FILE"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
uv run python "$SCRIPT_DIR/scripts/config_validate.py" "$CONFIG_FILE"
