# Sprint 1: canonical backend consolidation

Status: in progress. Do not deploy both commerce applications as independent writers to the same stock/sales ledger.

## Decision
Use `services/api/transactional` as the canonical sales, inventory, payment, idempotency, and outbox engine. Keep `backend/commerce` intact temporarily as a reference for feature migration. Do not deploy its legacy checkout in production once the canonical POS has been adopted.

## Source model mapping

| Legacy `backend/commerce` | Canonical `services/api/transactional` | Gap / migration action |
| --- | --- | --- |
| Product (SKU, barcode, unit, retail/wholesale Decimal prices) | Product (SKU, name, currency, unit_price_minor) | Add barcode, unit, explicit retail/wholesale money-in-minor-units and validate currency; do not silently drop wholesale pricing. |
| InventoryLocation (name) | POSLocation (code, name) | Establish stable location-code mapping. |
| StockBalance (decimal quantity, reserved_quantity, version) | InventoryItem (integer quantity) | Decide fractional-unit and reservation requirements before moving stock. |
| StockMovement | InventoryMovement | Map movement categories, reference and actor/audit data. |
| Customer (email, wholesale flag) | Customer (name, phone) | Preserve email, type and associations. |
| CashierShift | No equivalent shift table | Add shifts tied to POSOperator, POSLocation and POSTerminal, with open/close/reconciliation. |
| Sale, SaleItem | Sale, SaleLine | Convert decimal prices to integer minor units, map statuses/reference, preserve legacy receipt numbers and ownership. |
| Payment | Payment, PaymentRefund, PaymentWebhookEvent | Map provider references and statuses; avoid double-creating settlements. |
| IdempotencyKey | IdempotencyRecord | Scope and fingerprint semantics differ; do not blindly import keys. |
| SaleReturn, SaleReturnItem | PaymentRefund + inventory movements only | Add return-document and returned-item accounting tied to sales and restock decisions. |
| InventoryAdjustment | InventoryMovement | Add adjustment authorization and reason/history API. |

## API contract mismatch

- Legacy Next.js POS: `/api/auth/token/`, `/api/products/`, `/api/shifts/`, `/api/sales/checkout/`, `/api/sales/{id}/receipt/`, `/api/sales/{id}/return/`.
- Canonical transactional API: `/api/transactional/pos/sales/`, Paystack initialization, webhook, reconciliation, refund and health endpoints.
- Authentication differs: legacy DRF token header versus canonical Basic/Session with role-assigned POS operators and location/terminal scope.
- Cash sale payload differs: canonical requires lines, location_code, terminal_code, currency, amount_minor, sale_idempotency_key, payment_idempotency_key and provider_reference.
- Cash sale response differs: canonical returns sale_id, reference, payment_id, total_minor, currency and statuses.

## Required migration sequence

1. Snapshot and back up the legacy and canonical PostgreSQL databases; record row counts and existing stock/payments.
2. Extend canonical schema only through reviewed migrations and add migration tests for money/quantity conversions.
3. Implement canonical read APIs (catalog, stock, locations, terminals) and operator authentication; enforce scoped authorization.
4. Port cashier shifts and reconciliation to canonical models; do not call legacy endpoints from the migrated POS.
5. Port returns/adjustments with explicit inventory movement and refund reconciliation invariants.
6. Adapt the Next.js frontend through a versioned API client with stable checkout keys (generated once per attempted sale, retained on network failure, reset only on confirmed success or deliberate new sale).
7. Render receipt data as React text rather than interpolating unescaped HTML; implement a separate authenticated print bridge.
8. Switch deployment to one API and one transactional PostgreSQL store; decommission legacy writes only after data reconciliation and a parallel-read verification period.

## Acceptance gates

- Complete real cash sale: authorized terminal -> checkout -> one sale/payment/stock movement -> receipt data.
- Duplicate submission/retry returns the same sale, no extra stock deduction.
- Two terminals cannot oversell the last unit.
- Shift opening/closing and reconciliation succeed.
- Product selection, barcode scan and wholesale pricing match server-calculated totals.
- Legacy import preserves product/customer/sale and monetary data with audited conversion.
- `uv run pytest -q transactional/` passes before merging.
