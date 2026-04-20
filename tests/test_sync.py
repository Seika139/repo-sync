"""Tests for repo_sync.sync using real temporary git repos."""

import subprocess
from pathlib import Path

import pytest

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
