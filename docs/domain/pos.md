# POS Domain

The POS is the in-shop interface over the transactional sales engine. It is not the source of truth for financial or inventory rules.

## Core flow

Cart → checkout validation → sale/order creation → payment → inventory effect → receipt/audit.

Exact state transitions must follow the implementation and applicable ADRs.

## Invariants

- A checkout must not create duplicate financial or inventory effects when retried.
- Totals must be calculated from authoritative line-item/pricing rules rather than trusted client totals.
- Completed transactions must not be edited through ordinary cart operations.
- Inventory effects must be atomic with the business operation that requires them, or use an explicitly documented eventual-consistency workflow.
- Payment state must be represented explicitly.
- Receipts are projections of transaction state, not an independent source of truth.

## Agent guidance

When changing POS behavior, inspect sales, payments, inventory, and receipt paths before editing. Add tests for successful checkout, invalid checkout, retry/idempotency behavior, and relevant failure paths.
