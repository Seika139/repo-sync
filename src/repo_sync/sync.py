"""Core synchronization logic."""

from __future__ import annotations

import logging
import urllib.error
import urllib.request
from datetime import datetime
from enum import Enum

from discord_notify import DiscordWebhook, Embed
from discord_notify.webhook import COLOR_ERROR, COLOR_SUCCESS, COLOR_WARNING

from repo_sync.config import Config, Direction, RepoConfig
from repo_sync.git_ops import (
    RepoStatus,
    commit_all,
    fetch,
    get_current_branch,
    get_repo_status,
    has_uncommitted_changes,
    pull_ff,
    push,
    rebase,
    rebase_abort,
)

logger = logging.getLogger(__name__)


class SyncResult(Enum):
    UP_TO_DATE = "up-to-date"
    PULLED = "pulled"
    PUSHED = "pushed"
    REBASED_AND_PUSHED = "rebased-and-pushed"
    CONFLICT = "conflict"
    ERROR = "error"


def _send_webhook(webhook: DiscordWebhook, embeds: list[Embed]) -> None:
    """Send webhook with error handling. Never raises."""
    try:
        webhook.send(embeds=embeds)
    except urllib.error.HTTPError as e:
        logger.error("Discord webhook failed: %s %s — check webhook URL", e.code, e.reason)
    except Exception as e:
        logger.error("Discord webhook failed: %s", e)


def _notify_conflict(
    webhook: DiscordWebhook | None,
    repo: RepoConfig,
    reason: str,
) -> None:
    if webhook is None:
        return
    embed = Embed(
        title="Sync conflict detected",
        color=COLOR_ERROR,
    )
    embed.add_field("Repository", str(repo.path), inline=True)
    embed.add_field("Branch", repo.branch, inline=True)
    embed.add_field("Direction", repo.direction.value, inline=True)
    embed.add_field("Reason", reason)
    _send_webhook(webhook, [embed])


def _notify_summary(
    webhook: DiscordWebhook | None,
    results: list[tuple[RepoConfig, SyncResult]],
) -> None:
    """Send a summary of all sync results when there's at least one notable action."""
    if webhook is None:
        return
    notable = [(r, s) for r, s in results if s not in (SyncResult.UP_TO_DATE,)]
    if not notable:
        return

    has_error = any(s in (SyncResult.CONFLICT, SyncResult.ERROR) for _, s in notable)
    color = COLOR_WARNING if has_error else COLOR_SUCCESS

    embed = Embed(
        title="repo-sync completed",
        color=color,
        description=f"Synced {len(results)} repositories at {datetime.now():%Y-%m-%d %H:%M}",
    )
    for repo, result in notable:
        embed.add_field(str(repo.path), result.value, inline=True)
    _send_webhook(webhook, [embed])


def sync_repo(
    repo: RepoConfig,
    webhook: DiscordWebhook | None,
    *,
    dry_run: bool = False,
) -> SyncResult:
    """Synchronize a single repository. Returns the outcome."""
    logger.info("Syncing %s (direction=%s)", repo.path, repo.direction.value)

    # 0. Skip if not on the expected branch
    current_branch = get_current_branch(repo.path)
    if current_branch and current_branch != repo.branch:
        logger.info(
            "Skipping %s: on branch '%s' (expected '%s')", repo.path, current_branch, repo.branch
        )
        return SyncResult.UP_TO_DATE

    # 1. Fetch remote
    fetch_result = fetch(repo.path, repo.remote)
    if not fetch_result.ok:
        logger.error("Fetch failed for %s: %s", repo.path, fetch_result.stderr)
        _notify_conflict(webhook, repo, f"git fetch failed: {fetch_result.stderr}")
        return SyncResult.ERROR

    # 2. Commit uncommitted changes if applicable
    if repo.auto_commit and repo.direction in (Direction.PUSH, Direction.BOTH):
        if has_uncommitted_changes(repo.path):
            msg = f"auto-sync: {datetime.now():%Y-%m-%d_%H:%M}"
            logger.info("Auto-committing in %s", repo.path)
            if not dry_run:
                commit_result = commit_all(repo.path, msg)
                if not commit_result.ok:
                    logger.error("Commit failed: %s", commit_result.stderr)
                    return SyncResult.ERROR

    # 3. Determine status
    status = get_repo_status(repo.path, repo.remote, repo.branch)
    logger.info("Status for %s: %s", repo.path, status.value)

    if status == RepoStatus.UP_TO_DATE:
        return SyncResult.UP_TO_DATE

    # 4. Act based on direction
    if repo.direction == Direction.PULL:
        return _sync_pull(repo, status, webhook, dry_run=dry_run)
    elif repo.direction == Direction.PUSH:
        return _sync_push(repo, status, webhook, dry_run=dry_run)
    else:
        return _sync_both(repo, status, webhook, dry_run=dry_run)


