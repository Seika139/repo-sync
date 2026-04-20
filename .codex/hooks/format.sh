#!/usr/bin/env bash

set -u

repo_root=$(git rev-parse --show-toplevel 2>/dev/null || printf '%s\n' "${PWD:-.}")

if ! cd "$repo_root" 2>/dev/null; then
  printf '{"continue":true}\n'
  exit 0
fi

changed_files() {
  local ext="$1"
  {
    git diff --name-only --diff-filter=ACMR -- "*.$ext"
    git diff --cached --name-only --diff-filter=ACMR -- "*.$ext"
    git ls-files --others --exclude-standard -- "*.$ext"
  } 2>/dev/null | sed '/^$/d' | sort -u
}

# Python: ruff format + ruff check --fix
py_files=$(changed_files py)
if [ -n "$py_files" ] && command -v uv >/dev/null 2>&1; then
  while IFS= read -r file; do
    [ -f "$file" ] || continue
    uv run ruff format "$file" >/dev/null 2>&1 || true
    uv run ruff check --fix "$file" >/dev/null 2>&1 || true
  done <<EOF
$py_files
EOF
fi

# Shell: shfmt
sh_files=$(changed_files sh)
if [ -n "$sh_files" ] && command -v shfmt >/dev/null 2>&1; then
  while IFS= read -r file; do
    [ -f "$file" ] || continue
    shfmt -w -i 2 -ci "$file" >/dev/null 2>&1 || true
  done <<EOF
$sh_files
EOF
fi

# Markdown: rumdl fmt
md_files=$(changed_files md)
if [ -n "$md_files" ] && command -v rumdl >/dev/null 2>&1; then
  while IFS= read -r file; do
    [ -f "$file" ] || continue
    rumdl fmt --silent -- "$file" >/dev/null 2>&1 || true
  done <<EOF
$md_files
EOF
fi

printf '{"continue":true}\n'
