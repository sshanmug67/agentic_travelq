# docker-compose.prod.yml — Line by Line Explanation

## Overview — What This File Replaces

```
YOUR CURRENT LOCAL DEV SETUP:              THIS FILE (PRODUCTION):

PowerShell Terminal 1: Redis container     ┐
PowerShell Terminal 2: celery worker       ├→ One command: docker compose up -d
PowerShell Terminal 3: uvicorn main:app    │
Browser: npm run dev (Vite :3000)          ┘
```

You currently manage 4 things manually across 4 terminals.
This file defines all 4 as services so Docker manages them together.


---


## Line 18 — `version: '3.8'`

Specifies the Docker Compose file format version. 3.8 supports all features
we need (health checks, depends_on conditions, deploy options). Recent Docker
versions actually ignore this line, but it's good practice to include it for
backward compatibility.


---


## Lines 25-44 — NGINX SERVICE

```yaml
nginx:
    build:
      context: ./frontend
      dockerfile: Dockerfile.prod
      args:
        VITE_API_URL: /api
```

- `context: ./frontend` — Docker looks inside `frontend/` folder for the build
- `dockerfile: Dockerfile.prod` — Uses our multi-stage Dockerfile (not a default one)
- `args: VITE_API_URL: /api` — Passed into the Dockerfile as a build argument.
  Vite bakes this into the React bundle at build time, so all API calls go to
  `/api/...` (relative path). Nginx then proxies these to the backend container.

```yaml
    container_name: travelq-nginx
```
Gives the container a fixed name instead of a random one like `agentic_travelq-nginx-1`.
Makes it easier to find in `docker ps` and logs.

```yaml
    ports:
      - "80:80"
```
**Only service exposed to the outside world.**
Maps host port 80 → container port 80. This is how your browser reaches the app.
Compare with `expose: "8000"` on backend — which is internal only.

```yaml
    depends_on:
      backend:
        condition: service_healthy
```
**Startup order control.** Nginx won't start until the backend container passes
its health check. This prevents Nginx from trying to proxy to a backend that
isn't ready yet (which would cause 502 Bad Gateway errors).

Startup sequence: Redis → Backend (waits for Redis) → Nginx (waits for Backend)

```yaml
    restart: always
```
If the container crashes, Docker automatically restarts it. Also starts the
container when Docker itself starts (e.g., after EC2 reboot). Options are:
- `no` — never restart (default)
- `on-failure` — restart only on errors
- `always` — always restart (what we want for production)
- `unless-stopped` — like always, but respects manual `docker stop`

```yaml
    networks:
      - travelq-network
```
Connects this container to the private Docker network. Without this,
containers can't talk to each other.

```yaml
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```
**Log rotation.** Without this, Docker logs grow forever and can fill up the disk.
- `max-size: 10m` — each log file maxes out at 10MB
- `max-file: 3` — keep only 3 rotated files (30MB total max for nginx logs)

On a t3.small with 20GB disk, this prevents logs from eating all your storage.


---


## Lines 51-85 — BACKEND SERVICE (FastAPI)

```yaml
backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
```
Builds using `backend/Dockerfile` — the one with Python 3.12, Gunicorn, etc.

```yaml
    env_file:
      - .env.prod
```
**Loads ALL variables from `.env.prod` into the container.**
This is how your API keys (OPENAI, AMADEUS, GOOGLE_PLACES) get into the container.
It's equivalent to setting each one as an `environment:` entry, but cleaner.

```yaml
    environment:
      - REDIS_URL=redis://redis:6379/0
      - CELERY_BROKER_URL=redis://redis:6379/0
      - CELERY_RESULT_BACKEND=redis://redis:6379/0
      - APP_ENV=production
```
**These OVERRIDE anything in `.env.prod`** (environment > env_file priority).

Why separate from `.env.prod`? Because these use Docker service names (`redis`)
that only work inside Docker's network. In `.env.prod` you might have
`REDIS_URL=redis://localhost:6379/0` for local dev. This override ensures the
container always uses the correct Docker internal hostname.

`/0` at the end means Redis database 0 (Redis has databases 0-15 by default).

```yaml
    volumes:
      - ./config:/config:ro
```
**Mounts your project's config/ folder into the container.**

- `./config` — the `config/` folder in your project root (where app_config.yaml lives)
- `:/config` — appears at `/config` inside the container
- `:ro` — read-only (the container can read but not modify your config files)

Your `settings.py` does `Path(__file__).resolve().parent.parent.parent` which
resolves to `/` inside the container, then looks for `/config/app_config.yaml`.
This mount makes that path work.

```yaml
    expose:
      - "8000"
```
**Internal only** — other containers can reach port 8000, but your browser cannot.
Only Nginx (via `proxy_pass`) connects to this port. This is a security boundary.

```yaml
    depends_on:
      redis:
        condition: service_healthy
```
Backend won't start until Redis passes its health check (`redis-cli ping`).
FastAPI needs Redis for Celery task queuing — starting without Redis would
cause connection errors.

```yaml
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/trips/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
```
Docker runs this check to know if the backend is alive:

- `test` — calls your `/api/trips/health` endpoint. `-f` makes curl fail on HTTP errors.
- `interval: 30s` — check every 30 seconds
- `timeout: 10s` — if no response in 10s, count as failure
- `retries: 3` — 3 consecutive failures = container marked "unhealthy"
- `start_period: 40s` — give FastAPI 40 seconds to boot before checking
  (loading Python packages, connecting to Redis, initializing agents)

This health check is what Nginx's `depends_on: condition: service_healthy`
waits for. It's also what the Dockerfile's HEALTHCHECK does, but the
docker-compose version takes precedence.


---


## Lines 92-120 — CELERY WORKER SERVICE

