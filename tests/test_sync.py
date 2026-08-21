"""Tests for repo_sync.sync using real temporary git repos."""

import subprocess
from pathlib import Path

import pytest
from discord_notify import DiscordWebhook, Embed

from repo_sync.config import Direction, RepoConfig
from repo_sync.sync import SyncResult, sync_repo


def _run_git(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, capture_output=True, check=True)


@pytest.fixture
def git_pair(tmp_path: Path) -> tuple[Path, Path]:
    """Create a bare 'remote' and cloned 'local' with one initial commit."""
    bare = tmp_path / "remote.git"
    bare.mkdir()
    _run_git("init", "--bare", "--initial-branch=main", cwd=bare)

    local = tmp_path / "local"
    _run_git("clone", str(bare), str(local), cwd=tmp_path)
    _run_git("config", "user.email", "test@test.com", cwd=local)
    _run_git("config", "user.name", "Test", cwd=local)

    (local / "README.md").write_text("init")
    _run_git("add", ".", cwd=local)
    _run_git("commit", "-m", "initial", cwd=local)
    _run_git("push", "origin", "main", cwd=local)

    return local, bare


def _make_other_clone(bare: Path) -> Path:
    other = bare.parent / "other"
    _run_git("clone", str(bare), str(other), cwd=bare.parent)
    _run_git("config", "user.email", "test@test.com", cwd=other)
    _run_git("config", "user.name", "Test", cwd=other)
    return other


def _make_repo_config(path: Path, direction: Direction) -> RepoConfig:
    return RepoConfig(path=path, direction=direction, branch="main")


class FakeWebhook(DiscordWebhook):
    """Records embeds sent via `_send_webhook` without hitting the network."""

    def __init__(self) -> None:
        super().__init__("https://example.com/webhook")
        self.sent_embeds: list[Embed] = []

    def send(
        self,
        content: str = "",
        embeds: list[Embed] | None = None,
        *,
        dry_run: bool = False,
    ) -> list[int]:
        self.sent_embeds.extend(embeds or [])
        return []


class TestSyncPull:
    def test_up_to_date(self, git_pair: tuple[Path, Path]) -> None:
        local, _ = git_pair
        repo = _make_repo_config(local, Direction.PULL)
        assert sync_repo(repo, webhook=None) == SyncResult.UP_TO_DATE

    def test_behind_pulls(self, git_pair: tuple[Path, Path]) -> None:
        local, bare = git_pair
        other = _make_other_clone(bare)
        (other / "new.txt").write_text("data")
        _run_git("add", ".", cwd=other)
        _run_git("commit", "-m", "new", cwd=other)
        _run_git("push", "origin", "main", cwd=other)

        repo = _make_repo_config(local, Direction.PULL)
        assert sync_repo(repo, webhook=None) == SyncResult.PULLED
        assert (local / "new.txt").exists()

    def test_ahead_reports_conflict(self, git_pair: tuple[Path, Path]) -> None:
        local, _ = git_pair
        (local / "local.txt").write_text("data")
        _run_git("add", ".", cwd=local)
        _run_git("commit", "-m", "local", cwd=local)

        repo = _make_repo_config(local, Direction.PULL)
        assert sync_repo(repo, webhook=None) == SyncResult.CONFLICT


class TestSyncPush:
    def test_up_to_date(self, git_pair: tuple[Path, Path]) -> None:
        local, _ = git_pair
        repo = _make_repo_config(local, Direction.PUSH)
        assert sync_repo(repo, webhook=None) == SyncResult.UP_TO_DATE

    def test_uncommitted_changes_auto_commit_and_push(self, git_pair: tuple[Path, Path]) -> None:
        local, _ = git_pair
        (local / "new.txt").write_text("data")

        repo = _make_repo_config(local, Direction.PUSH)
        assert sync_repo(repo, webhook=None) == SyncResult.PUSHED

    def test_ahead_pushes(self, git_pair: tuple[Path, Path]) -> None:
        local, _ = git_pair
        (local / "new.txt").write_text("data")
        _run_git("add", ".", cwd=local)
        _run_git("commit", "-m", "local", cwd=local)

        repo = _make_repo_config(local, Direction.PUSH)
        assert sync_repo(repo, webhook=None) == SyncResult.PUSHED


