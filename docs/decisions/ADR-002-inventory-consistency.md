# ADR-002: Inventory Consistency

## Status

Accepted — foundation decision; refine when inventory implementation is finalized.

## Decision

Inventory-changing operations must be represented as explicit, auditable domain operations rather than arbitrary quantity overwrites.

Stock effects caused by sales, returns, receiving, transfers, reservations, or adjustments must have a traceable source and an atomic persistence strategy appropriate to the operation.

## Consequences

- Stock history is preserved.
- Concurrent operations must be considered explicitly.
- Corrections should create an auditable adjustment rather than silently rewriting history.
- Agents should inspect inventory services and database constraints before changing stock logic.

## Non-goals

This ADR does not yet define the final reservation model or isolation strategy; those should be recorded in follow-up decisions once implemented.