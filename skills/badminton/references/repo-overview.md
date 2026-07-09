# Repo Overview

## Active Modules

- `badminton-backend`: Flask API, SQLAlchemy models, auth, bookings, invoices, payments, and WhatsApp notification orchestration.
- `badminton-frontend`: Vue 3 + Vite client with a router-driven dashboard and shared `Dashboard.vue` surface for most member and admin views.
- `badminton-infra`: Docker Compose, Nginx, Cloudflare tunnel, Raspberry Pi deploy helpers, and Kubernetes manifests.
- `whatsapp-bot`: separate helper service used by backend notification flows in the Docker app stack.

## Preferred Paths

Work in these top-level directories first:

- `badminton-backend/...`
- `badminton-frontend/...`
- `badminton-infra/...`

Legacy nested copies exist under:

- `badminton-frontend/badminton-frontend`
- `badminton-infra/badminton-infra`

Do not edit those unless the task explicitly targets the split-repo layout.

## Cross-Module Flows

### Member auth

Frontend login/register screens call `/api/auth/...`, store the JWT in browser storage, and refresh user details from `/api/auth/me`.

### Booking management

Admins create and edit bookings in the Vue dashboard. The Flask backend calculates costs, manages participants, and returns booking payloads that the frontend renders directly.

### Monthly invoices and payments

The backend builds monthly summaries from completed bookings and misc costs, generates payment invoices, and integrates with Wise webhooks. The frontend exposes both member invoice views and admin payment settings/status screens.

### WhatsApp notifications

The backend owns notification settings, reminder generation, and outbound calls. In Docker app mode it talks to the `whatsapp-bot` service using `WHATSAPP_BOT_URL` and `WHATSAPP_BOT_TOKEN`.

### Deployment

Local development usually runs backend and frontend from source with Postgres and Redis in Docker. The Raspberry Pi deployment rebuilds from source through `badminton-infra/update-from-main.sh` and Compose.

## Common Commands

### Local DB services

```bash
cd badminton-infra
docker compose -f docker-compose.local-db.yml up -d
```

### Backend

```bash
cd badminton-backend
pytest
```

### Frontend

```bash
cd badminton-frontend
npm run build
```

### Full local app stack

```bash
cd badminton-infra
docker compose -f docker-compose.app.yml up --build -d
```
