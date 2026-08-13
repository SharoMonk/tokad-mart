# Evaluation Status Contract

Evaluation results use four states:

- `passed`: the scenario executed and all assertions succeeded.
- `failed`: the scenario executed and one or more assertions failed.
- `blocked`: the scenario could not execute because a required application/service capability is missing.
- `not-applicable`: the scenario does not apply to the current change or deployment mode.

## Rules

1. `blocked` is never equivalent to `passed`.
2. A change affecting a domain with mandatory evaluations cannot be considered verified while those evaluations are blocked.
3. Evaluation reports must include the scenario ID, prerequisite, observed result, and next action.
4. Agents must not modify an evaluation merely to make an implementation pass unless the product contract itself changed and the corresponding documentation/decision is updated.
5. Production-like behavior should be tested with isolated data and deterministic fixtures.
