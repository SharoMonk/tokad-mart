# Tokad Mart Evaluation Harness

Application-level evaluations are black-box acceptance scenarios for critical business behavior. They are intentionally separate from unit tests: an eval asks whether the system as a whole satisfies a business contract.

## Structure

- `scenarios/` — versioned POS and transactional scenarios.
- `run-evals.sh` — canonical local entry point.
- `reports/` — generated locally/CI; do not commit results.

## Rules

1. Every critical business invariant should have at least one executable scenario.
2. Scenarios must define setup, action, expected outcome, and failure signal.
3. A passing unit test does not substitute for a passing application-level eval.
4. Scenarios must be deterministic and isolated from production services.
5. When an eval fails, the failure report must identify the scenario, expected behavior, observed behavior, and relevant logs.

The initial repository is still a foundation scaffold. Scenarios are therefore registered now and become executable as the corresponding application modules land.
