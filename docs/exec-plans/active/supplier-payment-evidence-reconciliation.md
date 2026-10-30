# Supplier payment evidence, independent review and finance reconciliation

## Scope

Migration `0018_supplier_payment_evidence` adds `SupplierPaymentEvidence` to associate external supplier payment references with a matched `SupplierInvoice`. There is **no** bank transfer, financial provider integration, automatic bank reconciliation, external confirmation, general-ledger posting or proof of settlement implemented. A supervisor must inspect evidence from the bank/accounting system before entering it.

Evidence is recorded as `RECORDED` and only becomes `VERIFIED` when a **different supervisor** manually reviews it and supplies a note. The application cannot determine if the external transaction was reversed or forged.

## APIs

All endpoints are underneath `/api/transactional/`, require authenticated Django session + CSRF on writes, active `SUPERVISOR` POS operator and assigned location + terminal.

| Method | Endpoint | Purpose |
| --- | --- | --- |
| GET/POST | `pos/manage/supplier-payments/` | List payment evidence or add reference |
| POST | `pos/manage/supplier-payments/<id>/verify/` | Second-person manual verification |
| GET | `pos/manage/supplier-reconciliation/` | Manual evidence by matched/exception invoice |
| GET | `pos/manage/accounts-payable/` | Updated invoice exposure + review statuses |

Example recorded evidence:
```json
{
  "location_code": "MAIN",
  "terminal_code": "MAIN-01",
  "invoice_id": 10,
  "reference": "EXTERNAL-BANK-TRANSACTION-001",
  "amount_minor": 350000,
  "notes": "Bank account statement transaction reviewed externally",
  "idempotency_key": "supplier-payment-attempt-001"
}
```

A repeated request with the same idempotency key and unchanged content returns `replayed=true` without double-recording; conflicting data or another external reference collision returns HTTP 409. The invoice is locked in the same database transaction while checking previously recorded amounts to avoid duplicate reservations. Maximum cumulative recorded/verified evidence for an invoice cannot exceed that invoice's `amount_minor`. Invoices with `status=EXCEPTION` cannot have payment evidence posted until the exception is resolved in a future controlled workflow.

Second supervisor verification:
```json
{"location_code":"MAIN","terminal_code":"MAIN-01","notes":"Compared reference, payer and amount against independently sourced bank statement"}
```

## Reporting semantics

`verified_evidence_minor`: externally sourced payment evidence **manually checked** by a second supervisor.

`pending_review_minor`: evidence recorded but not independently reviewed.

`remaining_unverified_minor`: invoice face amount minus verified evidence. It is **not** a bank-confirmed amount due or a legally established payable balance.

`uncovered_minor`: invoice amount minus verified and pending evidence.

`review_status`: `EXCEPTION`, `UNRECORDED`, `PENDING_REVIEW`, `PARTIAL`, or `MANUALLY_RECONCILED`.

Lists currently show up to 100 evidence records and up to 200 invoices. This is not a complete financial ledger, payment initiation system, or authoritative monthly financial statement. Bank-statement imports, chargebacks, partial discrepancies, exception resolution, VAT and invoice-credit notes are future work.

## Local release checks

```bash
git status --short
git pull --ff-only origin feat/transactional-concurrency
cd services/api
uv run python manage.py migrate
uv run python manage.py makemigrations --check --dry-run
uv run python manage.py check
uv run python -m pytest -q --reuse-db --create-db transactional/tests/test_supplier_payment_evidence.py
uv run python -m pytest -q --reuse-db transactional/
cd ../..
npm run build
```

Acceptance checks:
1. Supervisor A registers evidence on a matched invoice; cashier is rejected
2. Submitting identical evidence under the same idempotency key returns replay without another record
3. A different key with an existing external transaction reference or cumulative amount exceeding the invoice is rejected
4. Exception invoices cannot receive payment evidence
5. Supervisor A cannot independently verify their own evidence; supervisor B can
6. AP exposure distinguishes recorded, manually verified and uncovered amounts without claiming bank confirmation
7. Cash POS sales, product receiving, stocktake, and PO approvals remain unaffected

No local run of Django tests or Next.js build has been performed as part of these GitHub commits.
