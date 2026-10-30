# Inventory stocktaking, low-stock monitoring and reporting

This milestone extends the existing canonical inventory ledger and supervisor API. No duplicate inventory balance table or new migration is introduced.

## Interfaces

- `GET /api/transactional/pos/manage/inventory-report/?location_code=MAIN&terminal_code=MAIN-01&threshold=5&mode=low`
- `mode=all` lists active NGN products, including zero-stock products without an InventoryItem row.
- Default threshold is five units, inclusive (`quantity <= threshold`). The API returns a maximum of 200 SKUs sorted by SKU; this is a first-page operational report, **not** an exhaustive export.
- Supervisor panel has an editable low-stock threshold, a Refresh report button and a Stocktake action on each SKU. These are refresh-based indicators, **not** scheduled push alerts.

### Reconcile physical count safely

The stocktake action captures the current inventory quantity as `expected_quantity`. A discrepancy is submitted through the existing `POST /pos/manage/stock/` endpoint as `operation=ADJUST`, signed `quantity=(physical_count - expected_quantity)`, with the baseline, count-sheet reference, notes and idempotency key.

The backend obtains a row-level inventory lock and compares `expected_quantity` with the current database stock **inside the transaction**. If it differs, HTTP 409 `stock_changed_since_count` is returned with `current_quantity`, and no movement or balance change occurs. This prevents stocktake adjustments from overwriting a concurrent sale or stock receipt that updated the balance since the count was reviewed. Staff should recount / investigate and reload the report before retrying with a fresh baseline.

Successful adjustments use `InventoryMovement(reason=ADJUSTMENT)`, `StockOperation` idempotency records and `AuditEvent` with the supplied count-sheet notes.

**Limitations:** These baseline counts are snapshots of the report, not physically timed counts; conduct controlled physical stocktakes (for example closing the area or using count sheets) to avoid mixing in sales during counting. Current management UI stores unfinished request keys only in browser memory; refresh or restart requires investigation before repeating uncertain writes. A production-grade stocktake session, pagination, supplier reordering, alert scheduling and inventory valuation are future increments.

## Verification

From repository root:
```bash
git status --short
git pull --ff-only origin feat/transactional-concurrency
cd services/api
uv run python manage.py migrate
uv run python manage.py makemigrations --check --dry-run
uv run python -m pytest --reuse-db --create-db -q transactional/tests/test_supervisor_stocktake_report.py
uv run python -m pytest --reuse-db -q transactional/
uv run python manage.py check
```
Then, from repo root, `npm run build`.

Test a supervisor session with stocked and zero-stock SKUs, change the threshold, refresh inventory report, and record a physical count discrepancy using a count-sheet reference. Verify the `current_quantity` conflict if stock changes after loading the report and before submitting.

Code was committed remotely; local migration/test/build execution remains a release gate.
