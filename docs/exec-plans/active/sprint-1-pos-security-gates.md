# Sprint 1 — protect the canonical cashier API

This milestone hardens the existing session-based POS without adding another sales, payments, or stock ledger.

## Changes

- `pos/scope/`, `pos/catalog/`, `pos/sales/<id>/receipt/`, `pos/shifts/` and shift closing now accept Django **session authentication only**, rather than HTTP Basic credentials. SessionAuthentication enforces CSRF for unsafe requests.
- `pos/shift-sales/` remains the shift-required cashier checkout path.
- `pos/sales/` is a **legacy compatibility route**. It is enabled only when both `DEBUG=True` and `POS_ENABLE_LEGACY_CHECKOUT=1`. In production it returns HTTP 410 and does not process a sale, regardless of the setting.
- `POS_SESSION_AGE_SECONDS` controls the Django session-cookie lifetime (default 28800 seconds). This is a maximum cookie age, **not an inactivity timeout**.
- The Paystack/payment endpoints still have their existing authentication contracts; review them before public deployment.

## Local verification

```bash
cd services/api
uv sync --extra dev
uv run python -m pytest -q transactional/tests/test_pos_production_guard.py -vv
uv run python -m pytest -q transactional/tests/test_pos_session_shift_flow.py -vv
uv run python -m pytest -q transactional/
uv run python manage.py check
```

If the local database has `DJANGO_DEBUG=0`, the legacy checkout tests that explicitly exercise `pos/sales/` must be adapted to use `shift-sales/` or opt in to the development compatibility setting for their test only. This development-only route is never intended for a real shop.

## Before real deployment

Configure `DJANGO_DEBUG=0`, strong secret key, HTTPS, dedicated allowed hosts, CSRF trusted origins, and shared cache-backed login throttling; deploy with secure session cookies. Add production audit logging, session expiry/inactivity policies, centralized authentication monitoring, and external payment auth review. The current development server must not be exposed as a production endpoint. Verify Next.js proxy cookie and CSRF forwarding using the deployment hostname.
