#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
HOOKS_DIR="$ROOT/.githooks"

if [[ ! -d "$HOOKS_DIR" ]]; then
  echo "Missing .githooks directory" >&2
  exit 1
fi

git config core.hooksPath .githooks

echo "Tokad Mart Git hooks installed."
echo "core.hooksPath=$(git config --get core.hooksPath)"
