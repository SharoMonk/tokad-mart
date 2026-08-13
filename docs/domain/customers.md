# Customers Domain

The customer domain owns customer identity linkage and customer-facing profile data used by commerce workflows.

## Core invariants

- Identity data has one authoritative owner.
- Customer data is accessed only through authorized boundaries.
- Historical transaction ownership is not casually rewritten.
- Optional and nullable API fields remain explicit.

Consult `.agent/skills/customers/SKILL.md` before changing customer behavior.