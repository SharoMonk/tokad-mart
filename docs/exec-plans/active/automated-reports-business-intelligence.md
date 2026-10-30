# Automated Reporting & Business Intelligence

## Implemented in this milestone

- `0020_scheduled_management_reports`: stores per-location management report schedules and an immutable-per-period execution history
- `GET /api/transactional/pos/manage/report-xlsx/`: directly downloads a real .xlsx file for the selected authorized store and date range (up to 32 inclusive days)
- `GET/POST /api/transactional/pos/manage/report-schedules/`: list/create DAILY or WEEKLY report schedules for an **administrator-allowlisted** email recipient
- `POST /api/transactional/pos/manage/report-schedules/<id>/disable/`: creator-only disable operation
- `GET /api/transactional/pos/manage/bi-insights/`: completed-sales daily trend, top 20 selling SKU/name snapshots, and first 50 low-stock SKUs (current balances)
- `run_scheduled_reports` Django management command: execute due schedules after a period closes and record results

Every HTTP report endpoint requires an active supervisor assigned to the requested active location and terminal. Existing enterprise CSV exports remain available.

## Schedule periods

A daily report executed on day D covers **D-1**, not an in-progress current-day total. A weekly report executed on **Monday** covers the prior Monday through Sunday. All report periods use Django's Africa/Lagos local timezone configuration.

Reports are one store per email. They include an Excel operational summary with completed sales, closed shifts, cashier variance, and approved-expense figures. This is not a profit-and-loss report, bank balance, or financial statement.

### Email delivery is deliberately disabled by default

The server administrator must configure:
```env
TOKAD_REPORT_DELIVERY_ENABLED=1
TOKAD_REPORT_ALLOWED_EMAILS=manager@example.com,reviewer@example.com
DJANGO_EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
DJANGO_DEFAULT_FROM_EMAIL=reports@example.com
DJANGO_EMAIL_HOST=smtp.example.com
DJANGO_EMAIL_PORT=587
DJANGO_EMAIL_USE_TLS=1
DJANGO_EMAIL_HOST_USER=<SMTP ACCOUNT>
DJANGO_EMAIL_HOST_PASSWORD=<SMTP SECRET>
```
The addresses and SMTP values above are placeholders; **do not deploy them verbatim**. Store secrets in your server's protected environment, never in the repository. Use an SMTP provider you control, confirm domain authentication and privacy requirements, and approve each recipient in the env allowlist. The recipient allowlist is rechecked during execution to honor revocations. The worker rejects console/dummy/test backends so a development log cannot be mistaken for actual delivery.

After configuration, install a single process scheduler (cron or systemd timer) to invoke this **once per day, shortly after midnight in Africa/Lagos**:
```bash
cd /path/to/tokad-mart/services/api
uv run python manage.py run_scheduled_reports
```
No cron job, SMTP credentials, email connector, or automatic task was configured by the GitHub commits alone. Until you install this external schedule and set the required environment, schedules **will not send anything**.

### Delivery semantics and history

A unique constraint on `(schedule_id, period_end)` prevents more than one **delivery attempt** for each scheduled period even if two workers run concurrently. A previous failure or process crash can leave a `FAILED` or `CLAIMED` record. Such periods **are not automatically resent**, because the SMTP server might have accepted a message before the process lost its response. Administrators must verify the external delivery status and investigate before creating any manual resend workflow.

`SUCCEEDED` only means the SMTP/email backend accepted one message; it is **not proof of inbox delivery or that the message was read**. `CLAIMED` may indicate a crash, not completion.

## Excel report format

The .xlsx workbook is generated using Python's standard library without introducing an additional dependency or lockfile change. It uses explicit data cells (never Excel formulas), bold column headers and fixed widths. Monetary figures are stored as integers of **NGN minor units (kobo)**, not automatically guessed exchange rates. For rich multi-tab Excel dashboards and charts, a later iteration can introduce a spreadsheet library with coordinated dependency-lockfile updates.

## BI metrics

The BI endpoint uses the selected date window (maximum 32 inclusive days), and only completed NGN sales associated with the selected store. Daily trends include date, count and gross recorded sales; product rankings use snapshots from `SaleLine`, not current product names. Low-stock balances are **current**, not the historical period-end balances. Sales figures are not margins, tax-adjusted revenues, or bank deposits.

## Local verification / release gates

At repository root:
```bash
git status --short
git pull --ff-only origin feat/transactional-concurrency
cd services/api
uv run python manage.py migrate
uv run python manage.py makemigrations --check --dry-run
uv run python manage.py check
uv run python -m pytest -q --reuse-db --create-db transactional/tests/test_report_scheduling.py transactional/tests/test_store_bi.py
uv run python -m pytest -q --reuse-db transactional/
cd ../..
npm run build
```

Acceptance includes: supervisor can download and open the .xlsx workbook in Excel/LibreOffice; cashier and unassigned supervisors cannot access; recipient not allowlisted is rejected; successful schedule creation displays in history; duplicate worker executions do not send twice; revocation prevents later sends; supervisor can disable own schedule; BI counts match known completed sales, and low-stock watchlist reflects physical inventory.

No tests or backend migrations have been executed in the user's local environment by these commits. Do not deploy until those checks pass.
