# Database Policy

- Development and test environments only for agent-driven database operations.
- Never use production credentials or production data.
- Model changes require migrations.
- Validate migrations before completion.
- Destructive operations require explicit human approval and a documented recovery/data-preservation plan.
- Financial and inventory-changing workflows must have explicit transaction and concurrency semantics.
