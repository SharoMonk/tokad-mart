# ADR-003: Payment State

## Status

Accepted — foundation decision; provider-specific details belong in the payment integration documentation.

## Decision

Payment state is authoritative domain state. Order state must not be changed to paid solely from client-side claims or UI state.

Provider callbacks/webhooks are treated as external events and must be processed idempotently. Provider references required for reconciliation are retained without storing unnecessary sensitive payment data.

## Consequences

- Payment transitions are explicit and testable.
- Duplicate or delayed provider callbacks must be safe.
- Order completion must depend on authoritative payment state and the defined checkout policy.
- Agents must inspect the payment abstraction before modifying provider integrations.