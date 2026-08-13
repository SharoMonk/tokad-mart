# Products Domain Skill

Use this skill for product catalog, SKUs, variants, pricing, categories, units, and product availability.

## Implementation rules

1. Inspect existing product models and API contracts before introducing fields or abstractions.
2. Keep identifiers and SKU semantics explicit and stable.
3. Treat prices as domain data; avoid floating-point arithmetic for monetary values.
4. Separate catalog/product data from transaction snapshots where historical accuracy requires it.
5. Preserve compatibility for public API consumers when changing schemas.
6. Add tests for uniqueness, validation, pricing behavior, and relevant API contracts.

## Verification

Run focused product tests and API checks, then `scripts/agent/verify`.