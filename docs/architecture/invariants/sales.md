# Sales Invariants

These rules define correctness boundaries for the sales domain. Prefer enforcing them with automated tests and structural checks rather than relying on agent instructions alone.

- SALE-001: Completed sales are immutable; corrections use explicit reversal/refund flows.
- SALE-002: Sale creation and all stock-affecting effects must share an explicit transaction boundary.
- SALE-003: Retried requests must not create duplicate sales.
- SALE-004: Persisted totals must reconcile with line items and approved adjustments.
- SALE-005: Presentation/API layers must not perform direct persistence for completed-sale state transitions.
