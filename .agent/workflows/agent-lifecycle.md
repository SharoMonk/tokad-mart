# Agent Lifecycle

## Purpose

Define the safe lifecycle for coding-agent work in Tokad Mart.

## Lifecycle

1. **Discover** — read `AGENTS.md`, locate relevant domain docs and skills, inspect the repository state.
2. **Plan** — create or update an execution plan for non-trivial work.
3. **Isolate** — work on a dedicated Git branch/worktree. Never use `main` for autonomous changes.
4. **Implement** — make the smallest coherent change that satisfies the task.
5. **Verify** — run `scripts/agent/verify.sh` and relevant targeted tests.
6. **Review** — inspect `git diff`, changed files, migrations, dependencies, and security-sensitive changes.
7. **Handoff** — commit only verified changes and open/update a PR for human review.
8. **Recover** — if verification fails, diagnose and iterate; if requirements are ambiguous or destructive access is required, stop and request human input.

## Completion criteria

An agent must not describe a task as complete until:

- the requested behavior is implemented;
- relevant tests exist or an explicit reason is documented;
- `scripts/agent/verify.sh` passes, or known environment limitations are reported;
- architectural invariants remain satisfied;
- the final diff is scoped to the task;
- no secrets or local-only artifacts are committed.

## Isolation rule

Prefer a dedicated worktree for concurrent or autonomous work. The helper `scripts/agent/worktree.sh` creates and removes isolated worktrees without changing the current checkout.
