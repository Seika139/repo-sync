"""CLI entry point for repo-sync."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from repo_sync.config import load_config
from repo_sync.sync import SyncResult, run_sync

DEFAULT_CONFIG = Path("~/.config/repo-sync/config.yaml").expanduser()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="repo-sync",
        description="Sync local git repositories with their GitHub remotes.",
    )
    parser.add_argument(
        "-c",
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help=f"Path to config file (default: {DEFAULT_CONFIG})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable debug logging",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger = logging.getLogger("repo_sync")

    config_path: Path = args.config
    if not config_path.exists():
        logger.error("Config file not found: %s", config_path)
        return 1

    try:
        config = load_config(config_path)
    except (ValueError, Exception) as e:
        logger.error("Failed to load config: %s", e)
        return 1

    if args.dry_run:
        logger.info("Running in dry-run mode")

    results = run_sync(config, dry_run=args.dry_run)

    has_failures = any(result in (SyncResult.CONFLICT, SyncResult.ERROR) for _, result in results)
    return 1 if has_failures else 0


if __name__ == "__main__":
    sys.exit(main())
