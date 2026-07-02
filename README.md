# Badminton - Development & Deployment

Lightweight badminton booking platform with member login, court bookings, family members, play attendance votes, admin court management, and invoice generation.

## Project Layout

- `badminton-frontend/`: Vue 3, Vite, Vue Router, Tailwind CSS.
- `badminton-backend/`: Flask, Flask-SQLAlchemy, Alembic, JWT auth, Redis/Twilio hooks, pytest.
- `badminton-infra/`: Docker Compose, local Postgres/Redis helpers, Nginx, Kubernetes manifests, seed SQL.

## Prerequisites

- Python 3.11+ recommended. The current local venv may use Python 3.13 and works for development.
- Node.js 18+ and npm.
- Docker and Docker Compose.

## Demo Accounts

The backend creates this initial administrator:

- Admin: `admin` / `admin123`

## Run Locally

This mode runs Postgres and Redis in Docker, while the backend and frontend run from your local source folders.

### 1. Start Local Postgres And Redis

```bash
cd badminton-infra
docker compose -f docker-compose.local-db.yml up -d
```

Local service ports:

- Postgres: `localhost:5433`
- Redis: `localhost:6380`

The backend creates only the initial `admin` user on startup.

### 2. Run Backend Locally

```bash
cd badminton-backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

export DATABASE_URL="postgresql://badminton_user:strongpassword@localhost:5433/badminton"
export REDIS_URL="redis://localhost:6380/0"
export SECRET_KEY="dev-secret"
export JWT_SECRET="dev-jwt-secret"
export FLASK_ENV=development
export AUTH_MOCK=1

flask --app app:create_app run --host 127.0.0.1 --port 8000
```

Backend URL:

- `http://127.0.0.1:8000/api/health`

### 3. Run Frontend Locally

```bash
cd badminton-frontend
npm install
npm run dev -- --host 127.0.0.1
```

Frontend URL:

- `http://127.0.0.1:5173`

Vite proxies `/api` to `http://127.0.0.1:8000` through `badminton-frontend/vite.config.js`.

## Run With Docker

This mode builds and runs Postgres, Redis, backend, and frontend in Docker from the current repo layout.

If the local DB-only stack is already running, stop it first so ports `5433` and `6380` are free:

```bash
cd badminton-infra
docker compose -f docker-compose.local-db.yml down
```

```bash
cd badminton-infra
docker compose -f docker-compose.app.yml up --build -d
```

The compose file starts Postgres and Redis first, waits for both services to become healthy, and then starts the Flask backend and Vue/Nginx frontend.

Docker service ports:

- Frontend: `http://localhost:8080`
- Backend: `http://localhost:8000`
- Postgres: `localhost:5433`
- Redis: `localhost:6380`

Verify the running app:

```bash
curl http://localhost:8080/api/health
```

Expected response:

```json
{"status":"ok"}
```

Useful Docker commands:

```bash
docker compose -f docker-compose.app.yml ps
docker compose -f docker-compose.app.yml logs -f badminton-backend
docker compose -f docker-compose.app.yml logs -f badminton-frontend
docker compose -f docker-compose.app.yml down
```

If a container is restarting, inspect its recent logs:

```bash
docker compose -f docker-compose.app.yml logs --tail=100 badminton-backend
```

To switch back to local source-code development after using the full Docker app stack:

```bash
docker compose -f docker-compose.app.yml down
docker compose -f docker-compose.local-db.yml up -d
```

The older `badminton-infra/docker-compose.yml` is kept for split-repository deployment layouts where build contexts are named `./backend` and `./frontend`. Use `docker-compose.app.yml` for this monorepo checkout.

## Raspberry Pi Startup Service

The Pi is configured to start the Docker app and Cloudflare tunnel on boot through `systemd`.

Service file in this repo:

```text
badminton-infra/badminton-app.service
```

Installed service:

```text
/etc/systemd/system/badminton-app.service
```

The service runs:

