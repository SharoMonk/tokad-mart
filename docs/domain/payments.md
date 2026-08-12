# Payments Domain

Payment state is authoritative domain state and integrates with external providers through explicit boundaries.

## Core invariants

- Client/UI claims do not establish authoritative payment success.
- Provider callbacks are safe to process more than once.
- Delayed, failed, cancelled, and refunded states are explicit.
- Reconciliation data is retained without unnecessary sensitive payment data.

Consult `.agent/skills/payments/SKILL.md` and ADR-003/ADR-004 before changing payment behavior.