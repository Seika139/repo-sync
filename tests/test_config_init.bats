#!/usr/bin/env bats

setup() {
  ORIG_HOME="$HOME"
  TEST_HOME="$(mktemp -d)"
  export HOME="$TEST_HOME"

  TEST_WORKDIR="$(mktemp -d)"
  echo "sample content" > "$TEST_WORKDIR/config.sample.yaml"

  SCRIPT="$BATS_TEST_DIRNAME/../mise/tasks/config-init.sh"
}

teardown() {
  export HOME="$ORIG_HOME"
  rm -rf "$TEST_HOME" "$TEST_WORKDIR"
}

@test "config.yaml を新規作成する" {
  cd "$TEST_WORKDIR"
  run bash "$SCRIPT"

  [ "$status" -eq 0 ]
  [ -f "$TEST_HOME/.config/repo-sync/config.yaml" ]
  [[ "$output" == *"Created:"* ]]
}

@test "作成された config.yaml の権限が 600 である" {
  cd "$TEST_WORKDIR"
  run bash "$SCRIPT"

  perms=$(stat -f "%Lp" "$TEST_HOME/.config/repo-sync/config.yaml" 2>/dev/null \
    || stat -c "%a" "$TEST_HOME/.config/repo-sync/config.yaml" 2>/dev/null)
  [ "$perms" = "600" ]
}

@test "作成された config.yaml の内容がサンプルと一致する" {
  cd "$TEST_WORKDIR"
  run bash "$SCRIPT"

  diff -q "$TEST_WORKDIR/config.sample.yaml" "$TEST_HOME/.config/repo-sync/config.yaml"
}

@test "config.yaml が既に存在する場合はスキップする" {
  mkdir -p "$TEST_HOME/.config/repo-sync"
  echo "existing" > "$TEST_HOME/.config/repo-sync/config.yaml"

  cd "$TEST_WORKDIR"
  run bash "$SCRIPT"

  [ "$status" -eq 0 ]
  [[ "$output" == *"already exists"* ]]
  [ "$(cat "$TEST_HOME/.config/repo-sync/config.yaml")" = "existing" ]
}

@test "config.sample.yaml が無い場合はエラーになる" {
  cd "$(mktemp -d)"
  run bash "$SCRIPT"

  [ "$status" -eq 1 ]
  [[ "$output" == *"not found"* ]]
}
