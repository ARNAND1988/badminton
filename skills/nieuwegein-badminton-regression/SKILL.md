---
name: nieuwegein-badminton-regression
description: Mandatory change-aware regression and quality gate for the Nieuwegein Badminton application. Use after feature, bug-fix, authentication, backend, frontend, database, booking, family, invoice, admin, mobile, PWA, or infrastructure changes and before reporting application work complete; use full mode for substantial features and deployment readiness.
---

# Nieuwegein Badminton Regression

Run the stable repository interface from the repository root:

```bash
./scripts/regression.sh fast   # development iteration
./scripts/regression.sh full   # feature completion (default)
```

## Workflow

1. Inspect `git diff` and the runner's detected files. Use `REGRESSION_BASE=<ref>` when a specific baseline is required.
2. Use fast mode while iterating. It selects focused auth journeys for auth-only changes and otherwise expands to dependent domain tests.
3. Use full mode after substantial features and before completion. It runs whitespace/format verification, Python compile checks, every backend/API/integration test, the critical member and admin journeys, responsive structural smoke checks, and the production frontend build.
4. Treat the runner's final report as the gate. Never report PASS when a relevant critical check failed.
5. If the change caused a failure, locate the flow, fix the implementation, rerun the relevant test, then rerun this gate. Do not weaken, remove, or skip a valid test.
6. Separate proven baseline failures from current-change failures. Do not modify unrelated behavior solely to hide a pre-existing failure.
7. Report BLOCKED, with the missing dependency or service, when a required check cannot execute.

## Safety

The runner forces an in-memory SQLite test database, development mock auth, inert messaging configuration, and test secrets. It refuses obvious production configuration. Never point it at production, reset/truncate/drop a real database, create fake production records or invoices, or send real email, WhatsApp, payments, booking mutations, or notifications.

Read [references/coverage.md](references/coverage.md) when extending the application or gate. Keep `./scripts/regression.sh` stable while evolving underlying commands and tests.