class TestSyncBoth:
    def test_behind_pulls(self, git_pair: tuple[Path, Path]) -> None:
        local, bare = git_pair
        other = _make_other_clone(bare)
        (other / "new.txt").write_text("data")
        _run_git("add", ".", cwd=other)
        _run_git("commit", "-m", "new", cwd=other)
        _run_git("push", "origin", "main", cwd=other)

        repo = _make_repo_config(local, Direction.BOTH)
        assert sync_repo(repo, webhook=None) == SyncResult.PULLED

    def test_ahead_pushes(self, git_pair: tuple[Path, Path]) -> None:
        local, _ = git_pair
        (local / "new.txt").write_text("data")
        _run_git("add", ".", cwd=local)
        _run_git("commit", "-m", "local", cwd=local)

        repo = _make_repo_config(local, Direction.BOTH)
        assert sync_repo(repo, webhook=None) == SyncResult.PUSHED

    def test_diverged_rebase_success(self, git_pair: tuple[Path, Path]) -> None:
        local, bare = git_pair
        # Remote gets a new commit
        other = _make_other_clone(bare)
        (other / "remote.txt").write_text("remote data")
        _run_git("add", ".", cwd=other)
        _run_git("commit", "-m", "remote", cwd=other)
        _run_git("push", "origin", "main", cwd=other)

        # Local gets a non-conflicting commit
        (local / "local.txt").write_text("local data")
        _run_git("add", ".", cwd=local)
        _run_git("commit", "-m", "local", cwd=local)

        repo = _make_repo_config(local, Direction.BOTH)
        assert sync_repo(repo, webhook=None) == SyncResult.REBASED_AND_PUSHED

    def test_diverged_rebase_conflict(self, git_pair: tuple[Path, Path]) -> None:
        local, bare = git_pair
        # Remote modifies README
        other = _make_other_clone(bare)
        (other / "README.md").write_text("remote version")
        _run_git("add", ".", cwd=other)
        _run_git("commit", "-m", "remote", cwd=other)
        _run_git("push", "origin", "main", cwd=other)

        # Local also modifies README (conflict!)
        (local / "README.md").write_text("local version")
        _run_git("add", ".", cwd=local)
        _run_git("commit", "-m", "local", cwd=local)

        repo = _make_repo_config(local, Direction.BOTH)
        assert sync_repo(repo, webhook=None) == SyncResult.CONFLICT


class TestDryRun:
    def test_dry_run_does_not_push(self, git_pair: tuple[Path, Path]) -> None:
        local, bare = git_pair
        (local / "new.txt").write_text("data")
        _run_git("add", ".", cwd=local)
        _run_git("commit", "-m", "local", cwd=local)

        repo = _make_repo_config(local, Direction.PUSH)
        assert sync_repo(repo, webhook=None, dry_run=True) == SyncResult.PUSHED

        # Verify nothing was actually pushed
        other = _make_other_clone(bare)
        assert not (other / "new.txt").exists()


def _install_hook(repo: Path, phase: str, body: str, *, executable: bool = True) -> Path:
    """Install a `.repo-sync/{phase}-sync.sh` hook and commit it.

    Committing avoids false positives where an uncommitted hook would itself
    trigger an auto-commit + push during sync.
    """
    hook_dir = repo / ".repo-sync"
    hook_dir.mkdir(exist_ok=True)
    hook = hook_dir / f"{phase}-sync.sh"
    hook.write_text(f"#!/usr/bin/env bash\nset -euo pipefail\n{body}\n")
    if executable:
        hook.chmod(0o755)
    _run_git("add", ".repo-sync", cwd=repo)
    _run_git("commit", "-m", f"add {phase}-sync hook", cwd=repo)
    _run_git("push", "origin", "main", cwd=repo)
    return hook


