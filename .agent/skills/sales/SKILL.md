# Sales Domain Skill

Use this skill for order, checkout, sale, refund, return, and receipt work.

## Required understanding

- Treat a sale as a domain transaction, not a collection of CRUD writes.
- Inspect order, line-item, payment, inventory, customer, and receipt flows before changing behavior.
- Preserve explicit state transitions and immutable completed-sale history.
- Financial and inventory effects must be atomic and auditable.
- Retries around externally visible effects must be idempotent.

## Implementation rules

1. Find the existing domain service before adding a new one.
2. Keep validation at appropriate boundaries and domain rules in domain/application services.
3. Do not calculate authoritative totals from client-provided values.
4. Do not mutate completed transactions to repair historical data; use correction/refund flows.
5. Add regression tests for every changed invariant.
6. Consider concurrent checkout and retry behavior for transactional changes.

## Verification

Run focused sales tests first, then `scripts/agent/verify`.
Document any new state transition or invariant in `docs/domain/` or `docs/decisions/`.