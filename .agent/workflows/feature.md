# Feature Workflow

Use for new functionality or materially changed behavior.

## 1. Discover

- Read `AGENTS.md` and `docs/README.md`.
- Identify the owning domain and relevant skill.
- Inspect existing implementation and tests.

## 2. Plan

Write an execution plan for non-trivial work under `docs/exec-plans/active/`. Record affected domains, API/data changes, risks, and completion criteria.

## 3. Implement

Make the smallest coherent change that satisfies the specification. Reuse established patterns and preserve domain invariants.

## 4. Verify

Run focused tests first, then `scripts/agent/verify` when the local environment supports it. Resolve failures rather than suppressing them.

## 5. Review

Inspect the Git diff for accidental changes, debug code, secrets, generated files, migration problems, and architectural drift.

## 6. Complete

Update durable documentation when behavior or architecture changed. Move a completed execution plan from `active/` to `completed/` when applicable. Report verification results and remaining risks.
