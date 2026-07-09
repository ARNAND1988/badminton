# Infra Agent Notes

## Stack

- Docker Compose for local/full-stack container orchestration
- `systemd` startup service on the Raspberry Pi 5
- Cloudflare Tunnel via `cloudflared`
- Nginx reverse proxy for frontend, backend API, and uploads
- Postgres 15 Alpine
- Redis 7 Alpine
- Kubernetes manifests for a `nieuwegein-badminton` namespace
- Traefik ingress and cert-manager annotation for `nieuwegeinbadminton.nl`
- GitHub Container Registry images referenced by Kubernetes manifests

## Active Paths

- `docker-compose.app.yml`: active monorepo app stack
- `docker-compose.cloudflare.yml`: Cloudflare Tunnel overlay
- `docker-compose.local-db.yml`: Postgres and Redis only for source-based local development
- `deploy-cloudflare.sh`: deploy helper that writes `.env` and starts Compose
- `update-from-main.sh`: Raspberry Pi update and redeploy script
- `nginx/nginx.conf`: reverse proxy for frontend, backend API, and uploads
- `infra/k8s/`: optional Kubernetes path

Prefer the top-level `badminton-infra` directory. Treat `badminton-infra/badminton-infra` as a legacy split-repo copy unless the task explicitly targets that layout.

## Important Files

- `docker-compose.app.yml`: active monorepo Docker app stack for Postgres, Redis, backend, and frontend.
- `docker-compose.cloudflare.yml`: Cloudflare Tunnel overlay service.
- `docker-compose.local-db.yml`: local Postgres/Redis only.
- `badminton-app.service`: Pi boot service that starts the app stack plus Cloudflare tunnel.
- `docker-compose.yml`: older split-repository layout; build contexts do not match this monorepo checkout.
- `nginx/nginx.conf`: reverse proxy and API rate limit config.
- `../whatsapp-bot`: Compose-managed helper service used by backend notification features.
- `infra/k8s/namespace.yaml`: Kubernetes namespace.
- `infra/k8s/postgres-secret.yaml`: Postgres password secret.
- `infra/k8s/postgres-deployment.yaml`: in-cluster Postgres deployment.
- `infra/k8s/postgres-service.yaml`: Postgres service named `postgres`.
- `infra/k8s/init.sql`: SQL initialization script.
- `infra/k8s/sql-init-configmap.yaml`: ConfigMap wrapping `init.sql`.
- `infra/k8s/run-sql-job.yaml`: one-shot SQL init job.
- `infra/k8s/deployment.yaml`: backend/frontend deployments, services, and ingress.
- `infra/k8s/README.md`: SQL job runbook.

## Docker Compose Fast Start

For this monorepo checkout, use:

```bash
cd badminton-infra
docker compose -f docker-compose.app.yml -f docker-compose.cloudflare.yml up --build -d
```

For remote automation where `.env` is not already on disk, inject the tunnel token through the environment and run:

```bash
cd badminton-infra
CLOUDFLARED_TOKEN=replace-with-cloudflare-tunnel-connector-token ./deploy-cloudflare.sh
```

The helper also accepts `CLOUDFLARE_TUNNEL_TOKEN`, writes the ignored `.env`, and then starts the Compose stack.

The frontend publishes the app on `http://localhost:8080`, and the frontend Nginx proxies `/api/` to the backend service.

Compose services:

- `postgres`: database `badminton`, user `badminton_user`, password `strongpassword`.
- `redis`: cache/support service.
- `badminton-backend`: Flask API at container port `8000`, host port `8000`.
- `whatsapp-bot`: helper service for outbound WhatsApp automation at host port `3000`.
- `badminton-frontend`: Vue/Nginx frontend at container port `80`, host port `8080`.
- `cloudflared`: Cloudflare Tunnel connector; token is read from local ignored `.env`.

The older `docker-compose.yml` expects build contexts named `./backend` and `./frontend`; do not use it for this monorepo checkout unless those contexts are restored.

## Raspberry Pi Startup Service

The Pi has a `systemd` unit installed at:

```text
/etc/systemd/system/badminton-app.service
```

The source copy lives at:

```text
badminton-infra/badminton-app.service
```

It runs from `/home/admin/git-repo/badminton/badminton-infra`:

```bash
/usr/bin/docker compose -f docker-compose.app.yml -f docker-compose.cloudflare.yml up -d --remove-orphans
```

Boot state already configured:

- `docker.service` enabled.
- `badminton-app.service` enabled.
- `badminton-app.service` active after setup.

Useful commands:

