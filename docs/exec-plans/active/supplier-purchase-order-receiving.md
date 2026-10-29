# Sprint procurement: suppliers, POs, goods receipts and replenishment

## Scope and data model

Migration `0016_supplier_procurement` adds:
- `Supplier`: stable unique code, name, optional contact and active status
- `PurchaseOrder`: unique reference, location, supplier, creating supervisor and date
- `PurchaseOrderLine`: product, ordered units, cumulative received units and unit **purchase cost** (minor NGN units). Unique product per order
- `GoodsReceipt`: order, delivery-note reference, received-by supervisor and globally unique retry key with request fingerprint
- `GoodsReceiptLine`: quantity and **OneToOne link** to the existing canonical `InventoryMovement`

A receipt never edits `Product.unit_price_minor` or creates a `Payment`, `Sale`, supplier invoice or creditor balance. Purchase unit cost is procurement metadata, separate from POS selling price. Open/partial/received purchase order status is calculated from remaining quantity rather than a separately mutable state.

The procurement receipt endpoint is the **only** pathway needed to add stock for a PO delivery. Do not also post that physical delivery as a manual inventory `RECEIVE`: that would count the stock twice.

## Supervisor endpoints

Every endpoint requires a session-authenticated, active, staff `POSOperator` with `SUPERVISOR` role plus access to the submitted location and terminal. CSRF applies to writes.

| Method and path | Action |
| --- | --- |
| GET/POST `pos/manage/suppliers/` | List first 100 active suppliers / register supplier |
| GET/POST `pos/manage/purchase-orders/` | List 50 recent orders at authorized location / create PO |
| GET `pos/manage/purchase-orders/<id>/` | Read PO with ordered, received and outstanding units |
| POST `pos/manage/purchase-orders/<id>/receive/` | Receive one or more PO lines; allow partial deliveries |
| GET `pos/manage/replenishment/?threshold=5` | Low-stock SKUs, outstanding PO quantities, uncovered reorder gap |

All endpoints are underneath `/api/transactional/`. For supplier/PO GET and POST, send `location_code` and `terminal_code`. Purchase order line creation takes `lines:[{"sku":"RICE-001","quantity":10,"unit_cost_minor":120000}]`; `unit_cost_minor` is kobo (100 kobo per naira).

Goods receipt POST example:
```json
{
  "location_code": "MAIN",
  "terminal_code": "MAIN-01",
  "reference": "GRN-2026-001",
  "idempotency_key": "GRN-2026-001-unique-attempt",
  "lines": [{"line_id": 12, "quantity": 5}]
}
```

**On the server**:
1. Lock PO, reject unauthorized location and check idempotency key/fingerprint before touching stock
2. Lock PO lines and reject quantity exceeding outstanding order balance
3. Lock product / location inventory rows; update `InventoryItem.quantity` atomically
4. Write `GoodsReceipt`, line records, matching `InventoryMovement(reason=PURCHASE)` and `AuditEvent`
5. A replay with the exact same key and payload returns its existing receipt without another stock increment; a conflicting payload returns HTTP 409

The procurement UI has supplier registration, line-delimited PO entry (`SKU, quantity, cost in naira`), a single outstanding line per receipt submission, and low-stock/replenishment figures. The API supports multiple receipt lines per request. A failed or uncertain receipt retains its idempotency key **in the current browser session only**; do not reload and retry with a new key before checking its status.

Replenishment computes `reorder_gap_units = max(0, threshold + 1 - on_hand - outstanding_PO)`. This is a threshold-based convenience estimate, **not** demand forecasting or an automatic reorder recommendation. The report includes up to 200 low-stock SKUs; high-stock products are not listed.

## Local verification

```bash
git status --short
git pull --ff-only origin feat/transactional-concurrency
cd services/api
uv run python manage.py migrate
uv run python manage.py makemigrations --check --dry-run
uv run python manage.py check
uv run python -m pytest transactional/tests/test_supervisor_procurement.py -q --reuse-db --create-db
uv run python -m pytest transactional/ -q --reuse-db
```

From repository root, run `npm run build`.

Test supervisor create supplier → PO with two SKUs → receive partial delivery → verify quantities and movement IDs → repeat same receipt key → complete remaining lines → inspect `RECEIVED` status. Test an over-receipt attempt and unauthorized cashier access. Confirm a product sold at POS decrements the same `InventoryItem` quantity receiving increased.

## Deployment limits

This phase does not include supplier banking data, automated supplier ordering, approval/dispatch workflow, invoice matching, accounts payable, purchase order amendment/cancellation, VAT, purchase costing valuation, supplier portal, return-to-vendor, bulk imports, PO PDFs or automatic scheduled replenishment alerts. Production rollout requires staff workflow approval, a multi-session concurrency test, backup and migration verification, and UI hardware testing.
