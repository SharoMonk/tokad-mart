# Inventory Domain Skill

Use this skill for stock levels, stock movements, reservations, adjustments, receiving, transfers, and inventory effects of sales.

## Required understanding

- Inventory is a transactional domain with auditable state changes.
- Identify the source transaction for every stock movement.
- Distinguish available, reserved, committed, and released quantities where those concepts exist.
- Never silently overwrite stock quantities to resolve a business discrepancy.

## Implementation rules

1. Inspect existing stock models, services, constraints, and tests before changing inventory behavior.
2. Keep inventory-changing operations atomic with the transaction that authorizes the change.
3. Define behavior for insufficient stock explicitly.
4. Protect concurrent updates with the database mechanisms appropriate to the existing architecture.
5. Preserve a traceable movement history.
6. Add regression coverage for duplicate requests, concurrent updates, and rollback paths when relevant.

## Verification

Run focused inventory tests and migration checks for schema changes, then `scripts/agent/verify`.