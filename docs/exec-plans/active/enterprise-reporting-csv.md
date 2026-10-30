# Enterprise reporting — multi-location KPIs and CSV exports

This milestone provides read-only operational reporting across **active store locations explicitly assigned to the authenticated supervisor**. It adds **no migration** and does not alter existing inventory, cashier sales, payment or supplier accounting records.

## New endpoints

All routes begin `/api/transactional/` and use authenticated, active staff POS supervisor role checks:

| Method | Path | Returns |
| --- | --- | --- |
| GET | `pos/manage/enterprise-summary/?start=2026-10-01&end=2026-10-30` | Combined KPI totals plus one row per authorized location |
| GET | `pos/manage/enterprise-export/?start=2026-10-01&end=2026-10-30&report_type=daily` | CSV of store totals |
| GET | Same path with `report_type=closing` | CSV of closed cashier shift summaries and variance/review status |
| GET | Same path with `report_type=stock` | Current stock units and selling price (minor NGN units) for active products by location |

The optional `location_code=MAIN` restricts results to one assigned store. If the requested location isn't assigned and active, access is rejected; leaving it absent means **all assigned active locations**. A supervisor does not receive global access solely due to their role. The 32-day inclusive date window matches the finance dashboard's existing date validation.

Use the existing financial dashboard date controls in the supervisor POS and the new *Enterprise reporting and store performance* panel to view totals and download reports. Exports are standard UTF-8 CSV and can be opened in Excel; an actual formatted `.xlsx` workbook is **not yet implemented**.

### Metric definitions

- `completed_sales`: count of NGN Sales in COMPLETED state whose `completed_at` date falls in the requested window.
- `gross_sales_minor`: sum of Sale.total_minor over those sales. **Not** net revenue, cash collected, verified deposits or profit.
- `closed_shifts`: closed shifts whose closing date is within the selected period.
- `cashier_variance_minor`: summed `closing_cash_minor - expected_cash_minor` for closed shifts with both values; unresolved or unknown amounts are excluded.
- `approved_expenses_minor`: sum of expenses with an APPROVED independent review and incurred dates in the range.
- Stock CSV shows **current quantities**, not historic snapshot balances at the date filter. It includes zero-stock product rows.
- Closing CSV provides shift-specific expected and counted cash figures and independent review status.

CSV string cells beginning with `=`, `+`, `-`, or `@` (also following leading whitespace) are escaped to reduce spreadsheet formula injection. Numeric negative variance values are preserved.

## Scheduling boundary

This milestone adds **on-demand** CSV downloads only. No cron schedules, email sends, recurring automated jobs, or delivery connectors were configured. For scheduled reporting, a later release should add a per-store reporting schedule, execution history, approved recipient management, secure distribution, and retries. Do not claim that the application sends daily or weekly automatic reports yet.

## Local validation

Run at the repository root:

```bash
git status --short
git pull --ff-only origin feat/transactional-concurrency
cd services/api
uv run python manage.py migrate
uv run python manage.py makemigrations --check --dry-run
uv run python manage.py check
uv run python -m pytest -q --reuse-db --create-db transactional/tests/test_enterprise_reporting.py
uv run python -m pytest -q --reuse-db transactional/
cd ../..
npm run build
```

Verify a supervisor assigned to STORE-A only cannot access STORE-B data, then assign the supervisor STORE-B to verify expansion is deliberate. Open all three CSV exports in Excel, verify formula-safe product names and negative numeric variances, and confirm POS cash transactions and inventory checkout are not altered by reporting.

The GitHub commits have been written, but Django migration, automated tests, Next.js build, and browser testing **have not been run in the local deployment environment**.
