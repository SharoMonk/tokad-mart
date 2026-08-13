# Architecture Policy

## Required behavior

- Reuse established boundaries before creating new ones.
- Domain business rules must have an identifiable owner.
- API clients must not become a second implementation of server-side transactional rules.
- Cross-domain dependencies must be explicit and justified.
- Material architectural changes require an ADR under `docs/decisions/`.

## Agent stop conditions

Stop and request human direction when requirements conflict with an existing architectural decision, when a new architectural boundary is unavoidable but unspecified, or when correctness cannot be established from available tests and documentation.
