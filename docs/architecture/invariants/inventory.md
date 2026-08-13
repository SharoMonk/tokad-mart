# Inventory Invariants

- INV-001: Stock-changing operations occur inside an explicit database transaction.
- INV-002: Inventory writes are performed through approved domain/service boundaries, not presentation code.
- INV-003: Every stock adjustment has an auditable reason and actor/source.
- INV-004: Concurrent checkout cannot silently oversell stock; locking or an equivalent concurrency strategy is required.
- INV-005: Failed sales do not leave partial inventory mutations behind.
