# Review and Repair Workflow

## Purpose
Turn verification failures and review findings into a structured repair loop rather than allowing an agent to stop after the first failed check.

## Lifecycle

1. Run `bash scripts/agent/collect-failures.sh`.
2. Read `.agent/reports/verification-latest.md`.
3. Classify each failure as:
   - deterministic tooling failure
   - implementation failure
   - architecture invariant failure
   - environment/dependency failure
   - missing test/coverage
4. Inspect the smallest relevant code and documentation surface.
5. Make one coherent repair.
6. Re-run `bash scripts/agent/collect-failures.sh`.
7. Run `bash scripts/agent/review.sh`.
8. If a reviewer signal remains, inspect the applicable reviewer contract and repair before continuing.
9. Repeat until verification passes or a human escalation condition is reached.

## Human escalation conditions

Stop and ask for human direction when:

- requirements conflict with an existing ADR or invariant;
- the correct behavior cannot be established from repository evidence;
- a production credential, production database, or destructive operation would be required;
- a migration requires irreversible data loss;
- verification is unavailable or produces contradictory results;
- the agent would need to weaken or bypass an invariant to make the checks pass.

## Completion criteria

A task is not complete merely because the implementation compiles. Completion requires:

- verification passes;
- applicable reviewer contracts have been evaluated;
- no unresolved blocker/major findings remain;
- the diff is scoped to the task;
- relevant tests or regression coverage exist;
- any architectural decision is recorded when required.
