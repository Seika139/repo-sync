# Changelog

<!-- markdownlint-disable MD024 -->

このプロジェクトの注目すべき変更はこのファイルで文書化されています。

フォーマットは [Keep a Changelog](https://keepachangelog.com/ja/1.1.0/) に基づいており、
このプロジェクトは [セマンティック バージョニング](https://semver.org/lang/ja/spec/v2.0.0.html) を遵守しています。

## Tagged Releases

- [unreleased](https://github.com/Seika139/repo-sync/compare/v0.1.1...HEAD)
- [0.1.1](https://github.com/Seika139/repo-sync/compare/v0.1.0...v0.1.1)
- [0.1.0](https://github.com/Seika139/repo-sync/releases/tag/v0.1.0)

## [Unreleased]

### Added

- リポジトリ直下の `.repo-sync/pre-sync.sh` と `.repo-sync/post-sync.sh` を自動検知して実行する
  hook discovery 機能を追加する。`pre-sync.sh` は `git fetch` より前、`post-sync.sh` は sync
  成功時にリポジトリのルートで実行される。フックが非 0 で終了した場合は `error` として記録し、
  Discord に通知する。
- フックは 15 分 (`HOOK_TIMEOUT_SEC`) で強制終了する。shebang 不備などで exec 自体が失敗した
  場合も `OSError` を捕捉して `error` として通知する。フック出力は 4000 文字 (`MAX_HOOK_OUTPUT_CHARS`)
  で末尾からトランケートしてログする。
- 失敗時の Discord 通知タイトルをシナリオ別に分岐する (`Pre-sync hook failed`,
  `Post-sync hook failed`, `Auto-commit failed`)。従来は全て `Sync conflict detected` に
  固定されていた。

### Fixed

- `commit_all` が `git add -A` の結果を捨てていたため、nested git repo などで add が失敗すると
  stderr が空のまま「Commit failed: 」とだけログされる問題を修正する。add 失敗時はそのまま
  `GitResult` を伝播し、呼び出し側で Discord 通知まで行う。

## [0.1.1] - 2026-04-14

### Added

- mypy strict と `ty` による型チェックを導入する
- `types-PyYAML` を dev 依存として追加し、`pyyaml` の型情報を提供する
- `CHANGELOG.md` を追加し、Keep a Changelog 形式で変更履歴を管理する
- `update-version` reusable workflow を導入し、バージョン管理を自動化する

### Changed

- `discord-notify` の依存を `v0.1.0` から `v0.1.1` に更新する
- テスト関数に戻り値アノテーション `-> None` を追加する

## [0.1.0] - 2026-04-14

### Added

- `repo-sync` CLI を実装し、ローカル git リポジトリを GitHub リモートと同期可能にする
- `push` / `pull` / `both` の同期方向をリポジトリごとに指定可能にする
- `both` かつ branches が diverged している場合、`git rebase` を試行し、
  失敗時は `git rebase --abort` で元に戻した上で Discord に通知する
- `auto_commit` オプションで未コミット変更を自動コミット可能にする
- `discord-notify` と連携してコンフリクト発生時に Discord 通知を送信する
- `--dry-run` オプションで実際の変更を行わずに動作を確認可能にする
- YAML 設定ファイル (`~/.config/repo-sync/config.yaml`) から複数リポジトリを管理する
