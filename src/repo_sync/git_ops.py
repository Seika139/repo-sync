"""Git operations via subprocess."""

from __future__ import annotations

import logging
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class RepoStatus(Enum):
    """Relationship between local HEAD and its upstream."""

    UP_TO_DATE = "up-to-date"
    AHEAD = "ahead"
    BEHIND = "behind"
    DIVERGED = "diverged"


@dataclass(frozen=True)
class GitResult:
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


# Stderr substrings indicating a retry-worthy transient failure
# (network flakes, server-side hiccups). Match is case-insensitive.
# Stable failures like "non-fast-forward" / "rejected" / merge conflicts
# are intentionally excluded — retrying them just delays the inevitable.
TRANSIENT_STDERR_PATTERNS: tuple[str, ...] = (
    "internal error performing authentication",  # GitHub auth flap
    "kex_exchange_identification",  # SSH handshake reset
    "connection reset by peer",
    "connection timed out",
    "operation timed out",
    "could not resolve hostname",
    "temporary failure in name resolution",
    "connection refused",
    "early eof",
    "the remote end hung up unexpectedly",
    "rpc failed; http 5",  # 5xx from GitHub
    "remote: error: 5",
    "bad gateway",
    "service unavailable",
)

MAX_NETWORK_ATTEMPTS = 3
# Backoff seconds between attempts N and N+1 (length must be MAX_NETWORK_ATTEMPTS - 1)
RETRY_BACKOFF_SECONDS: tuple[float, ...] = (1.0, 3.0)


def git(*args: str, cwd: Path) -> GitResult:
    """Run a git command and return the result."""
    cmd = ["git", *args]
    logger.debug("git %s (cwd=%s)", " ".join(args), cwd)
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)  # noqa: S603
    return GitResult(
        returncode=result.returncode,
        stdout=result.stdout.strip(),
        stderr=result.stderr.strip(),
    )


def _is_transient_error(stderr: str) -> bool:
    """Return True iff stderr suggests a retry-worthy transient failure."""
    lowered = stderr.lower()
    return any(p in lowered for p in TRANSIENT_STDERR_PATTERNS)


def _with_retry(op_name: str, fn: Callable[[], GitResult]) -> GitResult:
    """Run a git network op, retrying on transient errors with backoff."""
    result = fn()
    for attempt in range(1, MAX_NETWORK_ATTEMPTS):
        if result.ok or not _is_transient_error(result.stderr):
            return result
        delay = RETRY_BACKOFF_SECONDS[attempt - 1]
        first_line = result.stderr.splitlines()[0] if result.stderr else ""
        logger.info(
            "Transient error on %s (attempt %d/%d), retrying in %.1fs: %s",
            op_name,
            attempt,
            MAX_NETWORK_ATTEMPTS,
            delay,
            first_line,
        )
        time.sleep(delay)
        result = fn()
        if result.ok:
            logger.info("%s succeeded on attempt %d", op_name, attempt + 1)
    return result


def fetch(cwd: Path, remote: str = "origin") -> GitResult:
    return _with_retry("fetch", lambda: git("fetch", remote, cwd=cwd))


def has_uncommitted_changes(cwd: Path) -> bool:
    result = git("status", "--porcelain", cwd=cwd)
    return bool(result.stdout)


def commit_all(cwd: Path, message: str) -> GitResult:
    add_result = git("add", "-A", cwd=cwd)
    if not add_result.ok:
        return add_result
    return git("commit", "-m", message, cwd=cwd)


def get_current_branch(cwd: Path) -> str:
    """Return the current branch name, or empty string on failure."""
    result = git("rev-parse", "--abbrev-ref", "HEAD", cwd=cwd)
    return result.stdout if result.ok else ""


def get_repo_status(cwd: Path, remote: str = "origin", branch: str = "main") -> RepoStatus:
    """Compare local HEAD with its remote tracking branch."""
    local = git("rev-parse", "HEAD", cwd=cwd)
    remote_ref = f"{remote}/{branch}"
    remote_result = git("rev-parse", remote_ref, cwd=cwd)

    if not local.ok or not remote_result.ok:
        logger.warning("Could not resolve refs for %s", cwd)
        return RepoStatus.DIVERGED

    if local.stdout == remote_result.stdout:
        return RepoStatus.UP_TO_DATE

    base = git("merge-base", "HEAD", remote_ref, cwd=cwd)

    if local.stdout == base.stdout:
        return RepoStatus.BEHIND
    if remote_result.stdout == base.stdout:
        return RepoStatus.AHEAD
    return RepoStatus.DIVERGED


def pull_ff(cwd: Path) -> GitResult:
    return _with_retry("pull --ff-only", lambda: git("pull", "--ff-only", cwd=cwd))


def push(cwd: Path, remote: str = "origin", branch: str | None = None) -> GitResult:
    args = ["push", remote]
    if branch:
        args.append(branch)
    return _with_retry("push", lambda: git(*args, cwd=cwd))


def rebase(cwd: Path, remote: str = "origin", branch: str = "main") -> GitResult:
    return _with_retry("rebase", lambda: git("rebase", f"{remote}/{branch}", cwd=cwd))


def rebase_abort(cwd: Path) -> GitResult:
    return git("rebase", "--abort", cwd=cwd)
