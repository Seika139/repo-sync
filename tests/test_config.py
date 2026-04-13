"""Tests for repo_sync.config."""

import textwrap
from pathlib import Path

import pytest

from repo_sync.config import Config, Direction, load_config


@pytest.fixture
def config_file(tmp_path: Path) -> Path:
    """Create a valid config file with a real git repo."""
    repo = tmp_path / "my-repo"
    repo.mkdir()
    (repo / ".git").mkdir()

    config = tmp_path / "config.yaml"
    config.write_text(
        textwrap.dedent(f"""\
        discord_webhook_url: "https://discord.com/api/webhooks/test/test"
        bot_username: "test-bot"
        repos:
          - path: {repo}
            direction: push
            branch: main
          - path: {repo}
            direction: pull
            branch: develop
            remote: upstream
            auto_commit: false
        """)
    )
    return config


def test_load_config(config_file: Path):
    config = load_config(config_file)
    assert isinstance(config, Config)
    assert config.discord_webhook_url == "https://discord.com/api/webhooks/test/test"
    assert config.bot_username == "test-bot"
    assert len(config.repos) == 2


def test_load_config_repo_fields(config_file: Path):
    config = load_config(config_file)
    repo = config.repos[0]
    assert repo.direction == Direction.PUSH
    assert repo.branch == "main"
    assert repo.remote == "origin"
    assert repo.auto_commit is True

    repo2 = config.repos[1]
    assert repo2.direction == Direction.PULL
    assert repo2.branch == "develop"
    assert repo2.remote == "upstream"
    assert repo2.auto_commit is False


def test_load_config_invalid_path(tmp_path: Path):
    config = tmp_path / "config.yaml"
    config.write_text(
        textwrap.dedent("""\
        discord_webhook_url: ""
        repos:
          - path: /nonexistent/path/abc123
            direction: push
        """)
    )
    with pytest.raises(ValueError, match="does not exist"):
        load_config(config)


def test_load_config_not_git_repo(tmp_path: Path):
    repo = tmp_path / "not-a-repo"
    repo.mkdir()
    config = tmp_path / "config.yaml"
    config.write_text(
        textwrap.dedent(f"""\
        discord_webhook_url: ""
        repos:
          - path: {repo}
            direction: push
        """)
    )
    with pytest.raises(ValueError, match="Not a git repository"):
        load_config(config)
