# Sprint 1 — cashier expiry, supervisor reconciliation, and Redis limiter

## Overview

Cashier session expiry is displayed by the Next.js POS. It retains an unresolved cart and its checkout idempotency key in memory so the cashier can log back in and retry safely. It does **not** persist unresolved attempts across a full page reload, browser close, or machine restart; investigate the sale ledger before recreating an uncertain transaction.

New supervisor API: `GET|POST /api/transactional/pos/shifts/<shift_id>/review/`. It requires a valid Django session, an active assigned POS supervisor, and a shift operated by somebody else. POST body:

```json
{"decision": "APPROVED", "notes": "Drawer counted against completed sales."}
```

Only closed shifts can be reviewed, each shift can be reviewed once, and audit history is written to canonical `AuditEvent`. The supervisor cannot edit cashier-reported cash, expected cash, or the original variance. Migration: `0012_shift_reconciliation_review.py`. Supervisor POS view provides a minimal review submission panel.

Production rate limiting now uses Redis and a single Lua script to atomically reserve both account and IP quotas **before** credential verification. Default account allowance is 5 attempts per 900-second fixed window; source IP allowance 50 attempts per window. A successful login clears only the account quota, not the IP quota. In development with no Redis URL the original in-memory failure limiter is retained to avoid external infrastructure during tests. Configure `POS_LOGIN_REDIS_URL` for production and **do not expose** a development-mode POS to public networks. Reverse proxy MUST set the client address correctly in `REMOTE_ADDR`; this app does not trust unvalidated forwarded headers.

## Commands

```bash
cd services/api
uv sync --extra dev
uv run python manage.py migrate
uv run python -m pytest -q --reuse-db --create-db \
  transactional/tests/test_supervisor_shift_review.py \
  transactional/tests/test_redis_login_throttle.py \
  transactional/tests/test_pos_auth_and_reconciliation_guards.py \
  transactional/tests/test_pos_session_shift_flow.py
uv run python -m pytest -q --reuse-db transactional/
uv run python manage.py check
```

From the Next.js root, run `npm run build` and restart Next.js against the local Django API. Test login/session timeout recovery with an unresolved checkout and review an already closed shift from a distinct assigned supervisor account.

## Deployment controls

- Redis should be dedicated or namespace-isolated, reachable over authenticated TLS (use `rediss://` when appropriate); limit network access and configure HA, persistence and monitoring. An unavailable Redis instance causes login errors rather than bypassing throttling. `POS_LOGIN_REDIS_URL` is mandatory outside DEBUG.
- For deployments use `DJANGO_DEBUG=0`, HTTPS, secure cookies, strong secret key, explicit allowed hosts, CSRF trusted origins and a production WSGI/ASGI server. Do not use Django's development server or share credentials between cashier accounts.
- Redis atomic counters are shared across app workers. Client-IP accuracy depends on trusted proxy configuration and MUST be verified. 50 attempts per IP can affect NAT-shared locations; configure thresholds for your topology.
- The login limiter is fixed-window rather than adaptive credential-stuffing detection; central logging and incident alerts are still recommended.
- Migration and tests have been committed but not executed from GitHub editing tools; local verification required.
