# Customers Domain Skill

Use this skill for customer profiles, customer identity, purchase history, loyalty linkage, and customer-facing account data.

## Implementation rules

1. Inspect the existing customer/user boundary before changing identity behavior.
2. Minimize stored personal data and avoid duplicating identity fields across domains.
3. Preserve authorization boundaries around customer data.
4. Treat historical transaction ownership carefully; do not rewrite transaction history casually.
5. Keep customer-facing APIs explicit about nullable and optional fields.
6. Add authorization, validation, and regression tests for changed behavior.

## Verification

Run focused customer/API tests, then `scripts/agent/verify`.