class TestHooks:
    def test_post_sync_runs_on_pull(self, git_pair: tuple[Path, Path]) -> None:
        local, bare = git_pair
        marker = local / ".post-sync-ran"
        _install_hook(local, "post", f'touch "{marker}"')

        # Make origin ahead of local by pushing from another clone
        other = _make_other_clone(bare)
        (other / "new.txt").write_text("data")
        _run_git("add", ".", cwd=other)
        _run_git("commit", "-m", "new", cwd=other)
        _run_git("push", "origin", "main", cwd=other)

        repo = _make_repo_config(local, Direction.PULL)
        assert sync_repo(repo, webhook=None) == SyncResult.PULLED
        assert marker.exists()

    def test_post_sync_runs_on_up_to_date(self, git_pair: tuple[Path, Path]) -> None:
        local, _ = git_pair
        marker = local / ".post-sync-ran"
        _install_hook(local, "post", f'touch "{marker}"')

        repo = _make_repo_config(local, Direction.BOTH)
        assert sync_repo(repo, webhook=None) == SyncResult.UP_TO_DATE
        assert marker.exists()

    def test_post_sync_skipped_on_conflict(self, git_pair: tuple[Path, Path]) -> None:
        local, _ = git_pair
        marker = local / ".post-sync-ran"
        _install_hook(local, "post", f'touch "{marker}"')

        # Make local ahead of origin (without pushing)
        (local / "local.txt").write_text("data")
        _run_git("add", ".", cwd=local)
        _run_git("commit", "-m", "local", cwd=local)

        # PULL + AHEAD → CONFLICT → hook must not run
        repo = _make_repo_config(local, Direction.PULL)
        assert sync_repo(repo, webhook=None) == SyncResult.CONFLICT
        assert not marker.exists()

    def test_pre_sync_runs_before_auto_commit(self, git_pair: tuple[Path, Path]) -> None:
        """Files created by pre-sync must be picked up by auto-commit and pushed."""
        local, bare = git_pair
        generated = local / "generated.txt"
        _install_hook(local, "pre", f'echo pre > "{generated}"')

        repo = _make_repo_config(local, Direction.PUSH)
        assert sync_repo(repo, webhook=None) == SyncResult.PUSHED

        other = _make_other_clone(bare)
        assert (other / "generated.txt").exists()

    def test_pre_sync_failure_aborts(self, git_pair: tuple[Path, Path]) -> None:
        local, _ = git_pair
        _install_hook(local, "pre", "exit 1")

        repo = _make_repo_config(local, Direction.BOTH)
        assert sync_repo(repo, webhook=None) == SyncResult.ERROR

    def test_post_sync_failure_returns_error(self, git_pair: tuple[Path, Path]) -> None:
        local, _ = git_pair
        _install_hook(local, "post", "exit 1")

        repo = _make_repo_config(local, Direction.BOTH)
        assert sync_repo(repo, webhook=None) == SyncResult.ERROR

    def test_non_executable_hook_is_skipped(self, git_pair: tuple[Path, Path]) -> None:
        local, _ = git_pair
        # Hook exists but is not chmod +x → should be skipped, not fail
        _install_hook(local, "post", "exit 1", executable=False)

        repo = _make_repo_config(local, Direction.BOTH)
        assert sync_repo(repo, webhook=None) == SyncResult.UP_TO_DATE

    def test_dry_run_skips_hooks(self, git_pair: tuple[Path, Path]) -> None:
        local, _ = git_pair
        marker = local / ".post-sync-ran"
        _install_hook(local, "post", f'touch "{marker}"')

        repo = _make_repo_config(local, Direction.BOTH)
        sync_repo(repo, webhook=None, dry_run=True)
        assert not marker.exists()

    def test_hook_not_run_on_wrong_branch(self, git_pair: tuple[Path, Path]) -> None:
        local, _ = git_pair
        _run_git("checkout", "-b", "feature", cwd=local)

        marker = local / ".pre-sync-ran"
        _install_hook(local, "pre", f'touch "{marker}"')

        repo = _make_repo_config(local, Direction.BOTH)
        assert sync_repo(repo, webhook=None) == SyncResult.UP_TO_DATE
        assert not marker.exists()

    def test_hook_with_bad_shebang_returns_error(self, git_pair: tuple[Path, Path]) -> None:
        """Hook that can't be exec'd (bad shebang) must fail gracefully."""
        local, _ = git_pair
        hook_dir = local / ".repo-sync"
        hook_dir.mkdir()
        hook = hook_dir / "pre-sync.sh"
        hook.write_text("#!/nonexistent/interpreter\necho hello\n")
        hook.chmod(0o755)
        _run_git("add", ".repo-sync", cwd=local)
        _run_git("commit", "-m", "add bad hook", cwd=local)
        _run_git("push", "origin", "main", cwd=local)

        repo = _make_repo_config(local, Direction.BOTH)
        assert sync_repo(repo, webhook=None) == SyncResult.ERROR

    def test_hook_timeout_returns_error(
        self,
        git_pair: tuple[Path, Path],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A hanging hook must be killed by the timeout and reported as error."""
        import repo_sync.sync as sync_mod

        monkeypatch.setattr(sync_mod, "HOOK_TIMEOUT_SEC", 1)

        local, _ = git_pair
        _install_hook(local, "pre", "sleep 30")

        repo = _make_repo_config(local, Direction.BOTH)
        assert sync_repo(repo, webhook=None) == SyncResult.ERROR


class TestNotificationTitles:
    """Failure notifications must carry titles that reflect the actual failure,
    not a generic "conflict" label (see issue #38)."""

    def test_fetch_failure_notifies_with_fetch_failed_title(
        self, git_pair: tuple[Path, Path]
    ) -> None:
        local, _ = git_pair
        # An unconfigured remote name makes `git fetch` fail immediately, without
        # any real network activity, and it is not a conflict of any kind.
        repo = RepoConfig(
            path=local, direction=Direction.PULL, branch="main", remote="no-such-remote"
        )

        webhook = FakeWebhook()
        assert sync_repo(repo, webhook=webhook) == SyncResult.ERROR

        assert len(webhook.sent_embeds) == 1
        assert webhook.sent_embeds[0].title == "Fetch failed"

    def test_rebase_conflict_notifies_with_conflict_title(
        self, git_pair: tuple[Path, Path]
    ) -> None:
        local, bare = git_pair
        # Remote modifies README
        other = _make_other_clone(bare)
        (other / "README.md").write_text("remote version")
        _run_git("add", ".", cwd=other)
        _run_git("commit", "-m", "remote", cwd=other)
        _run_git("push", "origin", "main", cwd=other)

        # Local also modifies README (real rebase conflict!)
        (local / "README.md").write_text("local version")
        _run_git("add", ".", cwd=local)
        _run_git("commit", "-m", "local", cwd=local)

        repo = _make_repo_config(local, Direction.BOTH)
        webhook = FakeWebhook()
        assert sync_repo(repo, webhook=webhook) == SyncResult.CONFLICT

        assert len(webhook.sent_embeds) == 1
        assert "conflict" in webhook.sent_embeds[0].title.lower()

    def test_rebase_non_conflict_failure_notifies_with_rebase_failed_title(
        self, git_pair: tuple[Path, Path]
    ) -> None:
        local, bare = git_pair
        # Remote modifies README (diverges history so a rebase is attempted)
        other = _make_other_clone(bare)
        (other / "README.md").write_text("remote version")
        _run_git("add", ".", cwd=other)
        _run_git("commit", "-m", "remote", cwd=other)
        _run_git("push", "origin", "main", cwd=other)

        # Local commits a change to a different file so histories diverge
        # without a real content conflict on rebase.
        (local / "local.txt").write_text("data")
        _run_git("add", ".", cwd=local)
        _run_git("commit", "-m", "local", cwd=local)

        # Local also has unstaged changes, which blocks `git rebase` outright
        # with "cannot rebase: You have unstaged changes" — not a conflict.
        (local / "local.txt").write_text("dirty")

        repo = RepoConfig(path=local, direction=Direction.BOTH, branch="main", auto_commit=False)
        webhook = FakeWebhook()
        assert sync_repo(repo, webhook=webhook) == SyncResult.CONFLICT

        assert len(webhook.sent_embeds) == 1
        title = webhook.sent_embeds[0].title
        assert title == "Rebase failed"
        assert "conflict" not in title.lower()


class TestIsRebaseConflict:
    def test_unrelated_stderr_mentioning_conflict_is_not_a_conflict(self) -> None:
        from repo_sync.git_ops import GitResult
        from repo_sync.sync import _is_rebase_conflict

        result = GitResult(
            returncode=128,
            stdout="",
            stderr="fatal: invalid upstream 'conflict/main'",
        )
        assert _is_rebase_conflict(result) is False

    def test_real_conflict_diagnostic_is_a_conflict(self) -> None:
        from repo_sync.git_ops import GitResult
        from repo_sync.sync import _is_rebase_conflict

        result = GitResult(
            returncode=1,
            stdout="CONFLICT (content): Merge conflict in README.md",
            stderr="",
        )
        assert _is_rebase_conflict(result) is True


class TestTrimHookOutput:
    def test_short_unchanged(self) -> None:
        from repo_sync.sync import _trim_hook_output

        assert _trim_hook_output("hello") == "hello"
        assert _trim_hook_output("  spaced  ") == "spaced"

    def test_long_truncated_to_tail(self) -> None:
        from repo_sync.sync import MAX_HOOK_OUTPUT_CHARS, _trim_hook_output

        out = "x" * (MAX_HOOK_OUTPUT_CHARS + 500)
        trimmed = _trim_hook_output(out)
        assert trimmed.startswith("... (truncated)")
        # The tail (not the head) is preserved so the most recent stderr wins
        assert trimmed.endswith("x" * 100)
        assert len(trimmed) <= MAX_HOOK_OUTPUT_CHARS + len("... (truncated)\n")
