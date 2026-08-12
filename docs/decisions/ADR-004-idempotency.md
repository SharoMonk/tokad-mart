# ADR-004: Idempotency for Financial and Inventory Effects

## Status

Accepted — foundation decision.

## Decision

Operations that may be retried and can create financial, order, or inventory effects must have an explicit idempotency strategy.

Where an operation has a natural client or provider request identifier, that identifier should be used according to the concrete domain contract. Otherwise, the implementation must define how duplicate requests are detected safely.

## Consequences

- Checkout retries must not create duplicate sales.
- Payment callbacks must tolerate duplicate delivery.
- Background jobs must be safe to retry where they mutate business state.
- Idempotency behavior must be covered by tests for the affected operation.

## Non-goals

This ADR does not prescribe one universal idempotency-key storage schema. The implementation for each boundary should be documented when introduced.