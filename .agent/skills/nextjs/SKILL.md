# Next.js Skill

Use this skill for the web application, including POS UI and customer-facing commerce flows.

## Implementation rules

1. Inspect existing routing, data-fetching, component, and styling conventions before adding new patterns.
2. Keep server/client boundaries intentional and avoid unnecessary client-side state.
3. Treat API responses as untrusted input; validate at boundaries where appropriate.
4. Preserve accessibility and responsive behavior for POS workflows.
5. Keep business rules out of presentation components when they belong in the backend/domain layer.
6. Add focused tests for changed behavior and avoid coupling UI tests to implementation details.

## Verification

Run the narrowest relevant web tests, type checks, lint, and build checks available, then `scripts/agent/verify`.