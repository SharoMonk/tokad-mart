#!/usr/bin/env bash
set -euo pipefail

# Create/remove isolated Git worktrees for coding-agent tasks.
# Usage:
#   ./scripts/agent/worktree.sh create <task-name> [base-ref]
#   ./scripts/agent/worktree.sh remove <task-name>
#   ./scripts/agent/worktree.sh path <task-name>

REPO_ROOT="$(git rev-parse --show-toplevel)"
WORKTREE_ROOT="${TOKAD_WORKTREE_ROOT:-${REPO_ROOT}/.worktrees}"
PREFIX="agent/"

usage() {
  echo "Usage: $0 {create|remove|path} <task-name> [base-ref]" >&2
  exit 2
}

[[ $# -ge 2 ]] || usage
ACTION="$1"
TASK="$2"
BASE_REF="${3:-HEAD}"

if [[ ! "$TASK" =~ ^[A-Za-z0-9._/-]+$ ]]; then
  echo "Invalid task name: $TASK" >&2
  exit 2
fi

# Prevent path traversal while allowing readable task names.
case "$TASK" in
  /*|*..*) echo "Invalid task name: $TASK" >&2; exit 2 ;;
esac

SAFE_TASK="${TASK//\//-}"
WORKTREE_PATH="${WORKTREE_ROOT}/${SAFE_TASK}"
BRANCH="${PREFIX}${TASK}"

case "$ACTION" in
  create)
    mkdir -p "$WORKTREE_ROOT"
    if [[ -e "$WORKTREE_PATH" ]]; then
      echo "Worktree already exists: $WORKTREE_PATH" >&2
      exit 1
    fi
    if git show-ref --verify --quiet "refs/heads/$BRANCH"; then
      echo "Branch already exists: $BRANCH" >&2
      exit 1
    fi
    git worktree add -b "$BRANCH" "$WORKTREE_PATH" "$BASE_REF"
    echo "Created worktree: $WORKTREE_PATH"
    echo "Branch: $BRANCH"
    ;;
  remove)
    git worktree remove "$WORKTREE_PATH"
    echo "Removed worktree: $WORKTREE_PATH"
    ;;
  path)
    printf '%s\n' "$WORKTREE_PATH"
    ;;
  *)
    usage
    ;;
esac
