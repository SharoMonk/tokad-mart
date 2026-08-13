#!/usr/bin/env bash
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

REPORT_DIR="${TOKAD_AGENT_REPORT_DIR:-.agent/reports}"
mkdir -p "$REPORT_DIR"
REPORT="$REPORT_DIR/review-latest.md"
STATUS=0

has_changed() {
  local pattern="$1"
  git diff --name-only HEAD^ HEAD 2>/dev/null | grep -Eq "$pattern"
}

{
  echo "# Agent Review Report"
  echo
  echo "Generated: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo
  echo "## Reviewers"
  echo
  echo "### Architecture"
  cat .agent/reviewers/architecture.md
  echo
  echo "### Security"
  cat .agent/reviewers/security.md
  echo
  echo "### Backend"
  cat .agent/reviewers/backend.md
  echo
  echo "### POS"
  cat .agent/reviewers/pos.md
  echo
  echo "## Automated review signals"
  echo

  if git diff --check HEAD^ HEAD; then
    echo "- PASS: whitespace/error markers in the latest commit"
  else
    echo "- FAIL: whitespace/error markers in the latest commit"
    STATUS=1
  fi

  if has_changed 'services/api|apps/|packages/'; then
    echo "- INFO: application code changed; full verification is required"
  else
    echo "- INFO: no application source path detected in latest commit"
  fi

  if has_changed 'payment|payments|checkout|sale|sales|inventory|pos|order'; then
    echo "- REVIEW REQUIRED: transactional/POS-sensitive paths changed"
    echo "  - Apply `.agent/reviewers/pos.md` and relevant domain invariants."
  else
    echo "- INFO: no transactional/POS-sensitive path detected in latest commit"
  fi

  if has_changed 'manage.py|models.py|migrations/|pyproject.toml|requirements'; then
    echo "- REVIEW REQUIRED: backend/database paths changed"
    echo "  - Apply `.agent/reviewers/backend.md`."
  fi

  if has_changed 'auth|permission|security|secret|token|credential|\.env'; then
    echo "- REVIEW REQUIRED: security-sensitive path changed"
    echo "  - Apply `.agent/reviewers/security.md`."
  fi

  echo
  echo "## Changed files"
  git diff --name-status HEAD^ HEAD 2>/dev/null || echo "Unable to determine latest commit diff."
  echo
  echo "## Review contract"
  echo "Automated signals are not a substitute for semantic model review. A coding agent must inspect the applicable reviewer contract before declaring a task complete."
} > "$REPORT"

printf 'Review report: %s\n' "$REPORT"
exit "$STATUS"
