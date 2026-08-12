# POS Engineering Skill

Use this skill for work affecting checkout, cart-to-sale conversion, receipts, in-shop payment flows, or POS-specific UI/API behavior.

## Before coding

1. Read `docs/domain/pos.md`.
2. Inspect the sales, payment, inventory, and receipt implementations.
3. Identify the authoritative transaction boundary.
4. Find existing tests covering the affected workflow.

## Implementation rules

- Do not trust client-calculated totals when the server can calculate them authoritatively.
- Preserve idempotency for retriable checkout operations.
- Keep payment and inventory state explicit.
- Do not introduce side effects through unrelated model signals without documenting the reason.
- Preserve auditability of financial and inventory effects.

## Verification

At minimum, verify the changed behavior plus relevant failure/retry cases. Run the canonical agent verification command before completion.
