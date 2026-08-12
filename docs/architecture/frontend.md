# Frontend Architecture

The web/POS application uses Next.js and TypeScript.

## Boundaries

- Presentation code should not own authoritative commerce rules.
- Backend APIs are the source of truth for financial, inventory, order, and payment state.
- API responses should be treated as untrusted external input at application boundaries.
- POS interactions should prioritize clear state, resilience, and accessibility.

Consult `.agent/skills/nextjs/SKILL.md` for implementation guidance.