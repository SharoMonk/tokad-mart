# Quality Gates

The harness uses layered gates. A change must satisfy the gates that apply to its scope.

## Gate order

1. Repository hygiene
2. Documentation and agent-contract checks
3. Architecture/invariant checks
4. Unit tests
5. Integration/evaluation tests
6. Build/type/lint checks
7. Security checks
8. Review and diff inspection

## Change-class requirements

| Change | Minimum gates |
|---|---|
| Documentation/agent config | hygiene, docs, shell/structure checks |
| Backend/domain | architecture, unit, integration, lint/type checks |
| Database/migrations | architecture, migration validation, integration, rollback review |
| POS/checkout | architecture, transactional tests, POS evaluations, security, review |
| Payments | architecture, idempotency tests, security, POS evaluations, review |
| Frontend/mobile | architecture, tests, lint/type/build, relevant UX evaluation |

## Principle

A green unit-test suite is not sufficient evidence for transactional changes. Business invariants and end-to-end evaluations are required where the behavior crosses domain boundaries.

## No false green

An evaluation that cannot execute because its application prerequisite is absent must be reported as `blocked` or `not-applicable`, never as `passed`.
