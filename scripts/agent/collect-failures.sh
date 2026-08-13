#!/usr/bin/env bash
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

OUT_DIR="${TOKAD_AGENT_REPORT_DIR:-.agent/reports}"
mkdir -p "$OUT_DIR"
REPORT="$OUT_DIR/verification-latest.md"
TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT

set +e
bash scripts/agent/verify.sh 2>&1 | tee "$TMP"
VERIFY_STATUS=${PIPESTATUS[0]}
set -e

{
  echo "# Verification Report"
  echo
  echo "Generated: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo
  if [[ "$VERIFY_STATUS" -eq 0 ]]; then
    echo "## Status"
    echo "PASS"
  else
    echo "## Status"
    echo "FAIL"
  fi
  echo
  echo "## Failed checks"
  if grep -E '^FAIL: ' "$TMP"; then
    :
  else
    echo "None"
  fi
  echo
  echo "## Skipped checks"
  if grep -E '^SKIP: ' "$TMP"; then
    :
  else
    echo "None"
  fi
  echo
  echo "## Raw verification output"
  echo '```text'
  cat "$TMP"
  echo '```'
} > "$REPORT"

printf 'Report: %s\n' "$REPORT"
exit "$VERIFY_STATUS"
