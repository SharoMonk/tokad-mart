# Tokad Mart State Machine Contract

Status: implementation contract

State transitions are domain operations. Controllers, serializers, jobs, and UI code must not mutate state fields directly when a transition has business meaning.

## Sale

| From | Event | To |
|---|---|---|
| DRAFT | submit | PENDING_PAYMENT |
| PENDING_PAYMENT | payment_succeeded | COMPLETED |
| PENDING_PAYMENT | payment_failed | PAYMENT_FAILED |
| PENDING_PAYMENT | cancel | CANCELLED |

Completed, cancelled, and payment-failed terminal records must not be silently moved to another state.

## Payment

| From | Event | To |
|---|---|---|
| PENDING | provider_success | SUCCEEDED |
| PENDING | provider_failure | FAILED |
| PENDING | cancel | CANCELLED |
| SUCCEEDED | refund | REFUNDED |

A provider callback that repeats an already-applied transition is an idempotent no-op when the payload is equivalent. Conflicting callbacks must be rejected and audited.

## Inventory

Inventory is modeled as business movements rather than a general-purpose state machine. Supported movement reasons must be explicit, for example:

- SALE
- RETURN
- PURCHASE
- ADJUSTMENT
- TRANSFER_IN
- TRANSFER_OUT
- DAMAGE

A movement must never be created without a source/reference where the business event requires one.

## Implementation rule

The implementation must expose named transition/use-case functions or services. Direct status assignment should be limited to model construction, migrations, and persistence internals that are themselves covered by tests.
