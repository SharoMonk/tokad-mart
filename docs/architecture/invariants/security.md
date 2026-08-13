# Security Invariants

- SEC-001: Secrets and credentials never belong in source code, documentation, tests, or agent context.
- SEC-002: Authentication and authorization are enforced server-side for protected operations.
- SEC-003: Sensitive operations require explicit authorization checks at the domain/API boundary.
- SEC-004: Logs must not expose credentials, tokens, payment secrets, or unnecessary personal data.
- SEC-005: Agent tooling must default to development/test resources and require explicit approval for sensitive environments.
