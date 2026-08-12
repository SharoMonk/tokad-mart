# Inventory Domain

Inventory tracks stock-affecting operations and their audit trail.

## Core invariants

- Every stock mutation has an identifiable business cause.
- Stock-changing operations are atomic where consistency requires it.
- Concurrent updates must not silently lose stock changes.
- Historical corrections use explicit adjustments rather than rewriting history.
- Sales, returns, receiving, transfers, reservations, and adjustments must have explicit semantics.

## Agent guidance

Consult `.agent/skills/inventory/SKILL.md` and ADR-002 before changing inventory behavior. Update this document when the finalized inventory model introduces durable business rules.