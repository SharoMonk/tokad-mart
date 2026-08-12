# Data Architecture

PostgreSQL is the system of record for transactional commerce data.

## Rules

- Financial and inventory-changing operations must use appropriate database transactions.
- Do not rely on application-level checks alone for invariants that can be protected by database constraints.
- Schema changes require migrations and migration validation.
- Avoid destructive migrations without an explicit migration plan and rollback/data-preservation analysis.
- Treat indexes and query behavior as part of the data design for high-volume transaction paths.
- Do not use production data in development or tests.

## Transactional operations

For sales, payments, inventory, refunds, and other state-changing workflows, document:

- transaction boundary;
- locking/concurrency behavior;
- idempotency behavior;
- failure and retry behavior;
- audit requirements.
