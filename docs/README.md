# Tokad Mart Knowledge Base

This directory is the repository's durable source of engineering knowledge. Agents should start here after reading `AGENTS.md` and progressively load only the documents relevant to the task.

## Architecture

- `architecture/system.md` — system overview and repository boundaries.
- `architecture/backend.md` — Django/DRF backend conventions.
- `architecture/frontend.md` — Next.js/TypeScript conventions.
- `architecture/mobile.md` — companion React Native/Expo boundary.
- `architecture/data.md` — PostgreSQL, transactions, and persistence rules.

## Domain

- `domain/sales.md` — sale/order lifecycle and invariants.
- `domain/inventory.md` — stock and inventory consistency.
- `domain/products.md` — product/catalog concepts.
- `domain/customers.md` — customer identity and customer data.
- `domain/payments.md` — payment state and idempotency.
- `domain/pos.md` — in-shop POS behavior and constraints.

## Decisions

Architectural decisions are recorded in `decisions/ADR-*.md`. Agents must consult relevant ADRs before changing a settled architectural boundary.

## Execution plans

Large changes belong in `exec-plans/active/`. Completed plans move to `exec-plans/completed/`. Plans should capture scope, decisions, affected domains, verification, and unresolved risks.

## Specs

Product and feature requirements belong under `specs/` when they are durable enough to become repository knowledge.

## Generated knowledge

Machine-generated documentation belongs under `generated/`. Generated artifacts must not be treated as authoritative if they conflict with executable code or explicit architectural/domain documentation.
