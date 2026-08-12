# Bugfix Workflow

1. Reproduce the failure before changing code when practical.
2. Trace the failure to its root cause rather than patching the visible symptom.
3. Add or identify a regression test that demonstrates the failure.
4. Implement the smallest correct fix.
5. Run the regression test and relevant surrounding tests.
6. Run `scripts/agent/verify` when available.
7. Inspect the final diff and document any unresolved uncertainty.
