# Badminton — Development & Deployment

This repository contains a Flask backend and a Vite + Vue 3 frontend (Tailwind CSS). Below are quick start instructions for local development, testing, and production using Docker Compose.

## Prerequisites

- Python 3.11 (recommended)
- Node.js 18+ and npm (for frontend local dev)
- Docker & Docker Compose (for production / full stack local via containers)

## Environment variables

Create a `.env` file for the backend (used by `docker-compose` or development):

```
DATABASE_URL=postgresql://user:pass@postgres:5432/badminton
SECRET_KEY=change-me
JWT_SECRET=change-this-for-prod
REDIS_URL=redis://redis:6379/0
# Optional Twilio WhatsApp settings for production
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
WHATSAPP_FROM=+1415XXXXXXX
# Development mock mode (do NOT enable in production)
AUTH_MOCK=1
FLASK_ENV=development
```

## Local development (backend)

1. Create and activate a virtualenv, install dependencies:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Create tables (example uses `DATABASE_URL` env var):

```bash
export DATABASE_URL="sqlite:///db.sqlite"
export SECRET_KEY="dev-secret"
export FLASK_ENV=development
export AUTH_MOCK=1
python -c "from app import create_app, db; app=create_app(); with app.app_context(): db.create_all()"
```

3. Run the backend (development or production server):

Development (Flask dev server):
```bash
FLASK_APP=app:create_app FLASK_ENV=development flask run --port=8000
```

Production (Gunicorn):
```bash
gunicorn wsgi:app -w 2 -b 0.0.0.0:8000
```

## Local development (frontend)

1. Install node deps and run Vite dev server:

```bash
cd frontend
npm install
npm run dev
```

2. The Vite dev server runs on port `5173` and proxies `/api` to `http://localhost:8000` (see `vite.config.js`).

## Running tests

Backend tests use `pytest` and run with an in-memory SQLite DB and `AUTH_MOCK` enabled.

```bash
cd backend
pip install -r requirements.txt
pytest -q
```

## Production with Docker Compose

1. Build and start services:

```bash
docker-compose build
docker-compose up -d
```

2. The `nginx` service listens on port 80 and proxies `/api` to the backend service. The frontend image builds the Vite app and serves the `dist` via `nginx`.

3. Ensure you set production environment variables for `DATABASE_URL`, `JWT_SECRET`, and Twilio credentials. Disable `AUTH_MOCK` in production.

### Database migrations (Alembic)

Alembic is included to manage schema migrations. The repository contains an Alembic scaffold and an initial migration.

To run migrations locally:

```bash
pip install alembic
export DATABASE_URL="postgresql://user:pass@localhost:5432/badminton"
alembic -c alembic.ini upgrade head
```

To generate a new migration after changing models:

```bash
alembic -c alembic.ini revision --autogenerate -m "describe change"
alembic -c alembic.ini upgrade head
```

### Docker healthchecks

`docker-compose.yml` includes healthchecks for the backend and frontend services. Docker will report service health and retries according to the compose file.

### CI / Docker image build & push

Two GitHub Actions workflows are included:
- `.github/workflows/ci.yml` — runs backend tests and builds the frontend artifact on push/PR.
- `.github/workflows/docker-build-push.yml` — builds and pushes Docker images for backend and frontend to GitHub Container Registry (`ghcr.io`) on pushes to `main`/`master`.

To enable publishing to `ghcr.io` you do not need to add secrets for the default `GITHUB_TOKEN`, but you can create a PAT with `write:packages` if you prefer.


## CI

A GitHub Actions workflow is included at `.github/workflows/ci.yml` that runs backend tests and builds the frontend on push/PR.

## Notes

- Mock OTP: In development `AUTH_MOCK=1` will return the OTP in the API response for easier local testing. Never enable this in production.
- Token: The backend issues JWT tokens signed with `JWT_SECRET`.
- If you'd like, I can add healthchecks, container health endpoints, or automate DB migrations with Alembic.