```bash
sudo systemctl status badminton-app.service
sudo systemctl restart badminton-app.service
sudo systemctl stop badminton-app.service
journalctl -u badminton-app.service -n 100
docker compose -f docker-compose.app.yml -f docker-compose.cloudflare.yml ps
```

## Auto-Deploy From GitHub Main

Preferred push-triggered setup:

- `.github/workflows/pi-deploy.yml` runs on a self-hosted GitHub Actions runner with the custom label `pi5`.
- The runner should be installed on the Pi, preferably in `/home/admin/actions-runner`.
- The runner runs `/home/admin/git-repo/badminton/badminton-infra/update-from-main.sh` after each push to `main`.
- GitHub receives the push webhook; no inbound webhook listener or SSH port is required on the Pi.

Files:

- `update-from-main.sh`: fetches `origin/main`, compares it to local `HEAD`, pulls with `--ff-only` if changed, then runs `deploy-cloudflare.sh`.
- `badminton-auto-deploy.service`: one-shot systemd unit that runs the update script.
- `badminton-auto-deploy.timer`: polls every 5 minutes after boot.

Install on the Pi:

```bash
cd /home/admin/git-repo/badminton/badminton-infra
sudo cp badminton-auto-deploy.service /etc/systemd/system/
sudo cp badminton-auto-deploy.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now badminton-auto-deploy.timer
```

Check it:

```bash
systemctl list-timers badminton-auto-deploy.timer
journalctl -u badminton-auto-deploy.service -n 100
sudo systemctl start badminton-auto-deploy.service
```

After editing the service file, reinstall it:

```bash
sudo cp badminton-app.service /etc/systemd/system/badminton-app.service
sudo systemctl daemon-reload
sudo systemctl enable badminton-app.service
sudo systemctl restart badminton-app.service
```

## Expected `.env` for Compose

```dotenv
DATABASE_URL=postgresql://badminton_user:strongpassword@postgres:5432/badminton
SECRET_KEY=change-me
JWT_SECRET=change-this-for-prod
REDIS_URL=redis://redis:6379/0
FLASK_ENV=development
AUTH_MOCK=1
CLOUDFLARED_TOKEN=replace-with-cloudflare-tunnel-connector-token
```

Disable `AUTH_MOCK` and use strong secrets outside development.

## Nginx Routing

- `/api/` is proxied to `http://backend:8000/`.
- `/uploads/` is served from the mounted uploads volume.
- `/` is proxied to `http://frontend:80`.
- API requests are rate limited with `limit_req_zone` at `10r/s` and burst `20`.

Any change to service names or ports needs a coordinated update across Compose, Nginx, and any frontend or backend assumptions about reachable hosts.

## Kubernetes Fast Start

From `badminton-infra/infra`:

```bash
kubectl --context=pi-k3s-cluster apply -f k8s/namespace.yaml
kubectl --context=pi-k3s-cluster apply -f k8s/postgres-secret.yaml
kubectl --context=pi-k3s-cluster apply -f k8s/postgres-deployment.yaml
kubectl --context=pi-k3s-cluster apply -f k8s/postgres-service.yaml
kubectl --context=pi-k3s-cluster apply -f k8s/sql-init-configmap.yaml
kubectl --context=pi-k3s-cluster apply -f k8s/run-sql-job.yaml
kubectl --context=pi-k3s-cluster -n nieuwegein-badminton wait --for=condition=complete job/run-sql-init --timeout=300s
kubectl --context=pi-k3s-cluster -n nieuwegein-badminton logs job/run-sql-init
kubectl --context=pi-k3s-cluster apply -f k8s/deployment.yaml
```

The deployment manifest references:

- `ghcr.io/arnand1988/badminton-backend:latest`
- `ghcr.io/arnand1988/badminton-frontend:latest`

Ingress host:

- `nieuwegeinbadminton.nl`

## Working Notes

- The Kubernetes backend manifest currently sets `FLASK_ENV=development` and `AUTH_MOCK=1`; change this before production use.
- Secrets in the checked-in manifests are development placeholders. Use a secret manager or environment-specific sealed/external secrets for production.
- The backend Kubernetes `DATABASE_URL` points to service host `postgres` in namespace `nieuwegein-badminton`.
- The ingress routes only `/` to the frontend service. Make sure frontend production Nginx or cluster routing also sends `/api` to the backend if API calls need to work through the public host.
- Before changing ports or service names, update Docker Compose, Nginx config, Kubernetes service names, and the frontend API proxy assumptions together.
- Prefer `docker-compose.app.yml` for this monorepo checkout. The older `docker-compose.yml` expects different build contexts and is easy to break accidentally.
