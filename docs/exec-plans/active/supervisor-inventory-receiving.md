# Inventory receiving and controlled stock adjustments

This milestone extends Tokad Mart's canonical inventory ledger without introducing a parallel stock balance.

**Endpoint:** `POST /api/transactional/pos/manage/stock/`. Requires Django session authentication, CSRF protection, an active supervisor profile, and a location/terminal assigned to that supervisor.

Example receiving payload:

```json
{
  "location_code": "MAIN",
  "terminal_code": "MAIN-01",
  "sku": "DEMO-RICE-001",
  "operation": "RECEIVE",
  "quantity": 20,
  "reference": "SUPPLIER-INVOICE-100",
  "notes": "Twenty units counted and received",
  "idempotency_key": "receive-2026-10-29-invoice-100-rice"
}
```

Operations:
- `RECEIVE`: positive quantity only; creates `InventoryMovement(reason=PURCHASE)`.
- `ADJUST`: nonzero signed delta; creates `InventoryMovement(reason=ADJUSTMENT)`. The resulting stock must never become negative.
- Each operation locks the product and inventory row within the same database transaction and records a linked `StockOperation` with a unique idempotency key and payload fingerprint, plus an `AuditEvent`. This preserves exactly-once database effects when requests are retried with the **same** key. Concurrency is coordinated with existing POS checkout row locks.
- Product registration continues to create no stock until explicit receiving is recorded.
- Supervisor UI supports receipts and signed stock adjustments using the original key on retry. Reloading the page loses the current in-memory key; investigate uncertain writes before resubmitting.

**Important operational boundary:** This is not a supplier-payables or purchase-order subsystem. It records stock receipt references but does not create procurement invoices, cost accounting, VAT, or automatic cash movement. Negative adjustments require operational authorization and supporting explanations.

## Verify

```bash
git status --short
git pull --ff-only origin feat/transactional-concurrency
cd services/api
uv run python manage.py migrate
uv run python manage.py makemigrations --check --dry-run
uv run python -m pytest -q --reuse-db --create-db transactional/tests/test_supervisor_inventory_management.py -vv
uv run python -m pytest -q --reuse-db transactional/
uv run python manage.py check
```

In the repository root run `npm run build`.

In the browser sign in as an assigned supervisor, create a test product, and use **Supervisor stock receiving and adjustment** to receive 20 units. The catalogue and scanner lookup should then show stock 20, and a cash sale should decrement that same InventoryItem. Verify repeated receiving with the same request key does not add stock twice and that a negative adjustment beyond available stock is rejected.

**Release gates:** production deployment still needs a real multi-user concurrency test, operational role acceptance, stocktake reconciliation procedures and device testing. Neither GitHub commits nor this document assert local tests were executed.
