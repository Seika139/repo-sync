#!/usr/bin/env bash

# shellcheck disable=SC1091
#MISE description="config.yaml を検証"
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$SCRIPT_DIR/common.sh"

CONFIG_FILE="${1:-${HOME}/.config/repo-sync/config.yaml}"

if [[ ! -f "$CONFIG_FILE" ]]; then
  print_c red "ERROR: Config file not found: $CONFIG_FILE"
  print_c yellow "Run 'mise run config-init' to create one."
  exit 1
fi

print_c cyan "Validating: $CONFIG_FILE"

uv run python "$SCRIPT_DIR/scripts/config_validate.py" "$CONFIG_FILE"
