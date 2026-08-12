# Testing Skill

Use this skill for test additions, failures, and verification work.

## Principles

- Prefer a focused regression test before broad test execution.
- Test observable behavior and domain invariants rather than implementation details.
- Preserve deterministic tests; do not weaken assertions merely to make a suite pass.
- For transactional code, cover failure, retry, and consistency behavior where relevant.

## Completion

A task is not complete merely because the implementation looks correct. Record the tests actually run and any checks that could not be executed because of environment limitations.
