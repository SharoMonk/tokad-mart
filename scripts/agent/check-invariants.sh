#!/usr/bin/env bash
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

status=0
fail() {
  echo "FAIL: $1"
  status=1
}

require_file() {
  local file="$1"
  if [[ -f "$file" ]]; then
    echo "PASS: invariant source exists: $file"
  else
    fail "missing invariant source: $file"
  fi
}

for file in \
  docs/architecture/invariants/sales.md \
  docs/architecture/invariants/inventory.md \
  docs/architecture/invariants/payments.md \
  docs/architecture/invariants/pos.md \
  docs/architecture/invariants/dependencies.md \
  docs/architecture/invariants/security.md; do
  require_file "$file"
done

# Detect obvious committed secrets in the repository tree. This is deliberately
# conservative: CI should fail loudly on high-risk credential-like patterns.
if command -v git >/dev/null 2>&1; then
  tracked="$(git ls-files)"
  if printf '%s\n' "$tracked" | grep -Eiq '(^|/)(\.env|\.env\..*|.*\.pem|.*\.key)$'; then
    fail "tracked environment/private-key file detected"
  else
    echo "PASS: no tracked environment/private-key filenames detected"
  fi
fi

if [[ "$status" -ne 0 ]]; then
  echo "INVARIANT CHECK FAILED"
  exit "$status"
fi

echo "INVARIANT CHECK PASSED"
