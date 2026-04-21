"""Git operations via subprocess."""

from __future__ import annotations

import logging
import subprocess
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


def fetch(cwd: Path, remote: str = "origin") -> GitResult:
    return git("fetch", remote, cwd=cwd)


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
    return git("pull", "--ff-only", cwd=cwd)


def push(cwd: Path, remote: str = "origin", branch: str | None = None) -> GitResult:
    args = ["push", remote]
    if branch:
        args.append(branch)
    return git(*args, cwd=cwd)


def rebase(cwd: Path, remote: str = "origin", branch: str = "main") -> GitResult:
    return git("rebase", f"{remote}/{branch}", cwd=cwd)


def rebase_abort(cwd: Path) -> GitResult:
    return git("rebase", "--abort", cwd=cwd)
