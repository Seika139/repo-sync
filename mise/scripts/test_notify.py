"""Discord にテスト通知を送信する。"""

from __future__ import annotations

import sys
from pathlib import Path

from discord_notify import DiscordWebhook, Embed
from discord_notify.webhook import COLOR_SUCCESS
from repo_sync.config import load_config


def main(config_path: str) -> None:
    config = load_config(Path(config_path))
    if not config.discord_webhook_url or "YOUR_" in config.discord_webhook_url:
        print("ERROR: discord_webhook_url is not configured", file=sys.stderr)
        raise SystemExit(1)

    webhook = DiscordWebhook(
        url=config.discord_webhook_url, username=config.bot_username
    )
    embed = Embed(
        title="repo-sync test notification",
        description="If you see this, Discord notification is working correctly.",
        color=COLOR_SUCCESS,
    )
    webhook.send(embeds=[embed])
    print("Test notification sent successfully.")


if __name__ == "__main__":
    main(sys.argv[1])
