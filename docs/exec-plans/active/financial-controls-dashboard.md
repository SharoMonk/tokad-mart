# Financial controls and supervisor reporting dashboard

This milestone introduces a **location-scoped operational dashboard**, manual operating expenses and an independent expense-review trail.

## Schema and workflow

Migration `0019_expense_controls` adds:
- `StoreExpense`: globally unique reference, store location, category, description, amount in minor NGN units, incurred date, recording supervisor, timestamp.
- `ExpenseReview`: one-to-one immutable decision (APPROVED / REJECTED), reviewer, notes, timestamp.

A different assigned supervisor must review each expense. The expense is *not* a bank payment, payment-provider transaction, accounting posting, or automatically cash-deducted POS entry. References are unique and replaying the same form fails closed with HTTP 409 rather than adding an expense twice.

## API and access

All paths are relative to `/api/transactional/` and use cookie session authentication, DRF supervisor/operator checks and the caller's assigned location/terminal scope.

| Method | Path | Action |
| --- | --- | --- |
| GET | `pos/manage/financial-dashboard/?location_code=MAIN&terminal_code=MAIN-01&start=2026-10-01&end=2026-10-30` | Location-scoped operational summary |
| GET / POST | `pos/manage/expenses/` | List up to 100 expenses / add expense |
| POST | `pos/manage/expenses/<id>/review/` | Independent decision with required notes |

Write an expense with:
```json
{
  "location_code": "MAIN",
  "terminal_code": "MAIN-01",
  "reference": "EXP-2026-001",
  "category": "Electricity",
  "description": "Generator fuel",
  "amount_minor": 450000,
  "incurred_on": "2026-10-30"
}
```

Review:
```json
{
  "location_code": "MAIN",
  "terminal_code": "MAIN-01",
  "decision": "APPROVED",
  "notes": "Receipts checked against expense request"
}
```

## Dashboard semantics

Reports accept ISO dates with a maximum inclusive window of 32 days. Completed NGN sales are grouped by the `Sale.completed_at` calendar date. The gross sales figure is **not** verified payment proceeds, net profit, bank deposits, or a cash flow statement. It does not subtract refunds or discounts beyond those already recorded in sale totals.

Cashier variances are derived from CLOSED shifts using `closing_cash_minor - expected_cash_minor`; review status is shown independently.

Expenses show totals for APPROVED and PENDING-review entries by their **incurred date**. Rejected expenses do not contribute to approved totals.

Supplier invoice exposure shows invoices **recorded** during the report period with manual verified and pending supplier payment evidence. It is not a bank-confirmed unpaid balance and is not tied to completed POS sales. Supervisor access is limited to one assigned store location at a time.

The shift list is bounded at 100 recent closed shifts. Expense GET is bounded at 100. Large-scale invoice/report paging, bank reconciliation, scheduled exports, expense reversal workflows, closing periods, VAT and true profit & loss are future increments.

## Local verification

From repository root:
```bash
git status --short
git pull --ff-only origin feat/transactional-concurrency
cd services/api
uv run python manage.py migrate
uv run python manage.py makemigrations --check --dry-run
uv run python manage.py check
uv run python -m pytest -q --reuse-db --create-db transactional/tests/test_financial_dashboard.py
uv run python -m pytest -q --reuse-db transactional/
cd ../..
npm run build
```

In the UI: log in as a supervisor, select a location and reporting date window; refresh the financial dashboard; record an expense; sign in as a **different** supervisor with permission to that location to approve or reject it. Refresh the dashboard and confirm approved totals change, while pending totals decrease. Verify cashier accounts cannot see these endpoints.

**Release gate:** These changes are committed remotely, but local tests and frontend build have not been run in this workflow. Review and fix any failures before deploying.
