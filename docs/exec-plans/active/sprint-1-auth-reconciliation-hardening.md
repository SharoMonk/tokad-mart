# Sprint 1 — cashier authentication and reconciliation hardening

## Implemented

- POS login failures are counted by both account and direct peer IP, with hashed cache keys. Default threshold: 5 failures within 900 seconds; blocked attempts return HTTP 429. The login endpoint does not trust client-supplied forwarded IP headers.
- Successful login starts a server-enforced inactivity clock. POS requests after the configured idle period expire the Django session (default 900 seconds).
- Closed shift reconciliation refuses incomplete or cash-payment-mismatched canonical Sale records. Closing cash variance can still be nonzero and is audited.
- No parallel inventory, sales, or payment tables were introduced.

## Database cache preparation for production

Development defaults to in-process LocMemCache, so throttling only covers one development process. Production defaults to Django DatabaseCache, shared through the existing PostgreSQL connection.

Before starting production workers, provision the cache table:

```bash
cd services/api
DJANGO_DEBUG=0 uv run python manage.py createcachetable
```

The database user needs table-creation privileges for setup, or a separate privileged deployment migration step. Use a shared, correctly provisioned cache for all API workers; otherwise fail startup rather than running without enforcement. Django's database cache increment operations are not a fully atomic distributed rate limiter under concurrency: **an atomic Redis-backed limiter is a remaining production hardening requirement**.

Environment settings:
- `POS_LOGIN_MAX_FAILURES` (default `5`)
- `POS_LOGIN_WINDOW_SECONDS` (default `900`)
- `POS_SESSION_IDLE_SECONDS` (default `900`)
- `POS_SESSION_AGE_SECONDS` (default `28800`)
- `POS_LOGIN_CACHE_TABLE` (default `pos_login_throttle_cache`)

The inactivity check runs server-side when an authenticated POS endpoint is accessed; there is no timer background worker to proactively log out idle open browser tabs. Do not treat a browser inactivity popup as a substitute for the server-side timeout.

## Verify

```bash
cd services/api
uv sync --extra dev
uv run python -m pytest -q transactional/tests/test_pos_auth_and_reconciliation_guards.py -vv
uv run python -m pytest -q transactional/tests/test_pos_session_shift_flow.py -vv
uv run python -m pytest -q transactional/
uv run python manage.py check
```

Test with a running frontend afterward: log in, open shift, checkout, then close shift with the calculated cash count. Failed login attempts must be limited and an idle session must require reauthentication. Review the terminal/log output for CSRF and proxy cookie issues.

Production gates still outstanding: stronger shared-cache atomic login limiter, account lockout operations and observability, correct trusted proxy/IP configuration, per-terminal operator inactivity controls, secure credential recovery and supervisor override workflow, HTTPS/deployment checks and Paystack endpoint authentication review.
