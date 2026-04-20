"""config.yaml を検証して内容を表示する。"""

from __future__ import annotations

import sys
from pathlib import Path

from repo_sync.config import load_config


def main(config_path: str) -> None:
    path = Path(config_path)
    config = load_config(path)

    webhook_status = (
        "configured"
        if config.discord_webhook_url and "YOUR_" not in config.discord_webhook_url
        else "NOT configured"
    )
    print(f"  webhook: {webhook_status}")
    print(f"  bot_username: {config.bot_username}")
    print(f"  repos: {len(config.repos)}")
    for r in config.repos:
        print(f"    - {r.path} ({r.direction.value}, branch={r.branch})")
    print()
    print("Validation passed.")


if __name__ == "__main__":
    main(sys.argv[1])
