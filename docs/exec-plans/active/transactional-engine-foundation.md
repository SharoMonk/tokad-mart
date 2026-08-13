# Transactional Engine Foundation

Status: active
Owner: engineering

## Objective

Implement the first real Tokad Mart business domain on top of the existing harness, beginning with the transactional sales engine and POS checkout.

## Repository constraint

The current branch contains the agent/harness foundation but not yet the Django application implementation. Do not fabricate passing application evaluations. The implementation phase begins only when the backend scaffold is introduced.

## Phase 1 — domain primitives

- [ ] establish Django project/app boundaries
- [ ] configure PostgreSQL as the transactional store
- [ ] introduce Product and inventory-location primitives
- [ ] introduce Customer reference
- [ ] introduce Sale and SaleLine
- [ ] introduce Payment
- [ ] introduce InventoryMovement
- [ ] introduce IdempotencyRecord
- [ ] introduce AuditEvent

## Phase 2 — application services

- [ ] CheckoutSale
- [ ] ApplyPaymentResult
- [ ] AdjustInventory
- [ ] RefundSale

## Phase 3 — concurrency and correctness

- [ ] define and test stock concurrency policy
- [ ] define database transaction boundaries
- [ ] enforce idempotency uniqueness
- [ ] enforce money/currency rules
- [ ] enforce state-machine transitions

## Phase 4 — API/POS boundary

- [ ] expose checkout API
- [ ] expose payment-result API/webhook boundary
- [ ] expose inventory adjustment API
- [ ] expose receipt representation
- [ ] ensure API layer delegates business behavior to application services

## Phase 5 — evaluations

Turn POS-001 through POS-008 from `pending-implementation` into executable application evaluations only after the corresponding application behavior exists.

## Completion criteria

- `./scripts/agent/verify` passes.
- Architecture and dependency checks pass.
- Domain unit tests pass.
- Transaction/integration tests pass against PostgreSQL.
- POS evaluations POS-001 through POS-008 are executable and passing.
- No completed-sale mutation path bypasses compensating operations.
- Duplicate checkout/payment events do not duplicate business effects.
- Inventory movements are auditable.
