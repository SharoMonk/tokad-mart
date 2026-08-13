# Evaluation Workflow

Use this workflow for changes affecting business behavior.

## 1. Identify scenarios

Find existing scenarios under `docs/evals/scenarios/`. Add or update a scenario when the behavior is new or materially changed.

## 2. Map invariants

Every scenario must reference the architectural invariants it protects.

## 3. Implement

Prefer the smallest production change that satisfies the business contract.

## 4. Run unit/integration tests

Run the normal verification harness first.

## 5. Run application-level evals

```bash
bash scripts/agent/run-evals.sh
```

A registry PASS is not the same as an application behavior PASS. Once the relevant modules exist, each pending scenario must gain an executable adapter and move to passing.

## 6. Diagnose failures

Capture expected behavior, observed behavior, logs, and the smallest reproducible input. Do not weaken a scenario merely to make CI green.

## 7. Update the contract

If product behavior intentionally changed, update the scenario and its linked invariant/ADR in the same change.
