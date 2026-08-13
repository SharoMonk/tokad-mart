#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SCENARIO_FILE="$ROOT_DIR/docs/evals/scenarios/pos.yml"
REPORT_DIR="$ROOT_DIR/.agent/reports"
REPORT_FILE="$REPORT_DIR/evals-latest.md"

mkdir -p "$REPORT_DIR"

if [[ ! -f "$SCENARIO_FILE" ]]; then
  echo "ERROR: evaluation scenario registry missing: $SCENARIO_FILE" >&2
  exit 1
fi

python - "$SCENARIO_FILE" "$REPORT_FILE" <<'PY'
from pathlib import Path
import re
import sys

scenario_file = Path(sys.argv[1])
report_file = Path(sys.argv[2])
text = scenario_file.read_text(encoding="utf-8")
ids = re.findall(r'^  - id: (POS-\d+)$', text, re.M)
objectives = re.findall(r'^    objective: (.+)$', text, re.M)
invariants = re.findall(r'^    invariants: \[(.+)\]$', text, re.M)

errors = []
if len(ids) != len(objectives) or len(ids) != len(invariants):
    errors.append("Every scenario must define id, objective, and invariants.")
if len(ids) != len(set(ids)):
    errors.append("Scenario IDs must be unique.")

report = ["# Evaluation Report", "", f"Registered scenarios: {len(ids)}", ""]
if errors:
    report += ["## Registry validation: FAIL", ""] + [f"- {e}" for e in errors]
    report_file.write_text("\n".join(report) + "\n", encoding="utf-8")
    raise SystemExit(1)

report += ["## Registry validation: PASS", "", "| Scenario | Status |", "|---|---|"]
for scenario_id in ids:
    report.append(f"| {scenario_id} | pending-implementation |")
report += ["", "Application execution is not yet enabled because the transactional application modules are still being built."]
report_file.write_text("\n".join(report) + "\n", encoding="utf-8")
print(f"Evaluation registry valid: {len(ids)} scenarios")
print(f"Report: {report_file}")
PY
