# Mobile Architecture

The Tokad Mart mobile application is maintained in the companion React Native/Expo repository.

## Repository boundary

Do not implement mobile-only code in this repository. Backend API and contract changes belong here; mobile UI and device behavior belong in the companion repository.

## Cross-repository rules

- Backend API contracts are authoritative for server state.
- Cross-repository contract changes must identify both consumers and verification steps.
- POS offline/synchronization behavior must be explicitly designed rather than inferred from online checkout behavior.

Consult `.agent/skills/react-native/SKILL.md` when a task crosses the mobile boundary.