```bash
docker compose -f docker-compose.app.yml -f docker-compose.cloudflare.yml up -d --remove-orphans
```

from:

```text
/home/admin/git-repo/badminton/badminton-infra
```

Boot services:

- `docker.service` is enabled.
- `badminton-app.service` is enabled.
- `badminton-app.service` starts after Docker and network-online.

Useful commands:

```bash
sudo systemctl status badminton-app.service
sudo systemctl restart badminton-app.service
sudo systemctl stop badminton-app.service
journalctl -u badminton-app.service -n 100
```

After editing `badminton-infra/badminton-app.service`, reinstall and reload it:

```bash
sudo cp badminton-infra/badminton-app.service /etc/systemd/system/badminton-app.service
sudo systemctl daemon-reload
sudo systemctl enable badminton-app.service
sudo systemctl restart badminton-app.service
```

## Backend Environment Variables

Local development:

```dotenv
DATABASE_URL=postgresql://badminton_user:strongpassword@localhost:5433/badminton
REDIS_URL=redis://localhost:6380/0
SECRET_KEY=dev-secret
JWT_SECRET=dev-jwt-secret
FLASK_ENV=development
AUTH_MOCK=1
```

Docker app compose:

```dotenv
DATABASE_URL=postgresql://badminton_user:strongpassword@postgres:5432/badminton
REDIS_URL=redis://redis:6379/0
SECRET_KEY=dev-secret
JWT_SECRET=dev-jwt-secret
FLASK_ENV=development
AUTH_MOCK=1
```

Production notes:

- Use strong `SECRET_KEY` and `JWT_SECRET` values.
- Disable `AUTH_MOCK`.
- Consider setting `JWT_EXP_SECONDS`.

## Tests

Backend tests:

```bash
cd badminton-backend
source .venv/bin/activate
pytest -q
```

Frontend production build check:

```bash
cd badminton-frontend
npm run build
```

## Database Migrations

Alembic is included in `badminton-backend`.

Run migrations:

```bash
cd badminton-backend
source .venv/bin/activate
export DATABASE_URL="postgresql://badminton_user:strongpassword@localhost:5433/badminton"
alembic -c alembic.ini upgrade head
```

Generate a migration after changing models:

```bash
alembic -c alembic.ini revision --autogenerate -m "describe change"
alembic -c alembic.ini upgrade head
```

Note: `create_app()` currently calls `db.create_all()` on startup and seeds the initial admin user. Keep Alembic migrations updated for repeatable deployments.

## Cloudflare Domain Setup

Use Cloudflare DNS to point your domain to the machine that serves the frontend.

### Cloudflare Tunnel With Docker

This is the recommended setup if you want Cloudflare to connect to the Docker app without opening inbound ports on your machine.

1. In Cloudflare Zero Trust, create a tunnel.
2. Copy the tunnel token.
3. In Cloudflare tunnel public hostname settings, route your domain to the frontend service:
   - Public hostname: `yourdomain.com`
   - Service type: `HTTP`
   - Service URL: `badminton-frontend:80`
4. If you want `www.yourdomain.com`, add a second public hostname with the same service URL.
5. Create `badminton-infra/.env`:

```dotenv
CLOUDFLARED_TOKEN=your-cloudflare-tunnel-token
```

You can copy `badminton-infra/.env.example` as a starting point. Keep the real `.env` file private; it is ignored by git.

For remote deployments where the ignored `.env` file is not present, expose the token as a secret environment variable and let the deploy helper create `badminton-infra/.env` on the remote machine:

```bash
cd badminton-infra
CLOUDFLARED_TOKEN=your-cloudflare-tunnel-token ./deploy-cloudflare.sh
```

`CLOUDFLARE_TUNNEL_TOKEN` is also accepted as an alias. The helper writes `.env` with private file permissions before starting Docker Compose.

6. Start the Docker app with the Cloudflare tunnel overlay:

