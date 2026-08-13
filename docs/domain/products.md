# Products Domain

The product domain owns catalog concepts such as products, SKUs, variants, categories, units, and pricing metadata.

## Core invariants

- Stable identifiers and SKU semantics are preserved.
- Monetary values use appropriate exact representations rather than binary floating point.
- Transaction history is not silently rewritten when catalog data changes.
- Public API contracts remain intentional and validated.

Consult `.agent/skills/products/SKILL.md` for implementation guidance.