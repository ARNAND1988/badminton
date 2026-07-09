---
name: badminton
description: Navigate and modify the badminton monorepo. Use when Codex needs repo-specific context for the Nieuwegein Badminton system, especially for backend Flask API work, frontend Vue dashboard work, Docker or Raspberry Pi deployment changes, payment or WhatsApp flows, or cross-module changes that touch multiple parts of the stack.
---

# Badminton

Read [references/repo-overview.md](references/repo-overview.md) first when the task spans multiple modules or the repo layout is unclear.

Then load only the module notes you need:

- Backend/API/data/auth/payments/WhatsApp logic: read `badminton-backend/agent.md`
- Frontend/routes/dashboard/session/UI logic: read `badminton-frontend/agent.md`
- Docker/Compose/Nginx/Cloudflare/Pi/Kubernetes/deploy work: read `badminton-infra/agent.md`

## Quick Rules

- Prefer the top-level module directories: `badminton-backend`, `badminton-frontend`, and `badminton-infra`.
- Treat `badminton-frontend/badminton-frontend` and `badminton-infra/badminton-infra` as legacy split-repo copies unless the task explicitly targets them.
- When an API contract changes, update both the Flask endpoint and the Vue code that fetches or renders it.
- When service names, ports, or paths change, verify the frontend proxy assumptions and the infra routing together.
- Keep changes scoped. The backend has a large `bookings.py` module and the frontend has a large `Dashboard.vue`; edit the narrowest area that actually owns the behavior.

## Task Routing

### Backend

Use `badminton-backend/agent.md` for:

- auth and JWT behavior
- bookings, availability, family members, invoices, payments, or audit logs
- database model changes
- OpenAPI/docs behavior
- seeded user behavior in development and tests

### Frontend

Use `badminton-frontend/agent.md` for:

- Vue routes and navigation
- `Dashboard.vue` view logic
- login and session persistence
- admin screens, invoice screens, and play availability UI

### Infra

Use `badminton-infra/agent.md` for:

- local Docker stacks
- Raspberry Pi deploy flow
- Nginx proxying
- Cloudflare tunnel setup
- Kubernetes manifests

## Validation

Choose the smallest relevant validation:

- Backend: `cd badminton-backend && pytest`
- Frontend: `cd badminton-frontend && npm run build`
- Infra/config only: validate the touched YAML, compose file, or shell script and check related references

For cross-module work, validate each touched module separately instead of assuming one build covers the stack.
