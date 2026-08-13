# Migration Workflow

Use for database schema or data migrations.

## Steps

1. Identify affected models, constraints, indexes, and consumers.
2. Inspect existing migration history before creating a new migration.
3. Determine whether the change is additive, destructive, or data-transforming.
4. For non-trivial changes, create an execution plan covering compatibility and rollback considerations.
5. Implement the smallest safe migration.
6. Validate generated migration files and dependency ordering.
7. Test migration application from the current development state.
8. Test relevant application behavior after migration.
9. Never run destructive operations against production without explicit human approval.
10. Document important schema decisions in `docs/decisions/`.

## Completion criteria

- Migration is valid and ordered correctly.
- Existing data compatibility has been considered.
- Relevant tests pass.
- No unreviewed destructive operation is introduced.