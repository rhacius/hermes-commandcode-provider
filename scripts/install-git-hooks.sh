#!/usr/bin/env bash
# Install versioned hooks from .githooks/ into this checkout's git hooks dir.
set -euo pipefail

repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if ! git -C "$repo" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "Not a git checkout: $repo" >&2
  exit 1
fi

src="$repo/.githooks/pre-commit"
if [ ! -f "$src" ]; then
  echo "Missing hook source: $src" >&2
  exit 1
fi

hooks_dir="$(git -C "$repo" rev-parse --git-path hooks)"
case "$hooks_dir" in
  /*) ;;
  *) hooks_dir="$repo/$hooks_dir" ;;
esac
dest="$hooks_dir/pre-commit"

mkdir -p "$hooks_dir"
if [ -e "$dest" ] && ! cmp -s "$src" "$dest"; then
  echo "Refusing to overwrite existing hook: $dest" >&2
  echo "Move it aside or replace it manually if you want this project's hook." >&2
  exit 1
fi

install -m 755 "$src" "$dest"
echo "Installed pre-commit hook -> $dest"
