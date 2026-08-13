# Dependency Invariants

- DEP-001: Presentation/API layers depend on application/domain services rather than bypassing them for business mutations.
- DEP-002: Domain logic must not import presentation/UI modules.
- DEP-003: Infrastructure adapters are accessed through explicit service/repository boundaries.
- DEP-004: Cross-domain dependencies must be intentional and documented when they create business coupling.
- DEP-005: New architectural exceptions require an ADR or an update to an existing architectural decision.
