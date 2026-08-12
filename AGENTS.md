# Tokad Mart — Agent Contract

Tokad Mart is a retail and wholesale commerce platform. The current implementation focus is the transactional sales engine and in-shop POS.

## How to work in this repository

1. Read this file first.
2. Use `docs/README.md` as the map to deeper repository knowledge.
3. Inspect the existing implementation and tests before changing code.
4. Follow the relevant skill under `.agent/skills/` and workflow under `.agent/workflows/`.
5. Treat `docs/domain/` and `docs/decisions/` as the source of truth for business rules and architectural decisions.
6. Prefer existing patterns over introducing new abstractions or dependencies.
7. Keep changes scoped to the task. Do not perform unrelated cleanup.
8. Never guess external API or database behavior when it can be inspected or verified.

## Architecture boundaries

- Backend: Django + Django REST Framework.
- Database: PostgreSQL.
- Async work: Redis/Celery.
- Web/POS: Next.js + TypeScript.
- Mobile: React Native/Expo in the companion repository.
- Business domains must preserve transactional consistency, auditability, and explicit state transitions.

## Transactional rules

- Completed sales are immutable except through explicit correction/refund flows.
- Inventory-changing operations must be atomic and auditable.
- Payment and order state must not be silently inferred from UI state.
- Retries must be designed to be idempotent where an operation can create financial or inventory effects.
- Never bypass domain services merely to make a test pass.

## Verification

Before declaring a task complete:

- run the narrowest relevant tests;
- run static/lint checks relevant to changed code;
- validate migrations when models change;
- inspect the final Git diff;
- report anything that could not be verified.

Use `scripts/agent/verify` as the canonical verification entry point once the local environment is available.

## Safety and approval boundaries

Do not access production systems or credentials. Treat destructive database operations, dependency upgrades, architecture changes, CI/release changes, and pushes as actions requiring explicit human review unless the active workflow explicitly grants permission.

## Documentation discipline

When implementation changes an architectural rule, domain invariant, public API, or operational workflow, update the corresponding documentation in the same change. Keep this file short; add detail to the appropriate document instead of expanding this file.
