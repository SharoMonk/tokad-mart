# Agent Runtime and Isolation

Tokad Mart treats the coding agent as an engineering worker operating inside a controlled repository runtime.

## Runtime layers

```text
Task
  ↓
AGENTS.md + repository knowledge
  ↓
Workflow + relevant skills
  ↓
Isolated Git worktree
  ↓
Agent tools / code changes
  ↓
Verification + invariants
  ↓
Diff review
  ↓
Commit / PR
```

## Isolation contract

Autonomous or concurrent work must use a dedicated branch and preferably a dedicated Git worktree. The worktree is disposable; the branch is the durable unit of review.

Use:

```bash
bash scripts/agent/worktree.sh create pos-checkout main
```

This creates a branch named `agent/pos-checkout` and an isolated checkout under `.worktrees/` by default. Set `TOKAD_WORKTREE_ROOT` when a repository-external location is preferred.

Remove a finished worktree with:

```bash
bash scripts/agent/worktree.sh remove pos-checkout
```

The helper intentionally refuses to overwrite an existing task worktree or branch.

## Lifecycle hooks

Install the repository's lightweight pre-commit checks once per local checkout:

```bash
bash scripts/agent/install-hooks.sh
```

The hook runs documentation and invariant checks. Full application verification remains the responsibility of `scripts/agent/verify.sh` and CI.

A hook may be bypassed only for a deliberate local recovery operation:

```bash
TOKAD_SKIP_AGENT_HOOKS=1 git commit ...
```

A bypass must be explained in the task/PR when it affects the submitted change.

## Safety boundary

Worktrees isolate source trees, not external services. Concurrent agents must not share mutable development databases, credentials, ports, or external resources without an explicit isolation strategy.
