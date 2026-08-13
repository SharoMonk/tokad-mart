# Payments Domain Skill

Use this skill for payment intents, captures, failures, refunds, payment reconciliation, and payment-related order state.

## Required understanding

- Payment state is authoritative domain state and must not be inferred from UI state.
- External payment providers are unreliable boundaries: design for retries, timeouts, duplicate callbacks, and delayed confirmation.
- Never store or expose sensitive payment credentials unnecessarily.

## Implementation rules

1. Inspect the existing payment abstraction and provider integration before changing behavior.
2. Model provider callbacks/webhooks as idempotent events.
3. Separate requested, pending, successful, failed, cancelled, and refunded states where supported by the domain.
4. Never mark an order paid solely because a client reports success.
5. Preserve provider references needed for reconciliation without storing prohibited sensitive data.
6. Add tests for duplicate callbacks, delayed callbacks, failure paths, and refund transitions when applicable.

## Verification

Run focused payment tests and relevant API tests, then `scripts/agent/verify`.