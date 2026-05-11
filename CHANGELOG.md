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

- Ubuntu サーバ向けインストーラ `install.sh` を追加する。systemd unit / timer、logrotate、ログディレクトリ、journal 読み取り権限のセットアップを 1 コマンドで完了する ([#2](https://github.com/Seika139/repo-sync/pull/2))。
- 失敗通知ユニット `repo-sync-notify-failure.service` を追加する。systemd の `OnFailure=` 経由で Python 起動前のクラッシュも含めて検知し、curl で Discord webhook に通知する ([#2](https://github.com/Seika139/repo-sync/pull/2))。
- 週次サマリー機能を追加する。`repo-sync-summary.timer` が月曜 12:00 に直近 1 週間の sync 結果を集計し Discord に送信する ([#2](https://github.com/Seika139/repo-sync/pull/2))。
- Heartbeat URL (`heartbeat_url`) 設定を追加する。全リポジトリの sync 成功時に指定 URL を ping する (UptimeKuma / healthchecks.io 等を想定) ([#2](https://github.com/Seika139/repo-sync/pull/2))。
- リポジトリ直下の `.repo-sync/pre-sync.sh` と `.repo-sync/post-sync.sh` を自動検知して実行する hook discovery 機能を追加する。`pre-sync.sh` は `git fetch` より前、`post-sync.sh` は sync 成功時にリポジトリのルートで実行される。フックは 15 分 (`HOOK_TIMEOUT_SEC`) で強制終了し、出力は 4000 文字 (`MAX_HOOK_OUTPUT_CHARS`) で末尾からトランケートしてログする。shebang 不備などで exec 自体が失敗した場合も `OSError` を捕捉して `error` として通知する ([#13](https://github.com/Seika139/repo-sync/pull/13))。
- ネットワーク系 git 操作 (`fetch` / `pull` / `push` / `rebase`) に対する一過性エラーの自動リトライを追加する。GitHub の `internal error performing authentication` や SSH ハンドシェイクのリセット、5xx、DNS 一時障害などを `TRANSIENT_STDERR_PATTERNS` で検出し、最大 3 回 (バックオフ 1s, 3s) で再試行する。`non-fast-forward` / `rejected` / merge conflict など本質的な失敗はリトライ対象外。
- 失敗時の Discord 通知タイトルをシナリオ別に分岐する (`Pre-sync hook failed`, `Post-sync hook failed`, `Auto-commit failed`)。従来は全て `Sync conflict detected` に固定されていた。
- リポジトリの HEAD が設定ブランチと異なる場合は sync をスキップする安全装置を追加する。作業ブランチを誤って push する事故を防ぐ ([#9](https://github.com/Seika139/repo-sync/pull/9))。
- 運用支援用の mise タスクを追加する: `config-init` / `config-validate` / `logs` / `service` / `test-notify` / `test-summary`。
- `mise run logs follow` を追加し、`tail -f` でログをリアルタイム監視できるようにする (Ctrl+C で終了) ([#19](https://github.com/Seika139/repo-sync/pull/19))。
- `mise run service start` の完了後に `mise run logs file` を案内するメッセージを表示する ([#19](https://github.com/Seika139/repo-sync/pull/19))。

### Changed

- `discord-notify` の依存を v0.1.3 に更新し、Discord 側の User-Agent 制限による 403 を解消する ([#8](https://github.com/Seika139/repo-sync/pull/8))。
- `uv` 依存を最新版に更新する ([#15](https://github.com/Seika139/repo-sync/pull/15), [#16](https://github.com/Seika139/repo-sync/pull/16))。
- `mise run logs file` を「直近 60 分のスナップショット」に変更する。末尾 200 行をプレフィルタしてから awk で時刻フィルタを適用するため、ログが巨大でも高速。GNU date (Linux / WSL) と BSD date (macOS) の構文差は `uname -s` で吸収する ([#19](https://github.com/Seika139/repo-sync/pull/19))。

### Fixed

- Discord webhook の送信失敗で sync 全体が crash する問題を修正する。webhook エラーは catch してログに残し、後続のリポジトリ処理を続行する ([#6](https://github.com/Seika139/repo-sync/pull/6), [#7](https://github.com/Seika139/repo-sync/pull/7))。
- `commit_all` が `git add -A` の結果を捨てていたため、nested git repo などで add が失敗すると stderr が空のまま「Commit failed: 」とだけログされる問題を修正する。add 失敗時はそのまま `GitResult` を伝播し、呼び出し側で Discord 通知まで行う。
- systemd unit (`systemd/repo-sync.service`) の `GIT_SSH_COMMAND` が存在しない鍵パス (`~/.ssh/id_ed25519_github`) を指し続けていたため、毎回 `Warning: Identity file ... not accessible` が stderr に出る (普段は不可視だが fetch 失敗時に紛れ込んで原因切り分けを阻害) 問題を修正する。`Environment=GIT_SSH_COMMAND=...` を削除し、SSH 鍵の選択は `~/.ssh/config` (Include `config.secret`) の `Host github.com` ブロックに委譲する。

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
- `both` かつ branches が diverged している場合、`git rebase` を試行し、失敗時は `git rebase --abort` で元に戻した上で Discord に通知する
- `auto_commit` オプションで未コミット変更を自動コミット可能にする
- `discord-notify` と連携してコンフリクト発生時に Discord 通知を送信する
- `--dry-run` オプションで実際の変更を行わずに動作を確認可能にする
- YAML 設定ファイル (`~/.config/repo-sync/config.yaml`) から複数リポジトリを管理する
