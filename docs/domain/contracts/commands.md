# Tokad Mart Command Contract

Status: implementation contract

Business behavior should be exposed through explicit commands/use cases rather than arbitrary model mutation.

## Checkout

`CheckoutSale`

Inputs:

- cart/line items
- location
- currency
- customer reference (optional)
- payment intent/reference where applicable
- idempotency key
- actor/device reference

Guarantees:

- validates products and prices at the server boundary;
- calculates authoritative totals server-side;
- enforces the inventory concurrency policy;
- applies the defined transaction boundary;
- records the idempotency result;
- produces a canonical sale result.

## Payment callback

`ApplyPaymentResult`

Inputs:

- provider
- provider event/reference
- verified payment status
- amount/currency
- sale/payment reference
- idempotency key or provider event identity

Guarantees:

- verifies authenticity before changing payment state;
- rejects mismatched amount/currency/sale references;
- safely handles duplicate callbacks;
- records an audit event for accepted state changes.

## Inventory adjustment

`AdjustInventory`

Inputs:

- product/location
- quantity delta
- reason
- actor
- reference/note
- idempotency key where the command can be retried

Guarantees:

- validates the allowed reason;
- enforces stock policy;
- records an inventory movement;
- updates the stock projection atomically with the movement where both are persisted;
- is auditable.

## Refund

`RefundSale`

Inputs:

- sale reference
- amount or line selection
- reason
- actor
- idempotency key

Guarantees:

- cannot exceed refundable value;
- creates compensating inventory/payment effects where applicable;
- does not mutate the historical completed sale into a different historical transaction.

## Command boundary rule

HTTP endpoints, background jobs, POS clients, and future integrations should invoke these commands/use cases. They should not implement transactional business rules independently.