def _sync_pull(
    repo: RepoConfig,
    status: RepoStatus,
    webhook: DiscordWebhook | None,
    *,
    dry_run: bool,
) -> SyncResult:
    if status == RepoStatus.BEHIND:
        if not dry_run:
            result = pull_ff(repo.path)
            if not result.ok:
                _notify_conflict(webhook, repo, f"pull --ff-only failed: {result.stderr}")
                return SyncResult.CONFLICT
        return SyncResult.PULLED

    reason = (
        "Local has unpushed commits" if status == RepoStatus.AHEAD else "Branches have diverged"
    )
    _notify_conflict(webhook, repo, reason)
    return SyncResult.CONFLICT


def _sync_push(
    repo: RepoConfig,
    status: RepoStatus,
    webhook: DiscordWebhook | None,
    *,
    dry_run: bool,
) -> SyncResult:
    if status == RepoStatus.AHEAD:
        if not dry_run:
            result = push(repo.path, repo.remote, repo.branch)
            if not result.ok:
                _notify_conflict(webhook, repo, f"git push failed: {result.stderr}")
                return SyncResult.CONFLICT
        return SyncResult.PUSHED

    reason = "Remote has new commits" if status == RepoStatus.BEHIND else "Branches have diverged"
    _notify_conflict(webhook, repo, reason)
    return SyncResult.CONFLICT


def _sync_both(
    repo: RepoConfig,
    status: RepoStatus,
    webhook: DiscordWebhook | None,
    *,
    dry_run: bool,
) -> SyncResult:
    if status == RepoStatus.BEHIND:
        if not dry_run:
            result = pull_ff(repo.path)
            if not result.ok:
                _notify_conflict(webhook, repo, f"pull --ff-only failed: {result.stderr}")
                return SyncResult.CONFLICT
        return SyncResult.PULLED

    if status == RepoStatus.AHEAD:
        if not dry_run:
            result = push(repo.path, repo.remote, repo.branch)
            if not result.ok:
                _notify_conflict(webhook, repo, f"git push failed: {result.stderr}")
                return SyncResult.CONFLICT
        return SyncResult.PUSHED

    # DIVERGED: try rebase
    if dry_run:
        logger.info("Dry-run: would attempt rebase for %s", repo.path)
        return SyncResult.REBASED_AND_PUSHED

    rebase_result = rebase(repo.path, repo.remote, repo.branch)
    if rebase_result.ok:
        push_result = push(repo.path, repo.remote, repo.branch)
        if push_result.ok:
            return SyncResult.REBASED_AND_PUSHED
        _notify_conflict(webhook, repo, f"Push after rebase failed: {push_result.stderr}")
        return SyncResult.CONFLICT

    # Rebase failed — abort and notify
    logger.warning("Rebase failed for %s, aborting", repo.path)
    rebase_abort(repo.path)
    _notify_conflict(
        webhook,
        repo,
        f"Rebase conflict — manual resolution required:\n```\n{rebase_result.stderr}\n```",
    )
    return SyncResult.CONFLICT


def _ping_heartbeat(url: str) -> None:
    """Send a GET request to the heartbeat URL (best-effort, no exception on failure)."""
    try:
        urllib.request.urlopen(url, timeout=10)  # noqa: S310
        logger.info("Heartbeat pinged: %s", url)
    except Exception:
        logger.warning("Heartbeat ping failed: %s", url)


def run_sync(config: Config, *, dry_run: bool = False) -> list[tuple[RepoConfig, SyncResult]]:
    """Synchronize all configured repositories."""
    webhook: DiscordWebhook | None = None
    if config.discord_webhook_url:
        webhook = DiscordWebhook(config.discord_webhook_url, username=config.bot_username)

    results: list[tuple[RepoConfig, SyncResult]] = []
    for repo in config.repos:
        result = sync_repo(repo, webhook, dry_run=dry_run)
        results.append((repo, result))
        logger.info("Result for %s: %s", repo.path, result.value)

    _notify_summary(webhook, results)

    has_failures = any(r in (SyncResult.CONFLICT, SyncResult.ERROR) for _, r in results)
    if config.heartbeat_url and not has_failures and not dry_run:
        _ping_heartbeat(config.heartbeat_url)

    return results
