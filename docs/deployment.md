# Deployment: From Your Laptop to the Internet

> Status: local and Docker setups are written; the GitHub Actions run happens on your next push.
> **Cloud hosting is a guide below, not yet done.** Don't list it on a CV as live until it is.

## 1. Three ways to run AEGIS

| Where | What runs | Good for |
|---|---|---|
| **Local, no Docker** | uvicorn + `npm run dev`, database on Neon | Daily development ([setup.md](setup.md)) |
| **Local, Docker Compose** | db, redis, api, web (+ prometheus, grafana) in containers | Checking the real production setup on your PC |
| **Cloud** | API on Google Cloud Run, dashboard on Vercel, database on Neon | A public link for your CV |

## 2. Docker Compose (whole stack on your PC)

1. Install **Docker Desktop**; wait for "Engine running".
2. In the project folder, copy `.env.example` to `.env` and fill in the three values. Use the generator command inside the file.
3. Run:

   ```powershell
   docker compose --profile app --profile monitoring up -d --build
   ```

4. Create the first admin inside the running API container:

   ```powershell
   docker compose exec api python -m app.cli create-user admin --role admin
   ```

5. Open:
   - the dashboard: http://localhost:8080;
   - the API docs: http://localhost:8000/docs;
   - Grafana: http://localhost:3000;
   - Prometheus: http://localhost:9090.
6. Docker Desktop → **Containers** → `aegis` shows every service, its logs and start/stop buttons.
7. Stop with `docker compose --profile app --profile monitoring down`. Add `-v` to **also delete the database volume** (all data).

**What's inside:**
- **api:** `python:3.12-slim` image.
  - Runs as a non-root user.
  - Runs `alembic upgrade head` on start, then uvicorn.
  - Has a health check.
- **web:** two-stage image. Node builds the dashboard, then only the static files are copied into a tiny nginx image. nginx serves the pages and forwards `/api` to the api container (same address, so no CORS needed).
- **db:** PostgreSQL with a named volume, so data survives restarts. It's not exposed to your network.
- **redis:** shared rate-limit counters.

## 3. CI: GitHub Actions (automatic checks)

`.github/workflows/ci.yml` runs on every push to `main` and on pull requests:

1. **Backend:**
   - ruff;
   - all 143 tests against a fresh PostgreSQL service;
   - `alembic check` (models and migrations agree).
2. **Frontend:** `npm ci` → typecheck → tests → build.
3. **Docker:**
   - builds both images;
   - starts the whole stack;
   - checks `/health/ready`, the dashboard page, and that `/api` through nginx refuses anonymous calls;
   - tears everything down.

After pushing: GitHub → your repo → **Actions** tab → click the run. A green tick means all passed; a red X means click it to see which step failed.

## 4. Cloud plan (step by step, when you're ready)

### 4.1 Database: Neon (already have it)
- Create a separate **production branch/project** in Neon; never use your development database for the public app.
- Copy its connection string (keep `sslmode=require`).

### 4.2 Backend: Google Cloud Run
**Cloud Run** runs a container and gives it an HTTPS address. It scales to zero when idle, so it's nearly free for a demo.

1. Create a Google Cloud project, link billing, and **create a budget alert** (Billing → Budgets) first.
2. Enable Cloud Run, Artifact Registry and Secret Manager.
3. Store `DATABASE_URL` and `JWT_SECRET` in **Secret Manager**, not as plain environment variables.
4. Build and push the image:

   ```powershell
   gcloud builds submit backend --tag REGION-docker.pkg.dev/PROJECT/aegis/api
   ```

5. Deploy with:
   - the secrets mapped to environment variables;
   - `CORS_ORIGINS` set to your Vercel address;
   - minimum instances 0.
6. **Migrations:**
   - with one instance, the start-up `alembic upgrade head` is fine;
   - with several, run migrations once as a **Cloud Run job** before deploying. Two instances migrating at the same moment can conflict.
7. Redis is optional at first. Without `REDIS_URL` each instance limits on its own (documented trade-off). Memorystore costs money.

### 4.3 Dashboard: Vercel
1. Import the GitHub repo in Vercel and set **Root directory** to `frontend`.
2. Environment variable `VITE_API_URL=https://<your-cloud-run-url>`.
3. Add a rewrite so deep links (e.g. `/incidents/123`) serve `index.html`. That's Vercel's SPA setting, or a `vercel.json` with a catch-all rewrite.
4. Deploy, then add the Vercel address to the API's `CORS_ORIGINS` and redeploy the API.

### 4.4 Automate it later
Extend CI with a deploy job that runs only on `main` after all checks pass. Authenticate GitHub to Google with
**Workload Identity Federation**: GitHub proves its identity to Google, so no long-lived service-account keys are stored in GitHub.

## 5. Production checklist

- [ ] Secrets only in Secret Manager / Vercel env; `.env` never uploaded
- [ ] Budget alert set
- [ ] `CORS_ORIGINS` lists exactly the dashboard address
- [ ] `/metrics` not publicly reachable (or protected)
- [ ] First admin created with a strong password; test accounts not present
- [ ] `/health/ready` used as the readiness check
- [ ] Logs visible in Cloud Logging (they're JSON, so fields are searchable)
- [ ] README updated with the live links, **only after** they work

## 6. Kubernetes (later, optional)

Kubernetes runs containers across many machines and restarts or replaces them automatically.
For AEGIS it's a **learning extension**, not a need: Cloud Run already gives HTTPS, scaling and restarts.

When you get there:
- use Docker Desktop's built-in Kubernetes or K3s;
- write a Deployment for the API, with `livenessProbe: /health/live`, `readinessProbe: /health/ready`, and resource requests/limits;
- add a Service, a Secret and a ConfigMap;
- run migrations as a Job;
- then practise a rolling update and killing a pod to watch it come back.
