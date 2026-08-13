# Pass 10 — Database & Transactional Test Infrastructure

## Objective

Make the Django transactional foundation reproducible, migration-backed, and testable against the configured PostgreSQL database.

## Implemented

- Added the initial `transactional` Django migration.
- Added a migrations package marker.
- Added rollback coverage for insufficient-stock checkout.
- Added idempotency-key conflict coverage.
- Fixed idempotent checkout result reconstruction so UUID types remain stable.
- Added `scripts/agent/test-backend.sh` as the canonical backend test entry point.

## Verification contract

A green backend verification requires:

1. Django can load the settings module.
2. The transactional migration graph is valid.
3. pytest-django can provision a test database.
4. Checkout success persists sale, lines, inventory movement, audit event, and idempotency record.
5. Failed checkout leaves no partial transactional state.
6. Reusing an idempotency key with a different request is rejected.

## Not yet complete

- PostgreSQL service orchestration in CI.
- Concurrency tests using multiple database transactions.
- Payment callback idempotency.
- Completed-sale immutability enforcement.
- Full POS-001 through POS-008 evaluation activation.

These remain blocked until the corresponding application capabilities exist.
