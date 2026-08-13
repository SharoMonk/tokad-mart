# Payment Invariants

- PAY-001: Payment state transitions are explicit and auditable.
- PAY-002: Payment callbacks/webhooks are idempotent.
- PAY-003: A client-side claim is never treated as proof of successful payment without server-side verification.
- PAY-004: A completed payment cannot be silently rewritten into another state.
- PAY-005: Payment processing must not create duplicate sales when requests are retried.
