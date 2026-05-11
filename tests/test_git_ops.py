"""Tests for repo_sync.git_ops using real temporary git repos."""

import subprocess
from pathlib import Path

import pytest

from repo_sync import git_ops
from repo_sync.git_ops import (
    GitResult,
    RepoStatus,
    _is_transient_error,
    _with_retry,
    commit_all,
    get_current_branch,
    get_repo_status,
    has_uncommitted_changes,
)


def _run_git(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, capture_output=True, check=True)


@pytest.fixture
def git_pair(tmp_path: Path) -> tuple[Path, Path]:
    """Create a bare 'remote' repo and a cloned 'local' repo."""
    bare = tmp_path / "remote.git"
    bare.mkdir()
    _run_git("init", "--bare", "--initial-branch=main", cwd=bare)

    local = tmp_path / "local"
    _run_git("clone", str(bare), str(local), cwd=tmp_path)
    _run_git("config", "user.email", "test@test.com", cwd=local)
    _run_git("config", "user.name", "Test", cwd=local)

    # Create initial commit so main branch exists
    (local / "README.md").write_text("init")
    _run_git("add", ".", cwd=local)
    _run_git("commit", "-m", "initial", cwd=local)
    _run_git("push", "origin", "main", cwd=local)

    return local, bare


class TestHasUncommittedChanges:
    def test_clean(self, git_pair: tuple[Path, Path]) -> None:
        local, _ = git_pair
        assert has_uncommitted_changes(local) is False

    def test_with_new_file(self, git_pair: tuple[Path, Path]) -> None:
        local, _ = git_pair
        (local / "new.txt").write_text("hello")
        assert has_uncommitted_changes(local) is True

    def test_with_modified_file(self, git_pair: tuple[Path, Path]) -> None:
        local, _ = git_pair
        (local / "README.md").write_text("changed")
        assert has_uncommitted_changes(local) is True


class TestCommitAll:
    def test_commit(self, git_pair: tuple[Path, Path]) -> None:
        local, _ = git_pair
        (local / "file.txt").write_text("content")
        result = commit_all(local, "test commit")
        assert result.ok
        assert not has_uncommitted_changes(local)

    def test_returns_add_failure(self, git_pair: tuple[Path, Path]) -> None:
        """`git add -A` failure must propagate to the caller with stderr."""
        local, _ = git_pair
        # Nested git repo with no commits → `git add -A` fails with exit 128
        nested = local / "nested"
        nested.mkdir()
        _run_git("init", "--initial-branch=main", cwd=nested)

        result = commit_all(local, "test commit")
        assert not result.ok
        assert "nested" in result.stderr or "commit" in result.stderr.lower()


class TestGetCurrentBranch:
    def test_main(self, git_pair: tuple[Path, Path]) -> None:
        local, _ = git_pair
        assert get_current_branch(local) == "main"


class TestGetRepoStatus:
    def test_up_to_date(self, git_pair: tuple[Path, Path]) -> None:
        local, _ = git_pair
        assert get_repo_status(local) == RepoStatus.UP_TO_DATE

    def test_ahead(self, git_pair: tuple[Path, Path]) -> None:
        local, _ = git_pair
        (local / "new.txt").write_text("data")
        _run_git("add", ".", cwd=local)
        _run_git("commit", "-m", "local commit", cwd=local)
        assert get_repo_status(local) == RepoStatus.AHEAD

    def test_behind(self, git_pair: tuple[Path, Path]) -> None:
        local, bare = git_pair
        # Create another clone, commit and push
        other = bare.parent / "other"
        _run_git("clone", str(bare), str(other), cwd=bare.parent)
        _run_git("config", "user.email", "test@test.com", cwd=other)
        _run_git("config", "user.name", "Test", cwd=other)
        (other / "other.txt").write_text("data")
        _run_git("add", ".", cwd=other)
        _run_git("commit", "-m", "other commit", cwd=other)
        _run_git("push", "origin", "main", cwd=other)

        # Fetch in local
        _run_git("fetch", "origin", cwd=local)
        assert get_repo_status(local) == RepoStatus.BEHIND

    def test_diverged(self, git_pair: tuple[Path, Path]) -> None:
        local, bare = git_pair
        # Push from another clone
        other = bare.parent / "other"
        _run_git("clone", str(bare), str(other), cwd=bare.parent)
        _run_git("config", "user.email", "test@test.com", cwd=other)
        _run_git("config", "user.name", "Test", cwd=other)
        (other / "other.txt").write_text("data")
        _run_git("add", ".", cwd=other)
        _run_git("commit", "-m", "other commit", cwd=other)
        _run_git("push", "origin", "main", cwd=other)

        # Local also has a commit
        (local / "local.txt").write_text("data")
        _run_git("add", ".", cwd=local)
        _run_git("commit", "-m", "local commit", cwd=local)
        _run_git("fetch", "origin", cwd=local)

        assert get_repo_status(local) == RepoStatus.DIVERGED


class TestGitResult:
    def test_ok(self) -> None:
        assert GitResult(0, "out", "").ok is True
        assert GitResult(1, "", "err").ok is False


class TestIsTransientError:
    @pytest.mark.parametrize(
        "stderr",
        [
            "ERROR: internal error performing authentication",
            "kex_exchange_identification: Connection reset by peer",
            "ssh: connect to host github.com port 22: Connection timed out",
            "fatal: unable to access 'https://...': Could not resolve hostname github.com",
            "fatal: the remote end hung up unexpectedly",
            "fatal: early EOF",
            "remote: error: 502 Bad Gateway",
            "RPC failed; HTTP 503 curl 22",
        ],
    )
    def test_transient_patterns(self, stderr: str) -> None:
        assert _is_transient_error(stderr) is True

    @pytest.mark.parametrize(
        "stderr",
        [
            "",
            "fatal: refusing to merge unrelated histories",
            "error: failed to push some refs (non-fast-forward)",
            "Permission denied (publickey)",
            "CONFLICT (content): Merge conflict in README.md",
            "fatal: not a git repository",
        ],
    )
    def test_non_transient(self, stderr: str) -> None:
        assert _is_transient_error(stderr) is False


class TestWithRetry:
    @pytest.fixture(autouse=True)
    def _no_sleep(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("repo_sync.git_ops.time.sleep", lambda _s: None)

    def test_succeeds_immediately_no_retry(self) -> None:
        calls = [0]

        def fn() -> GitResult:
            calls[0] += 1
            return GitResult(0, "ok", "")

        result = _with_retry("fetch", fn)
        assert result.ok
        assert calls[0] == 1

    def test_recovers_on_second_attempt(self) -> None:
        calls = [0]

        def fn() -> GitResult:
            calls[0] += 1
            if calls[0] == 1:
                return GitResult(128, "", "ERROR: internal error performing authentication")
            return GitResult(0, "ok", "")

        result = _with_retry("fetch", fn)
        assert result.ok
        assert calls[0] == 2

    def test_exhausts_retries_on_persistent_transient(self) -> None:
        calls = [0]

        def fn() -> GitResult:
            calls[0] += 1
            return GitResult(128, "", "kex_exchange_identification: Connection reset by peer")

        result = _with_retry("fetch", fn)
        assert not result.ok
        assert calls[0] == git_ops.MAX_NETWORK_ATTEMPTS

    def test_no_retry_on_non_transient_error(self) -> None:
        calls = [0]

        def fn() -> GitResult:
            calls[0] += 1
            return GitResult(1, "", "error: failed to push some refs (non-fast-forward)")

        result = _with_retry("push", fn)
        assert not result.ok
        assert calls[0] == 1