```yaml
celery_worker:
    build:
      context: ./backend
      dockerfile: Dockerfile
```
**Uses the SAME Dockerfile as the backend.** Same Python packages, same code.
The only difference is the startup command.

```yaml
    command: celery -A celery_app worker --loglevel=info --concurrency=2
```
**Overrides the Dockerfile's CMD.** Instead of running Gunicorn (the FastAPI server),
this container runs a Celery worker — exactly what you type in PowerShell Terminal 2.

- `celery -A celery_app` — load the Celery app from celery_app.py
- `worker` — run as a worker (listens for tasks from Redis)
- `--loglevel=info` — show info-level logs
- `--concurrency=2` — run 2 worker threads (for t3.small's 2 vCPUs)

This is the power of Docker — one image, two containers, different commands:
```
backend container:        gunicorn main:app ...       (serves HTTP requests)
celery_worker container:  celery -A celery_app worker (processes background tasks)
```

```yaml
    depends_on:
      redis:
        condition: service_healthy
      backend:
        condition: service_healthy
```
Celery waits for BOTH Redis AND backend to be healthy:
- Redis — Celery needs it as the message broker
- Backend — ensures the API is ready before workers start processing tasks

The rest (env_file, environment, volumes, networks, logging) is identical
to the backend service — Celery needs the same API keys, Redis URLs,
config files, and network access.


---


## Lines 127-152 — REDIS SERVICE

```yaml
redis:
    image: redis:7-alpine
```
**No `build:` here** — unlike backend and nginx, Redis uses a pre-built public image
from Docker Hub. No Dockerfile needed. `7-alpine` means Redis version 7 on Alpine
Linux (tiny ~7MB image).

```yaml
    command: >
      redis-server
        --maxmemory 256mb
        --maxmemory-policy allkeys-lru
        --appendonly yes
        --appendfsync everysec
```
Overrides Redis's default config with production settings:

| Flag | What it does |
|---|---|
| `--maxmemory 256mb` | Cap Redis at 256MB RAM (prevents it from eating all memory) |
| `--maxmemory-policy allkeys-lru` | When full, evict **L**east **R**ecently **U**sed keys first |
| `--appendonly yes` | Write every operation to disk (persistence — survives restart) |
| `--appendfsync everysec` | Flush to disk every second (good balance of safety vs speed) |

Without `maxmemory`, Redis can grow until the EC2 instance runs out of RAM.
Without `appendonly`, all cached trip data is lost on container restart.

```yaml
    expose:
      - "6379"
```
Internal only — Redis should never be accessible from the internet.
Only backend and celery containers connect to it.

```yaml
    volumes:
      - redis-data:/data
```
**Named volume.** Redis writes its persistence files (appendonly.aof) to `/data`
inside the container. This volume maps to a Docker-managed location on the host.
Unlike container filesystems, volumes survive `docker compose down` and
`docker compose up` — your cached data persists across restarts.

```yaml
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
```
Runs `redis-cli ping` every 10 seconds. Redis responds with "PONG" if healthy.
Backend's `depends_on: condition: service_healthy` waits for this.
Checks more frequently than backend (10s vs 30s) because Redis starts fast.


---


## Lines 160-162 — NETWORK

```yaml
networks:
  travelq-network:
    driver: bridge
```
Creates an isolated virtual network. `bridge` is the default Docker network driver —
it creates a software bridge that lets containers communicate using service names.

Docker automatically runs a DNS server on this network:
- `redis` resolves to Redis container's IP
- `backend` resolves to Backend container's IP

Without this, containers would be isolated and unable to reach each other.


---


## Lines 167-169 — VOLUMES

```yaml
volumes:
  redis-data:
    driver: local
```
Declares a named volume managed by Docker. `local` driver stores data on the
host filesystem (under `/var/lib/docker/volumes/` on Linux).

Named volumes vs bind mounts:
- **Named volume** (`redis-data:/data`) — Docker manages the location, persists across restarts
- **Bind mount** (`./config:/config`) — You specify the exact host path, maps a folder you control

We use named volume for Redis because we don't need to access the raw data files.
We use bind mount for config because we want to control the exact file from our project.


---


## STARTUP SEQUENCE

When you run `docker compose -f docker-compose.prod.yml up -d`:

```
Step 1: Docker creates travelq-network
Step 2: Docker creates redis-data volume (if not exists)
Step 3: Start Redis
        └── health check: redis-cli ping → PONG ✅
Step 4: Start Backend (waited for Redis healthy)
        └── health check: curl /api/trips/health → 200 OK ✅
Step 5: Start Celery Worker (waited for Redis + Backend healthy)
Step 6: Start Nginx (waited for Backend healthy)
        └── health check: wget localhost:80 → 200 OK ✅

Total time: ~60 seconds on first boot
```

If any service crashes, `restart: always` brings it back automatically.


---


## COMPARISON: LOCAL DEV vs PRODUCTION

| Aspect | Local (your PowerShell) | Production (this file) |
|---|---|---|
| Start Redis | Open Docker Desktop, start container | `docker compose up` handles it |
| Start Celery | `celery -A celery_app worker` in Terminal 2 | Automatic, with restart |
| Start FastAPI | `uvicorn main:app --reload` in Terminal 3 | Gunicorn + 2 workers, no reload |
| Start Frontend | `npm run dev` (:3000) | Pre-built, served by Nginx |
| Environment | .env at project root | .env.prod loaded by docker-compose |
| Redis address | localhost:6379 | redis:6379 (Docker DNS) |
| API URL | http://localhost:8000 | /api (Nginx proxies) |
| Crash recovery | You restart manually | Automatic (`restart: always`) |
| Health checks | None | Automated, containers wait for dependencies |
| Log management | Scrolls forever in terminal | Rotated, max 10MB per file |