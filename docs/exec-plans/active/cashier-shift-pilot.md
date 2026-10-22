# Sprint 1 — cashier shift pilot

This phase adds `CashierShift` records to the **canonical** `services/api/transactional` database and associates shift-aware cash sales with the existing `Sale`, `Payment`, and `InventoryMovement` records. It does not create another financial or stock ledger.

## Pull and verify

From the repository root, preserve your local changes before pulling. Generated `.next/` and `node_modules/` should be locally ignored.

```bash
git status --short
git pull --ff-only --no-rebase origin feat/transactional-concurrency
cd services/api
uv sync --extra dev
uv run python manage.py migrate
uv run python manage.py makemigrations --check --dry-run
uv run --extra dev python -m pytest transactional/tests/test_cashier_shifts.py -vv
uv run --extra dev python -m pytest -q transactional/
```

From the repository root:

```bash
npm run build
TRANSACTIONAL_API_ORIGIN=http://127.0.0.1:8001 npm run dev
```

Use the port of your running canonical Django backend, not the legacy Docker backend.

## Browser acceptance

1. Log in with `demo_cashier`, select `MAIN` / `MAIN-01`.
2. Open a shift with ₦1,000 opening cash.
3. Search Demo Rice and sell two units: ₦7,000.
4. View the receipt and check the sale reference and ₦7,000 total.
5. Close the shift with ₦8,000 counted cash. Expected cash is ₦8,000 and variance is zero.
6. Verify stock decreases exactly once and that a new cash checkout is blocked when the shift is closed.

## Endpoints

- `GET /api/transactional/pos/shifts/?location_code=MAIN&terminal_code=MAIN-01`
- `POST /api/transactional/pos/shifts/` with `{ "location_code":"MAIN", "terminal_code":"MAIN-01", "opening_cash_minor":100000 }`
- `POST /api/transactional/pos/shifts/<id>/close/` with `{ "closing_cash_minor":800000 }`
- `POST /api/transactional/pos/sales/` accepts optional positive integer `shift_id`, used by the new Next.js browser interface.

## Limitations and further work

**Pilot, not production.** Authentication still uses HTTP Basic credentials in browser memory. Replace with secure same-origin sessions, CSRF protection and deployment hardening before public access. For compatibility, older API clients may still omit `shift_id`; a mandatory shift policy is not enforced globally until callers and tests are migrated. A shift close currently sums successful cash payments for completed sales linked to that shift; cash refunds, payouts, deposits, starting cash verification, and supervisor reconciliation still need dedicated transaction types and audit rules. Do not use cash variance as final financial accounting until those workflows exist.
