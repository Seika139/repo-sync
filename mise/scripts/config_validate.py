"""config.yaml を検証して内容を表示する。"""

from __future__ import annotations

import os
import stat
import sys
from pathlib import Path

from repo_sync.config import load_config


def _check_permissions(path: Path) -> bool:
    """Check that the config file has 600 permissions."""
    mode = stat.S_IMODE(os.stat(path).st_mode)
    if mode != 0o600:
        print(
            f"  WARNING: permissions are {oct(mode)} (expected 0o600)",
            file=sys.stderr,
        )
        print("  -> Fix with: chmod 600 " + str(path), file=sys.stderr)
        return False
    print("  permissions: 600 (ok)")
    return True


def main(config_path: str) -> None:
    path = Path(config_path)
    config = load_config(path)

    _check_permissions(path)

    webhook_status = (
        "configured"
        if config.discord_webhook_url and "YOUR_" not in config.discord_webhook_url
        else "NOT configured"
    )
    print(f"  webhook: {webhook_status}")
    print(f"  bot_username: {config.bot_username}")
    if config.heartbeat_url:
        print(f"  heartbeat_url: {config.heartbeat_url}")
    print(f"  repos: {len(config.repos)}")
    for r in config.repos:
        print(f"    - {r.path} ({r.direction.value}, branch={r.branch})")
    print()
    print("Validation passed.")


if __name__ == "__main__":
    main(sys.argv[1])
