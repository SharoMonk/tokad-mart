#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
API_DIR="$ROOT_DIR/services/api"

cd "$API_DIR"

if command -v uv >/dev/null 2>&1; then
  uv run pytest
elif command -v python >/dev/null 2>&1; then
  python -m pytest
else
  echo "ERROR: neither uv nor python is available" >&2
  exit 1
fi
