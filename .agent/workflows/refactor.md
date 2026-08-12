# Refactor Workflow

Use for structural changes where externally observable behavior should remain unchanged.

## Steps

1. Define the behavior that must remain stable.
2. Inspect current architecture and dependencies.
3. Establish or confirm characterization/regression tests.
4. Create a scoped execution plan for non-trivial refactors.
5. Refactor incrementally without mixing unrelated feature work.
6. Run focused tests after each meaningful boundary change.
7. Run full relevant verification.
8. Inspect the final diff for accidental behavior changes.
9. Update architecture documentation or ADRs if the structure changes.

## Completion criteria

- Existing behavior remains covered.
- Relevant tests and static checks pass.
- No unnecessary dependency or abstraction was introduced.
- Documentation reflects the resulting architecture.