"""Configuration loading and validation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import yaml


class Direction(Enum):
    PUSH = "push"
    PULL = "pull"
    BOTH = "both"


@dataclass(frozen=True)
class RepoConfig:
    path: Path
    direction: Direction
    branch: str = "main"
    remote: str = "origin"
    auto_commit: bool = True


@dataclass(frozen=True)
class Config:
    discord_webhook_url: str
    repos: list[RepoConfig]
    bot_username: str = "repo-sync"
    heartbeat_url: str = ""


def load_config(path: Path) -> Config:
    """Load and validate config from a YAML file."""
    with open(path) as f:
        raw = yaml.safe_load(f)

    if not isinstance(raw, dict):
        raise ValueError(f"Config file must be a YAML mapping: {path}")

    webhook_url = raw.get("discord_webhook_url", "")
    bot_username = raw.get("bot_username", "repo-sync")
    heartbeat_url = raw.get("heartbeat_url", "")
    repos: list[RepoConfig] = []

    for entry in raw.get("repos", []):
        repo_path = Path(entry["path"]).expanduser().resolve()
        direction = Direction(entry.get("direction", "both"))
        branch = entry.get("branch", "main")
        remote = entry.get("remote", "origin")
        auto_commit = entry.get("auto_commit", True)

        if not repo_path.is_dir():
            raise ValueError(f"Repository path does not exist: {repo_path}")
        if not (repo_path / ".git").exists():
            raise ValueError(f"Not a git repository: {repo_path}")

        repos.append(
            RepoConfig(
                path=repo_path,
                direction=direction,
                branch=branch,
                remote=remote,
                auto_commit=auto_commit,
            )
        )

    return Config(
        discord_webhook_url=webhook_url,
        repos=repos,
        bot_username=bot_username,
        heartbeat_url=heartbeat_url,
    )