```bash
cd badminton-infra
docker compose -f docker-compose.app.yml -f docker-compose.cloudflare.yml up --build -d
```

This starts the same Docker app stack plus a `cloudflared` container. The tunnel container uses the shared Compose network, so it can reach `badminton-frontend:80` directly.

7. Check tunnel logs:

```bash
docker compose -f docker-compose.app.yml -f docker-compose.cloudflare.yml logs -f cloudflared
```

The public hostname should point to `badminton-frontend:80`, not `localhost:8080`. Inside Docker, the frontend container can reach the backend through its Nginx `/api/` proxy, so `https://yourdomain.com/api/...` will flow through the frontend container to the backend service.

Check all app and tunnel containers:

```bash
docker compose -f docker-compose.app.yml -f docker-compose.cloudflare.yml ps
```

Stop the tunnel and app:

```bash
docker compose -f docker-compose.app.yml -f docker-compose.cloudflare.yml down
```

### If Hosting On Your Own Server

1. In Cloudflare, add your domain and make sure the domain's authoritative nameservers are Cloudflare.
2. In Cloudflare DNS, create an `A` record:
   - Type: `A`
   - Name: `@` for the root domain, or `www` for `www.yourdomain.com`
   - IPv4 address: your server public IP
   - Proxy status: Proxied if you want Cloudflare proxy/CDN, DNS only while debugging
3. If you use both root and `www`, add the second record too. Common setup:
   - `A @ -> server public IP`
   - `CNAME www -> your root domain`
4. On your server, expose the frontend through ports `80` and `443`. Cloudflare cannot reach a dev server on `localhost:5173` from the public internet.
5. Put Nginx, Caddy, Traefik, or another reverse proxy in front of the app:
   - `/` goes to the frontend container/site.
   - `/api/` goes to the backend on port `8000`.
6. In Cloudflare SSL/TLS, use `Full` or `Full (strict)` once your origin has a valid certificate. Use `Full (strict)` for production when possible.

For the current Docker app compose, the frontend is published on host port `8080`. For a real domain, either map the frontend/reverse proxy to host `80`/`443`, or place another host-level reverse proxy in front of `localhost:8080`.

### If Hosting As A Static Frontend

The Vue app can be built as static files:

```bash
cd badminton-frontend
npm run build
```

Deploy `badminton-frontend/dist/` to Cloudflare Pages or another static host. If the frontend is static-hosted separately, set up an API host such as `api.yourdomain.com` for the Flask backend and update the frontend API base/proxy strategy before building. The current local frontend code uses relative `/api` requests, which works best when the same domain reverse proxies `/api` to the backend.

Useful Cloudflare docs:

- DNS records: <https://developers.cloudflare.com/dns/manage-dns-records/how-to/create-dns-records/>
- SSL/TLS modes: <https://developers.cloudflare.com/ssl/origin-configuration/ssl-modes/>

## Kubernetes

Kubernetes manifests live in `badminton-infra/infra/k8s`.

The SQL init job uses:

```bash
cd badminton-infra/infra
kubectl --context=pi-k3s-cluster apply -f k8s/namespace.yaml
kubectl --context=pi-k3s-cluster apply -f k8s/postgres-secret.yaml
kubectl --context=pi-k3s-cluster apply -f k8s/postgres-deployment.yaml
kubectl --context=pi-k3s-cluster apply -f k8s/postgres-service.yaml
kubectl --context=pi-k3s-cluster apply -f k8s/sql-init-configmap.yaml
kubectl --context=pi-k3s-cluster apply -f k8s/run-sql-job.yaml
```

Then deploy app manifests:

```bash
kubectl --context=pi-k3s-cluster apply -f k8s/deployment.yaml
```

Review secrets, `AUTH_MOCK`, image tags, and ingress host before production use.

## CI

GitHub Actions workflows:

- `.github/workflows/ci.yml`: backend tests and frontend build.
- `.github/workflows/docker-build-push.yml`: builds and pushes backend/frontend images to GitHub Container Registry.
