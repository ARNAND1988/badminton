# Nieuwegein Badminton Codex workflow

Use the repository-local `nieuwegein-badminton-regression` skill as the mandatory quality gate for application changes. It inspects the diff, selects dependent domains in fast mode, runs isolated backend/API journeys and frontend checks, and emits the standard regression report.

For every feature change:

1. Understand the existing architecture and inspect the affected code.
2. Implement the feature and add or update tests.
3. Run the narrow relevant tests.
4. Run `./scripts/regression.sh fast` while iterating.
5. Fix failures introduced by the change, then rerun the gate.
6. Run `./scripts/regression.sh full` for substantial features and before declaring feature work complete.

Never weaken a valid test to obtain a pass. Fix failures caused by the current change before completion. Report unrelated, demonstrably pre-existing failures separately; do not silently change unrelated functionality to fix them. The gate is non-destructive and must only use its isolated test database and mocked external integrations.
