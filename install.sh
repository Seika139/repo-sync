#!/usr/bin/env bash
# =============================================================================
# install.sh - Set up repo-sync systemd timer on an Ubuntu server
# Run as root: sudo bash install.sh
# =============================================================================
set -euo pipefail

DEPLOY_USER="${DEPLOY_USER:-ebi}"
DEPLOY_HOME="/home/$DEPLOY_USER"
DEPLOY_DIR="${DEPLOY_DIR:-$DEPLOY_HOME/programs/tools/repo-sync}"
LOG_DIR="${LOG_DIR:-/var/log/repo-sync}"

# ---------------------------------------------------------------------------
# Pre-flight checks
# ---------------------------------------------------------------------------
if [[ "$(uname -s)" != "Linux" ]]; then
  echo "ERROR: This script is intended for Linux (Ubuntu) only" >&2
  exit 1
fi

if [[ $EUID -ne 0 ]]; then
  echo "ERROR: This script must be run as root (sudo bash install.sh)" >&2
  exit 1
fi

if ! id "$DEPLOY_USER" &>/dev/null; then
  echo "ERROR: User '$DEPLOY_USER' does not exist" >&2
  exit 1
fi

echo "=== repo-sync installer ==="

# ---------------------------------------------------------------------------
# 1. Verify repo-sync is deployable
# ---------------------------------------------------------------------------
echo "[1/5] Verifying repo-sync installation..."
if [[ ! -f "$DEPLOY_DIR/pyproject.toml" ]]; then
  echo "ERROR: $DEPLOY_DIR/pyproject.toml not found" >&2
  echo "  Clone the repo first: git clone git@github.com:Seika139/repo-sync.git $DEPLOY_DIR" >&2
  exit 1
fi

if ! command -v "$DEPLOY_HOME/.local/bin/mise" &>/dev/null; then
  echo "ERROR: mise not found at $DEPLOY_HOME/.local/bin/mise" >&2
  echo "  Install mise: curl https://mise.run | sh" >&2
  exit 1
fi

echo "  -> repo-sync found at $DEPLOY_DIR"

# ---------------------------------------------------------------------------
# 2. Sync dependencies via mise + uv
# ---------------------------------------------------------------------------
echo "[2/5] Syncing dependencies..."
sudo -u "$DEPLOY_USER" bash -c "cd $DEPLOY_DIR && $DEPLOY_HOME/.local/bin/mise exec -- uv sync --frozen"
echo "  -> dependencies synced"

# ---------------------------------------------------------------------------
# 3. Create log directory
# ---------------------------------------------------------------------------
echo "[3/5] Creating log directory $LOG_DIR..."
mkdir -p "$LOG_DIR"
chown "$DEPLOY_USER:$DEPLOY_USER" "$LOG_DIR"

# ---------------------------------------------------------------------------
# 4. Set up logrotate
# ---------------------------------------------------------------------------
echo "[4/5] Configuring logrotate..."
cat >/etc/logrotate.d/repo-sync <<'LOGROTATE'
/var/log/repo-sync/*.log {
    weekly
    rotate 4
    compress
    missingok
    notifempty
    copytruncate
}
LOGROTATE
echo "  -> logrotate configured (weekly, 4 rotations)"

# ---------------------------------------------------------------------------
# 5. Install systemd units
# ---------------------------------------------------------------------------
echo "[5/5] Installing systemd units..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

install_unit() {
  local src="$1"
  local dest
  dest="/etc/systemd/system/$(basename "$src")"
  sed \
    -e "s|__DEPLOY_USER__|$DEPLOY_USER|g" \
    -e "s|__DEPLOY_HOME__|$DEPLOY_HOME|g" \
    -e "s|__DEPLOY_DIR__|$DEPLOY_DIR|g" \
    -e "s|__LOG_DIR__|$LOG_DIR|g" \
    "$src" >"$dest"
}

install_unit "$SCRIPT_DIR/systemd/repo-sync.service"
install_unit "$SCRIPT_DIR/systemd/repo-sync.timer"
install_unit "$SCRIPT_DIR/systemd/repo-sync-notify-failure.service"
install_unit "$SCRIPT_DIR/systemd/repo-sync-summary.service"
install_unit "$SCRIPT_DIR/systemd/repo-sync-summary.timer"

systemctl daemon-reload
systemctl enable --now repo-sync.timer
systemctl enable --now repo-sync-summary.timer
echo "  -> repo-sync.timer enabled and started"
echo "  -> repo-sync-summary.timer enabled (weekly Monday 12:00)"

# ---------------------------------------------------------------------------
# Verify
# ---------------------------------------------------------------------------
echo ""
systemctl status repo-sync.timer --no-pager || true
echo ""
echo "=== Installation complete ==="
echo ""
echo "Next steps:"
echo "  1. Ensure config exists: $DEPLOY_HOME/.config/repo-sync/config.yaml"
echo "  2. Test manually:  sudo -u $DEPLOY_USER bash -c 'cd $DEPLOY_DIR && $DEPLOY_HOME/.local/bin/mise exec -- uv run repo-sync --dry-run -v'"
echo "  3. Check timer:    systemctl list-timers repo-sync.timer"
echo "  4. View logs:      tail -f $LOG_DIR/repo-sync.log"
echo "  5. Journal:        journalctl -u repo-sync.service -n 50"
echo ""
