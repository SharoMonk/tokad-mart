# React Native / Expo Skill

Use this skill for the Tokad Mart mobile companion application. The mobile repository is maintained separately from this backend/web repository.

## Implementation rules

1. Confirm whether the requested change belongs in this repository or the companion mobile repository before editing.
2. Preserve the existing Expo and navigation architecture.
3. Treat offline behavior and synchronization as explicit requirements when the feature touches POS workflows.
4. Keep API contracts aligned with the backend source of truth.
5. Avoid embedding business rules in screens when they belong in shared/domain or backend logic.
6. Add focused tests for changed behavior and document cross-repository contract changes.

## Verification

Run the mobile repository's relevant tests/type checks/build checks there. For backend contract changes, also run `scripts/agent/verify` in this repository.