# Backend Architecture

## Scope

The backend owns authentication, authorization, business rules, persistence, transactional workflows, and API contracts.

## Django/DRF guidance

- Keep serializers focused on boundary validation and representation.
- Keep views/controllers thin; delegate business workflows to services/use cases.
- Keep model methods focused on local invariants rather than orchestration across domains.
- Use database transactions for operations that change related financial, order, or inventory state.
- Prefer explicit service boundaries over hidden signal-driven business behavior.
- Add tests at the domain/service level and API level for externally observable behavior.

## New feature checklist

1. Identify the owning domain.
2. Find existing models/services/repositories before creating new ones.
3. Define state transitions and invariants.
4. Define API contract and validation behavior.
5. Implement the smallest coherent change.
6. Add regression and integration tests.
7. Validate migrations and API behavior.
