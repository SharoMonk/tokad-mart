# POS Invariants

- POS-001: Checkout is a domain transaction, not a collection of unrelated CRUD writes.
- POS-002: A completed checkout has one authoritative transaction identity.
- POS-003: Repeated submit/retry operations are idempotent.
- POS-004: Receipt totals, order totals, payment totals, and inventory effects reconcile.
- POS-005: Failed checkout leaves no partial committed sale or stock mutation.
- POS-006: Offline/synchronization behavior must not create duplicate transactions when supported.
