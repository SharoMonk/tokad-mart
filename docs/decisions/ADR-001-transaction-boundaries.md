# ADR-001: Transaction Boundaries

## Status

Accepted — foundation decision; refine when implementation reveals new constraints.

## Decision

Business operations that change financial or inventory state must execute within an explicit transactional boundary appropriate to the persistence architecture.

The domain/application service that owns the operation is responsible for coordinating the boundary. HTTP handlers, UI code, background jobs, and integrations must not independently perform partial state changes that can leave the transaction inconsistent.

## Consequences

- Checkout and other stock/financial mutations should be atomic.
- External side effects require an explicit strategy for retries and failure recovery.
- Tests should cover rollback behavior for important multi-write operations.
- Agents must inspect the existing transaction service before introducing new transaction boundaries.

## Non-goals

This ADR does not prescribe one Django transaction API or isolation level. Those choices depend on the concrete operation and PostgreSQL behavior.