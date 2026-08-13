#!/usr/bin/env bash
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

status=0

run_step() {
  local name="$1"
  shift
  echo
  echo "==> $name"
  if "$@"; then
    echo "PASS: $name"
  else
    echo "FAIL: $name"
    status=1
  fi
}

run_step "Agent documentation integrity" bash scripts/agent/check-docs.sh
run_step "Architecture invariants" bash scripts/agent/check-invariants.sh

if [[ -f services/api/manage.py ]]; then
  if command -v uv >/dev/null 2>&1; then
    run_step "Django checks" bash -lc 'cd services/api && uv run python manage.py check'
    run_step "Django migrations check" bash -lc 'cd services/api && uv run python manage.py makemigrations --check --dry-run'
  elif command -v python >/dev/null 2>&1; then
    run_step "Django checks" python services/api/manage.py check
    run_step "Django migrations check" python services/api/manage.py makemigrations --check --dry-run
  else
    echo "SKIP: python is not installed"
  fi
fi

if [[ -f services/api/pyproject.toml ]]; then
  if command -v uv >/dev/null 2>&1; then
    run_step "Backend tests" bash scripts/agent/test-backend.sh
  elif command -v pytest >/dev/null 2>&1; then
    run_step "Backend tests" pytest services/api
  else
    echo "SKIP: pytest is not installed"
  fi
fi

if [[ -f package.json ]] && command -v npm >/dev/null 2>&1; then
  if node -e 'const p=require("./package.json"); process.exit(p.scripts?.lint ? 0 : 1)' >/dev/null 2>&1; then
    run_step "Root lint" npm run lint
  fi
fi

if [[ "$status" -ne 0 ]]; then
  echo
  echo "VERIFICATION FAILED"
  exit "$status"
fi

echo
echo "VERIFICATION PASSED"
