# Purchase-order approval, invoice matching and AP exposure — acceptance plan

## Purpose

Extend the supplier / PO / goods receipt workflow without pretending that invoice registration is a payment or a completed accounting ledger.

Migration `0017_procurement_approval_invoice` adds:
- `PurchaseOrderApproval`: one-to-one immutable approval, actor, note and timestamp. PO creator cannot approve their own PO. A second assigned supervisor must approve before a **new** goods receipt is accepted.
- `SupplierInvoice`: supplier, one-to-one goods receipt, unique supplier invoice number, claimed amount and calculated expected amount in minor NGN units, MATCHED or EXCEPTION, reviewer and review notes.

### Workflow and endpoints

All endpoints are under `/api/transactional/`, use cookie session + CSRF for writes, and enforce supervisor role **and** assigned location and terminal.

| Endpoint | Method | Operation |
| --- | --- | --- |
| `pos/manage/purchase-orders/<id>/approve/` | POST | Second-person approval with `note` |
| `pos/manage/purchase-orders/<id>/receive/` | POST | Existing receipt endpoint now rejects unapproved POs |
| `pos/manage/supplier-invoices/` | POST/GET | Record or list invoices linked to one goods receipt |
| `pos/manage/accounts-payable/` | GET | Read-only, location-scoped supplier invoice exposure |

Sample approval body:
```json
{"location_code":"MAIN","terminal_code":"MAIN-01","note":"Supplier, price and quantities reviewed"}
```

Sample invoice matching body:
```json
{"location_code":"MAIN","terminal_code":"MAIN-01","receipt_id":12,"number":"INV-001","amount_minor":150000,"notes":"Delivery note and invoiced quantities checked"}
```

**Match rule:** each invoice represents precisely one goods receipt, and its expected value is `SUM(GoodsReceiptLine.quantity * PurchaseOrderLine.unit_cost_minor)`. The associated purchase order identifies supplier and SKU; the receipt provides actual accepted quantities. Equal amounts produce MATCHED, differing amounts produce EXCEPTION, **never silently alter the invoice or stock**. Duplicate invoice numbers per supplier or a second invoice against the same goods receipt are rejected. VAT, freight and discounts are not modeled separately, so documents containing those charges will remain exceptions until a richer invoice schema is implemented.

For printing, supervisor selects a PO in the browser and uses **Print / Save as PDF**. This uses the browser's print/PDF capability; it is **not** a server-generated or digitally signed purchase order PDF.

### Accounts payable limitations

`accounts-payable/` lists invoices and two exposure totals, MATCHED and EXCEPTION. All rows show `payment_status=NOT_TRACKED`. This is a **preliminary supplier invoice register**: the system cannot ascertain whether amounts are unpaid because no verified supplier payment transactions, remittances or general-ledger postings have been implemented. Do not use the exposure totals as actual accounts payable balances or initiate supplier transfers based only on this report.

### Legacy approval limitation

Purchase orders with goods receipts created **before** approval enforcement cannot be retroactively approved via the ordinary endpoint. They require a documented supervisory migration/reconciliation decision, not a silent backfill. Existing open orders without receipts can be approved by another supervisor. Ensure two independent active supervisor accounts with assigned POS scopes before using this feature.

### Verification

From repo root:
```bash
git status --short
git pull --ff-only origin feat/transactional-concurrency
cd services/api
uv run python manage.py migrate
uv run python manage.py makemigrations --check --dry-run
uv run python manage.py check
uv run python -m pytest -q --reuse-db --create-db transactional/tests/test_procurement_approval_invoice.py transactional/tests/test_supervisor_procurement.py
uv run python -m pytest -q --reuse-db transactional/
```
From repo root: `npm run build`.

Acceptance sequence: supervisor A creates PO; supervisor A cannot approve; cashier cannot approve; supervisor B approves; receive partial delivery with delivery note; match invoice against the displayed receipt ID; verify equal amount → MATCHED and mismatch → EXCEPTION; duplicates rejected; observe the AP register displays NOT_TRACKED and no real payment is created; print approved PO to PDF using the browser; check POS cash sales and receipt printing still behave correctly.

All GitHub edits are committed but **local tests, migrations, production security review and frontend build have not been run by this authoring workflow**.
