# repo-sync

ローカルの git リポジトリを GitHub リモートと自動で同期するツール。systemd timer や cron で定期実行する想定。

コンフリクト発生時は Discord Webhook で通知する。

## インストール

```bash
uv sync
```

`discord-notify` パッケージは git+tag 依存で自動取得されるため、別途 clone する必要はない。

## 設定

設定ファイルのサンプルをコピーして編集する。

```bash
mkdir -p ~/.config/repo-sync
cp config.sample.yaml ~/.config/repo-sync/config.yaml
```

### config.yaml の例

```yaml
# Discord Webhook URL（コンフリクト時の通知先）
# Server Settings > Integrations > Webhooks から取得
discord_webhook_url: "https://discord.com/api/webhooks/YOUR_ID/YOUR_TOKEN"

# Discord に表示される Bot 名（省略可、デフォルト: repo-sync）
bot_username: "repo-sync"

repos:
  - path: ~/dotfiles
    direction: push # push | pull | both
    branch: main
    # remote: origin      # デフォルト: origin
    # auto_commit: true   # デフォルト: true

  - path: ~/notes
    direction: both
    branch: main

  - path: ~/work/shared-config
    direction: pull
    branch: develop
    auto_commit: false
```

### 設定項目

| キー                  | 必須 | デフォルト  | 説明                                  |
| --------------------- | ---- | ----------- | ------------------------------------- |
| `discord_webhook_url` | -    | `""`        | Discord Webhook URL。空なら通知しない |
| `bot_username`        | -    | `repo-sync` | Discord に表示する Bot 名             |
| `repos[].path`        | Yes  | -           | リポジトリの絶対パス（`~` 展開可）    |
| `repos[].direction`   | -    | `both`      | 同期方向: `push`, `pull`, `both`      |
| `repos[].branch`      | -    | `main`      | 同期対象ブランチ                      |
| `repos[].remote`      | -    | `origin`    | リモート名                            |
| `repos[].auto_commit` | -    | `true`      | 未コミットの変更を自動コミットするか  |

## 使い方

```bash
# 全リポジトリを同期
uv run repo-sync

# 設定ファイルを指定
uv run repo-sync -c /path/to/config.yaml

# 何が実行されるか確認（実際には変更しない）
uv run repo-sync --dry-run

# デバッグログを表示
uv run repo-sync -v
```

## 同期ロジック

各リポジトリに対して以下の処理を行う。

### 1. `git fetch`

リモートの最新情報を取得する。

### 2. 未コミット変更の処理

`auto_commit: true` かつ `direction` が `push` または `both` の場合、未コミットの変更があれば `auto-sync: YYYY-MM-DD_HH:MM` というメッセージで自動コミットする。

### 3. 状態判定と同期

ローカル HEAD とリモートの関係を判定し、`direction` に応じて処理する。

| 状態       | `pull`               | `push`       | `both`               |
| ---------- | -------------------- | ------------ | -------------------- |
| up-to-date | 何もしない           | 何もしない   | 何もしない           |
| behind     | `git pull --ff-only` | Discord 通知 | `git pull --ff-only` |
| ahead      | Discord 通知         | `git push`   | `git push`           |
| diverged   | Discord 通知         | Discord 通知 | `git rebase` を試行  |

`both` + diverged の場合:

- rebase 成功 → `git push`
- rebase 失敗 → `git rebase --abort` で元に戻し、Discord で通知

## フック (`.repo-sync/pre-sync.sh` / `post-sync.sh`)

リポジトリ直下に `.repo-sync/pre-sync.sh` / `.repo-sync/post-sync.sh` を配置しておくと、repo-sync が自動で検知して実行する。設定ファイル (`config.yaml`) への追記は不要。

| フック            | 実行タイミング                              | 用途例                                   |
| ----------------- | ------------------------------------------- | ---------------------------------------- |
| `pre-sync.sh`     | `git fetch` より前                          | バックアップ生成、動的ファイル更新       |
| `post-sync.sh`    | sync が成功した後 (up-to-date 含む)         | インデックス再構築、キャッシュ無効化     |

### 仕様

- 実行ファイル（`chmod +x`）として配置すること。実行権限が無い場合は警告ログを出してスキップする。
- `cwd` はリポジトリのルート。
- `pre-sync.sh` は auto-commit より前に走るため、生成したファイルは `direction: push` または `both` で `auto_commit: true` のリポジトリであれば、同一サイクルで自動的にコミット & push される。`pull` のリポジトリでは生成ファイルは未コミットのまま残る。
- `post-sync.sh` は sync 結果が `up-to-date` / `pulled` / `pushed` / `rebased-and-pushed` のいずれかの場合にのみ実行される。`conflict` / `error` のときはスキップする。
- 期待ブランチ以外にチェックアウトされているリポジトリでは、sync 自体が skip されるためフックも実行されない。
- フックが非 0 で終了した場合、そのリポジトリの結果は `error` になり Discord 通知が送られる。
- フックは 15 分（`HOOK_TIMEOUT_SEC`）で強制終了される。ハングや長時間実行のフックは失敗扱い。
- shebang 不備や interpreter 不在などで exec 自体が失敗した場合も `error` として通知される。
- `--dry-run` 時は実行されず、ログに「would run」とだけ出す。

### 例: second-brain の post-sync

```bash
# /opt/second-brain/.repo-sync/post-sync.sh
#!/usr/bin/env bash
set -euo pipefail
uv run kc index
```

## デプロイ (systemd timer)

VPS に systemd timer として設置する手順。

### 前提条件

- Ubuntu 20.04+
- `mise` がインストール済み (`curl https://mise.run | sh`)
- SSH 鍵 (`~/.ssh/id_ed25519_github`) で GitHub に認証可能
- `~/.config/repo-sync/config.yaml` を作成済み

### セットアップ

```bash
cd ~/programs/tools/repo-sync
mise trust && mise install   # uv と python をインストール
mise exec -- uv sync --frozen
sudo bash install.sh
```

`install.sh` が行うこと:

1. `mise exec -- uv sync --frozen` で依存を同期
2. `/var/log/repo-sync/` を作成
3. logrotate を設定 (weekly, 4 世代)
4. `repo-sync.service` / `repo-sync.timer` を `/etc/systemd/system/` に配置
5. timer を有効化

### 運用コマンド

```bash
# timer の状態確認
systemctl list-timers repo-sync.timer

# 手動で即時実行
sudo systemctl start repo-sync.service

# ログ確認
tail -f /var/log/repo-sync/repo-sync.log    # 実行ログ
journalctl -u repo-sync.service -n 50       # サービスイベント

# 停止・無効化
sudo systemctl stop repo-sync.timer
sudo systemctl disable repo-sync.timer
```

### ツールの更新

```bash
cd ~/programs/tools/repo-sync
git fetch --tags
git checkout v0.2.0          # 目的のバージョンタグ
mise exec -- uv sync --frozen
sudo systemctl restart repo-sync.timer
```

### cron で実行する場合

systemd timer を使わない場合は cron でも動作する。

```cron
PATH=/home/user/.local/bin:/usr/local/bin:/usr/bin:/bin
*/30 * * * * cd /home/user/programs/tools/repo-sync && /home/user/.local/bin/mise exec -- uv run repo-sync >> /var/log/repo-sync/repo-sync.log 2>&1
```

## 開発

[mise](https://mise.jdx.dev/) でツールバージョンを管理している。

```bash
mise trust && mise install
```

### テスト

```bash
mise run test
# または
uv run pytest -v
```

### Lint

```bash
mise run lint
# または
uv run ruff check .
uv run ruff format --check .
```
