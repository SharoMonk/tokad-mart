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

# Harness/repository integrity is deterministic and should always run.
run_step "Agent documentation integrity" bash scripts/agent/check-docs.sh
run_step "Architecture invariants" bash scripts/agent/check-invariants.sh

# The repository is currently being scaffolded. These checks intentionally
# discover available tooling instead of assuming a single package manager.
if [[ -f services/api/manage.py ]]; then
  if command -v python >/dev/null 2>&1; then
    run_step "Django checks" python services/api/manage.py check
    run_step "Django migrations check" python services/api/manage.py makemigrations --check --dry-run
  else
    echo "SKIP: python is not installed"
  fi
fi

if [[ -f services/api/pyproject.toml || -f services/api/pytest.ini || -d services/api/tests ]]; then
  if command -v pytest >/dev/null 2>&1; then
    run_step "Backend tests" pytest services/api
  else
    echo "SKIP: pytest is not installed"
  fi
fi

if [[ -f package.json ]]; then
  if command -v npm >/dev/null 2>&1; then
    node -e 'const p=require("./package.json"); if (p.scripts?.lint) process.exit(0); process.exit(1)' >/dev/null 2>&1 && run_step "Root lint" npm run lint || true
  fi
fi

if [[ -f services/api/package.json ]]; then
  if command -v npm >/dev/null 2>&1; then
    node -e 'const p=require("./services/api/package.json"); if (p.scripts?.lint) process.exit(0); process.exit(1)' >/dev/null 2>&1 && (cd services/api && run_step "API lint" npm run lint) || true
  fi
fi

if [[ "$status" -ne 0 ]]; then
  echo
  echo "VERIFICATION FAILED"
  exit "$status"
fi

echo
echo "VERIFICATION PASSED"
