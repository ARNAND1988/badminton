# Smash Arena deployment

Deployed to https://nieuwegeinbadminton.nl at 2026-10-01T00:38:22.153595+02:00 using the existing Raspberry Pi Docker Compose stack.

Application release: `679cc4c9432dc634ab095e63182879440fb63944` on `design/smash-arena-theme`. Image: `badminton-frontend:smash-arena-679cc4c` (`sha256:58576a2e224cb115c98b498dc029af4f3b8c2136e732ed28390fa7513159dc74`). This was a direct frontend deployment from the reviewed branch; it was not pushed or merged into `main`. Before a future main-based update, integrate this release commit into the main release history. The automatic deployment timer was inactive at deployment time and was not changed.

Only `badminton-frontend` was recreated, using `up -d --no-deps --no-build badminton-frontend` with both existing Compose files. Backend, Postgres, Redis, WhatsApp and Cloudflare container IDs, image IDs, start times and health states were identical before/after. No configuration, credentials, auth/session handling or schema changed. No real bookings, invoices or notifications were modified by release verification.

## Validation

- Isolated full regression gate: 107 passed, zero failed/skipped.
- Focused frontend tests: 11 passed.
- Docker image build and Nginx configuration: passed.
- Public and local homepage returned identical new release HTML; both API health checks returned `status: ok`.
- Frontend and backend containers are healthy; the existing data/support services remain running.
- Live public availability/login/bookings checks: 12 page/viewport combinations at 375, 390, 768 and 1440px. All artwork loaded; no clipping, document horizontal overflow, JavaScript exceptions, console errors or HTTP errors. Zero write requests recorded.
- Production authenticated workflows were not repeated with live accounts. Existing isolated regression/API/browser evidence applies; no production login, booking, payment or notification was invoked. Device keyboard and screen-reader verification remain outside the available checks.

[Live desktop](screenshots/live-desktop.png) · [Live mobile](screenshots/live-mobile.png). Machine-readable release evidence: [deployment-verification.json](deployment-verification.json).

## Immediate frontend rollback

The previous image remains tagged `badminton-frontend:smash-arena-rollback-20261001` (`sha256:98420ab4b0572b60451e80ae479d9941c6d26ab8f41f86cd906f58100971c53b`). From the repository root:

```sh
docker image tag badminton-frontend:smash-arena-rollback-20261001 badminton-infra-badminton-frontend:latest
docker compose -f badminton-infra/docker-compose.app.yml -f badminton-infra/docker-compose.cloudflare.yml up -d --no-deps --no-build badminton-frontend
```

Check the homepage and `/api/health` afterward. This rollback affects only the frontend container; no database rollback is required. The new release image also remains tagged separately for review/redeployment. The deployment lock was released after verification.
