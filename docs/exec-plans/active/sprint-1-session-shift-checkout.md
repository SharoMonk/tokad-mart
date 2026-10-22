# Sprint 1 — session cashier authentication and shift-bound cash checkout

## Architecture

Canonical backend: `services/api/transactional`. Frontend: `components/CanonicalPOS.tsx`.
This builds on existing `CashierShift`, `shift_services.py`, `shift_api.py`, and migration `0011_cashier_shift.py`; it does not create a second ledger.

New routes:
- `GET /api/transactional/pos/session/`: sets CSRF cookie and returns session status
- `POST /api/transactional/pos/login/`: validates cashier credentials and creates Django HttpOnly session
- `POST /api/transactional/pos/logout/`: destroys session
- `GET|POST /api/transactional/pos/shifts/`: active shift lookup / opening
- `POST /api/transactional/pos/shifts/<id>/close/`: close shift, calculate expected cash
- `POST /api/transactional/pos/shift-sales/`: session-authenticated shift-bound cash sale

The existing `/pos/sales/` is temporarily retained for API compatibility and current regression coverage. **Only the new `shift-sales/` endpoint enforces open shift ownership**, so the older endpoint must be retired or protected before production release. The new client uses `shift-sales/` exclusively.

## Local setup

```bash
git pull --ff-only origin feat/transactional-concurrency
cd services/api
uv sync --extra dev
uv run python manage.py migrate
uv run python -m pytest -q transactional/tests/test_pos_session_shift_flow.py -vv
uv run python -m pytest -q transactional/
uv run python manage.py runserver 127.0.0.1:8001
```

In a separate terminal, from the repository root:

```bash
TRANSACTIONAL_API_ORIGIN=http://127.0.0.1:8001 npm run dev
```

At http://localhost:3000 log in as the demo cashier, open a shift (opening cash is entered in naira), perform a cash sale, inspect the receipt, and close the shift after clearing the cart. Expected cash equals opening cash plus successful cash payments attached to this shift.

Sessions are cookies (HttpOnly, SameSite Lax), while JavaScript sends the non-HttpOnly CSRF cookie value in `X-CSRFToken` for state-changing requests. Django rotates the CSRF cookie after login; always read it fresh. No Basic auth credentials are retained in browser storage.

## Security and unfinished production gates

- Use HTTPS, a strong `DJANGO_SECRET_KEY`, explicit `DJANGO_ALLOWED_HOSTS` and `DJANGO_CSRF_TRUSTED_ORIGINS`, secure cookies, and a real deployment authentication/rate-limiting policy.
- The basic-auth legacy API route and read endpoints still accept BasicAuthentication; disable Basic on all cashier endpoints before exposing the system publicly.
- The Next.js rewrite and Django proxy must share the browser-origin cookie domain; verify all CSRF and Set-Cookie behavior on actual deployment origin.
- Ensure a production session length, inactivity timeout, failed-login throttling, session revocation, and cashier logout-on-shift-close policy.
- First-time login will not automatically create a shift. Opening and closing cash amounts are integer minor units on the API, and naira amounts in the frontend.
- Existing `Sale.shift` is nullable for compatibility with earlier sales. New `shift-sales/` attaches each sale to a locked open shift atomically.
- Existing shifts and model migration `0011_cashier_shift.py` are already in this branch. Do not create a new parallel CashierShift table.
- Tests are committed but must be run locally against PostgreSQL; GitHub edit actions do not execute pytest or a Next build.
