"""Weekly summary report sent to Discord via systemd timer."""

from __future__ import annotations

import subprocess
import sys
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

from discord_notify import DiscordWebhook, Embed
from discord_notify.webhook import COLOR_ERROR, COLOR_SUCCESS

from repo_sync.config import load_config

DEFAULT_CONFIG = Path("~/.config/repo-sync/config.yaml").expanduser()
DEFAULT_LOG_FILE = Path("/var/log/repo-sync/repo-sync.log")


def _get_log_lines(log_file: Path, since: datetime) -> list[str]:
    """Read lines from the log file that are newer than `since`."""
    if not log_file.exists():
        return []
    since_str = since.strftime("%Y-%m-%d")
    lines: list[str] = []
    with log_file.open() as f:
        for line in f:
            line = line.rstrip()
            if line[:4].isdigit() and line >= since_str:
                lines.append(line)
    return lines


def _get_journal_lines(since: str) -> list[str]:
    result = subprocess.run(
        ["journalctl", "-u", "repo-sync.service", "--since", since, "--no-pager"],
        capture_output=True,
        text=True,
    )
    return result.stdout.splitlines() if result.returncode == 0 else []


def _parse_stats(lines: list[str]) -> dict[str, int]:
    stats: Counter[str] = Counter()
    for line in lines:
        if "Result for" in line:
            stats["total"] += 1
            if "up-to-date" in line:
                stats["up_to_date"] += 1
            elif "pulled" in line:
                stats["pulled"] += 1
            elif "pushed" in line:
                stats["pushed"] += 1
            elif "rebased-and-pushed" in line:
                stats["rebased"] += 1
            elif "conflict" in line:
                stats["conflict"] += 1
            elif "error" in line:
                stats["error"] += 1
    return dict(stats)


def _count_runs(lines: list[str]) -> tuple[int, int]:
    """Count successful and failed service runs from journal lines."""
    successes = sum(1 for line in lines if "Finished" in line)
    failures = sum(
        1 for line in lines if "repo-sync.service: Failed with result" in line
    )
    return successes, failures


def main() -> int:
    config = load_config(DEFAULT_CONFIG)

    if not config.discord_webhook_url:
        print("No webhook URL configured, skipping summary")
        return 0

    webhook = DiscordWebhook(config.discord_webhook_url, username=config.bot_username)

    now = datetime.now()
    since_dt = now - timedelta(days=7)
    since_str = since_dt.strftime("%Y-%m-%d")

    log_lines = _get_log_lines(DEFAULT_LOG_FILE, since_dt)
    journal_lines = _get_journal_lines(since_str)

    stats = _parse_stats(log_lines)
    successes, failures = _count_runs(journal_lines)

    has_error = stats.get("conflict", 0) > 0 or stats.get("error", 0) > 0 or failures > 0
    color = COLOR_ERROR if has_error else COLOR_SUCCESS

    period_start = since_dt.strftime("%m/%d")
    period_end = now.strftime("%m/%d")

    embed = Embed(
        title="repo-sync weekly summary",
        color=color,
        description=f"Period: {period_start} - {period_end}",
    )
    embed.add_field("Service runs", f"{successes} ok / {failures} failed", inline=True)
    embed.add_field("Repos synced", str(stats.get("total", 0)), inline=True)

    details: list[str] = []
    if stats.get("pulled", 0):
        details.append(f"Pulled: {stats['pulled']}")
    if stats.get("pushed", 0):
        details.append(f"Pushed: {stats['pushed']}")
    if stats.get("rebased", 0):
        details.append(f"Rebased: {stats['rebased']}")
    if stats.get("conflict", 0):
        details.append(f"Conflicts: {stats['conflict']}")
    if stats.get("error", 0):
        details.append(f"Errors: {stats['error']}")

    if details:
        embed.add_field("Breakdown", "\n".join(details))

    if failures > 0:
        embed.add_field("Note", "Service failures detected — check `journalctl -u repo-sync`")

    webhook.send(embeds=[embed])
    print(f"Weekly summary sent ({period_start} - {period_end})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
