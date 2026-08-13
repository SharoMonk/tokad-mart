# Django Engineering Skill

Use for Django/DRF backend changes.

## Procedure

1. Identify the owning app/domain.
2. Inspect models, services, serializers, views, URLs, and tests before changing code.
3. Preserve existing project conventions.
4. Put cross-model business workflows in explicit services/use cases.
5. Use database transactions for multi-step state changes.
6. Add regression tests for changed behavior.
7. Validate migrations when models change.

## Avoid

- unnecessary new dependencies;
- business logic hidden in signals;
- bypassing validation for convenience;
- broad refactors mixed into feature work.
