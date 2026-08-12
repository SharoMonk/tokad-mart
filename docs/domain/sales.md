# Sales Domain

Sales represent authoritative commerce transactions from checkout through completion, correction, return, or refund.

## Core invariants

- Completed sales are immutable except through explicit correction/refund flows.
- Authoritative totals are calculated server-side from validated transaction data.
- Financial and inventory effects have explicit transactional boundaries.
- Retried requests must not duplicate a sale.
- Receipts reflect the authoritative transaction snapshot.

Consult `.agent/skills/sales/SKILL.md` and ADR-001/ADR-004 before changing sales behavior.