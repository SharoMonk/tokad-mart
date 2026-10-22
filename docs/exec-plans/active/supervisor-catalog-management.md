# Supervisor catalog management — implementation and acceptance

## Implemented
- POST /api/transactional/pos/manage/products/ — create canonical NGN product (SKU, name, positive unit_price_minor). Product starts **without inventory**. Cashier sale and stock workflows are unchanged.
- GET /api/transactional/pos/manage/products/?sku=...&location_code=...&terminal_code=... — supervisor-authorized exact SKU lookup.
- GET/POST /api/transactional/pos/manage/products/<product_id>/barcodes/ — list/add physical barcode strings, preserving leading zeros. Idempotent retry for the same mapping; conflicts return 409.
- Existing session authentication, CSRF enforcement, POS operator role, and assigned location/terminal scope apply on the backend to every management operation.
- New UI appears only for supervisor sessions, but backend authorization does **not** rely on UI visibility.
- AuditEvent records created products and newly added barcodes. Changes do not generate inventory stock, Sale, SaleLine or Payment rows.

## Verify
```bash
git pull --ff-only origin feat/transactional-concurrency
cd services/api
uv run python manage.py migrate
uv run python -m pytest -q --reuse-db transactional/tests/test_supervisor_catalog_management.py -vv
uv run python -m pytest -q --reuse-db transactional/
uv run python manage.py check
uv run python manage.py makemigrations --check --dry-run
```
From repo root run `npm run build`.

To test the browser: sign in as an assigned supervisor; open product management, register a unique SKU/name/naira price, then enter that SKU and a manufacturer barcode to map it. Scan the barcode in an open cashier shift; it should resolve the product but report out-of-stock until an authorized inventory receiving workflow supplies stock. As a regular cashier, confirm that the management panel is absent, and backend POST requests remain forbidden.

## Scope and next gaps
This increment covers **new product registration and assigning physical codes**. It does not implement editing existing price/name/status, receiving stock, retail product import/export, changing/removing barcodes, or two-person approvals for catalog changes. Product prices should be reviewed before exposing to production users, and catalog changes should be restricted to trusted supervisors. No new database migrations were needed beyond prior `0013_product_barcode`.

All changes were committed to the feature branch. CI, Django tests, migrations and Next.js build must still be executed in a development environment.
