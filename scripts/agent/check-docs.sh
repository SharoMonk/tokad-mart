#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

status=0

require_file() {
  local path="$1"
  if [[ ! -f "$path" ]]; then
    echo "MISSING: $path"
    status=1
  fi
}

# Core agent contract and harness entry points.
require_file AGENTS.md
require_file docs/README.md
require_file scripts/agent/verify.sh

# Durable architectural decisions currently referenced by the agent contract.
require_file docs/decisions/ADR-001-transaction-boundaries.md
require_file docs/decisions/ADR-002-inventory-consistency.md
require_file docs/decisions/ADR-003-payment-state.md
require_file docs/decisions/ADR-004-idempotency.md

# Every skill must have a canonical SKILL.md entry point.
while IFS= read -r -d '' skill_dir; do
  require_file "$skill_dir/SKILL.md"
done < <(find .agent/skills -mindepth 1 -maxdepth 1 -type d -print0 2>/dev/null)

# Reject common accidental absolute-path links in repository-local docs.
if grep -RInE '\]\(/(home|Users|tmp|var)/' AGENTS.md docs .agent 2>/dev/null; then
  echo "INVALID: repository-local documentation contains an absolute filesystem link"
  status=1
fi

if [[ "$status" -ne 0 ]]; then
  echo "DOCUMENTATION CHECK FAILED"
  exit "$status"
fi

echo "DOCUMENTATION CHECK PASSED"
