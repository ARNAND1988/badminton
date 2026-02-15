Kubernetes helper: run SQL in `nieuwegein-badminton` namespace

This folder contains manifests to create the namespace, a Secret with the Postgres password, a ConfigMap with `init.sql`, and a Job that runs the SQL against the Postgres service in-cluster.

Quick apply (this will create namespace, secret, configmap, job, then wait for completion and show job logs):

```bash
# from the repo root
kubectl --context=pi-k3s-cluster apply -f k8s/namespace.yaml
kubectl --context=pi-k3s-cluster apply -f k8s/postgres-secret.yaml
kubectl --context=pi-k3s-cluster apply -f k8s/sql-init-configmap.yaml
kubectl --context=pi-k3s-cluster apply -f k8s/run-sql-job.yaml
kubectl --context=pi-k3s-cluster -n nieuwegein-badminton wait --for=condition=complete job/run-sql-init --timeout=300s
kubectl --context=pi-k3s-cluster -n nieuwegein-badminton logs job/run-sql-init
```

If you prefer to create the Secret/ConfigMap from local files manually:

```bash
kubectl --context=pi-k3s-cluster -n nieuwegein-badminton create secret generic postgres-creds --from-literal=password=strongpassword
kubectl --context=pi-k3s-cluster -n nieuwegein-badminton create configmap sql-init --from-file=init.sql=k8s/init.sql
```

Cleanup:

```bash
kubectl --context=pi-k3s-cluster -n nieuwegein-badminton delete job/run-sql-init
kubectl --context=pi-k3s-cluster -n nieuwegein-badminton delete configmap sql-init
kubectl --context=pi-k3s-cluster -n nieuwegein-badminton delete secret postgres-creds
kubectl --context=pi-k3s-cluster delete namespace nieuwegein-badminton
```

Notes:
- The Job uses the Postgres host `postgres` inside the namespace. If your in-cluster Service is named differently, edit `k8s/run-sql-job.yaml`.
- For production use store credentials in an external secret manager and set appropriate Job retries/backoff.
