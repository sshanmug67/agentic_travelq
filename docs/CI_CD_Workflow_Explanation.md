# TravelQ CI/CD Workflow — Detailed Explanation

## Overview

This GitHub Actions workflow automates the full deployment pipeline for the **TravelQ** application. Every time code is pushed to `main` (or the workflow is triggered manually), it builds Docker images, pushes them to AWS ECR, and deploys to an EC2 instance.

---

## Trigger Events

```yaml
on:
  push:
    branches: [main]
  workflow_dispatch:
```

- **`push → main`**: The pipeline runs automatically whenever a commit lands on the `main` branch (direct push or merged PR).
- **`workflow_dispatch`**: Allows you to trigger the workflow manually from the GitHub Actions UI — useful for redeployments without a code change.

---

## Environment Variables

```yaml
env:
  AWS_REGION: us-east-1
  ECR_BACKEND_REPOSITORY: travelq-backend
  ECR_FRONTEND_REPOSITORY: travelq-frontend
```

These are **workflow-level** environment variables available to all jobs:

| Variable | Purpose |
|---|---|
| `AWS_REGION` | The AWS region where your ECR repositories and EC2 instance live |
| `ECR_BACKEND_REPOSITORY` | The name of the ECR repository for the backend Docker image |
| `ECR_FRONTEND_REPOSITORY` | The name of the ECR repository for the frontend Docker image |

---

## Job 1: `build-backend` — Build & Push Backend Image

**Runs on:** `ubuntu-latest` (a fresh GitHub-hosted runner)

### Step-by-Step Breakdown

#### Step 1: Checkout Code
```yaml
- uses: actions/checkout@v4
```
Clones your repository onto the runner so subsequent steps can access your source code and Dockerfiles.

#### Step 2: Configure AWS Credentials
```yaml
- uses: aws-actions/configure-aws-credentials@v4
  with:
    aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
    aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
    aws-region: ${{ env.AWS_REGION }}
```
Sets up the AWS CLI environment on the runner using your IAM credentials stored as GitHub secrets. This allows subsequent AWS-related steps (like ECR login) to authenticate.

#### Step 3: Login to Amazon ECR
```yaml
- uses: aws-actions/amazon-ecr-login@v2
  id: login-ecr
```
Authenticates Docker with your private ECR registry. The `id: login-ecr` lets later steps reference the output — specifically `steps.login-ecr.outputs.registry`, which contains the full registry URL (e.g., `123456789.dkr.ecr.us-east-1.amazonaws.com`).

#### Step 4: Build and Push Backend Image
```yaml
run: |
  cd backend
  docker build --platform=linux/amd64 \
    -t $ECR_REGISTRY/$ECR_BACKEND_REPOSITORY:$IMAGE_TAG \
    -t $ECR_REGISTRY/$ECR_BACKEND_REPOSITORY:latest .
  docker push $ECR_REGISTRY/$ECR_BACKEND_REPOSITORY:$IMAGE_TAG
  docker push $ECR_REGISTRY/$ECR_BACKEND_REPOSITORY:latest
```

- **`cd backend`** — Navigates into the backend directory where the `Dockerfile` lives.
- **`--platform=linux/amd64`** — Forces the build to target x86_64 architecture, which is important if the runner or your local machine uses ARM (e.g., Apple Silicon). Your EC2 instance is likely x86_64.
- **Two tags are applied:**
  - `:<commit-sha>` — A unique, immutable tag tied to the exact commit. Useful for rollbacks and traceability.
  - `:latest` — A mutable tag that always points to the most recent build. Used by your EC2 deployment to pull the newest image.
- **Both tags are pushed** to ECR separately.

---

## Job 2: `build-frontend` — Build & Push Frontend Image

This job is structurally identical to `build-backend` with a few key differences:

### Key Differences from Backend Build

```yaml
run: |
  cd frontend
  docker build --platform=linux/amd64 \
    -f Dockerfile.prod \
    --build-arg VITE_API_URL=/api \
    -t $ECR_REGISTRY/$ECR_FRONTEND_REPOSITORY:$IMAGE_TAG \
    -t $ECR_REGISTRY/$ECR_FRONTEND_REPOSITORY:latest .
```

- **`-f Dockerfile.prod`** — Uses a production-specific Dockerfile (separate from the development one). This likely contains a multi-stage build: first building the Vite app, then serving the static output via Nginx.
- **`--build-arg VITE_API_URL=/api`** — Passes an environment variable into the Docker build process. Since Vite bakes environment variables into the JavaScript bundle at build time (not runtime), this tells the frontend to send API requests to `/api` on the same domain. Nginx then proxies those requests to the backend container.

### Parallel Execution

Jobs 1 and 2 run **in parallel** since neither has a `needs` dependency. This cuts your build time roughly in half compared to running them sequentially.

---

## Job 3: `deploy-ec2` — Deploy to EC2

```yaml
deploy-ec2:
  needs: [build-backend, build-frontend]
```

The `needs` keyword ensures this job **only starts after both build jobs succeed**. If either build fails, deployment is skipped entirely.

### The SSH Deployment Script

The entire deployment is executed over SSH using `appleboy/ssh-action@v1`. Here is what each section does:

#### 1. Pull Latest Code
```bash
set -e
cd ~/agentic-travelq
git pull origin main
```
- **`set -e`** — Exit immediately if any command fails. This prevents a broken deployment from continuing silently.
- **`cd ~/agentic-travelq`** — Navigate to the project directory on the EC2 instance.
- **`git pull origin main`** — Pull the latest code, which includes any updated `docker-compose.prod.yml` or configuration files.

#### 2. Login to ECR from EC2
```bash
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin \
  ${{ secrets.ECR_REGISTRY_URI }}
```
This authenticates the EC2 instance's Docker daemon with ECR so it can pull private images. The password is generated by `aws ecr get-login-password` and piped directly into `docker login`.

> **⚠️ Note:** This references `secrets.ECR_REGISTRY_URI`, which is **not currently in your GitHub secrets**. You need to add it. See the Secrets section below.

#### 3. Pull Latest Images
```bash
docker compose -f docker-compose.prod.yml pull backend
docker compose -f docker-compose.prod.yml pull nginx
```
Pulls only the `backend` and `nginx` (frontend) service images. This is more efficient than pulling all services if you have other services (like a database) that use local or unchanged images.

#### 4. Restart Services
```bash
docker compose -f docker-compose.prod.yml up -d --build
```
- **`up -d`** — Starts all services in detached mode (background).
- **`--build`** — Rebuilds any services that have local Dockerfiles, while using the already-pulled ECR images for backend and nginx.

#### 5. Cleanup
```bash
docker image prune -f
```
Removes dangling (unused) images to free up disk space on the EC2 instance. Over time, old image layers accumulate and can fill up the disk.

#### 6. Health Check
```bash
sleep 15
if curl -sf http://localhost/api/trips/health > /dev/null; then
  echo "Deployment successful! TravelQ is healthy."
else
  echo "Health check failed!"
  docker compose -f docker-compose.prod.yml logs --tail=50
  exit 1
fi
```
- **Waits 15 seconds** for containers to fully start.
- **Hits the health endpoint** (`/api/trips/health`) silently (`-sf` = silent + fail on HTTP errors).
- **If healthy** — prints a success message.
- **If unhealthy** — dumps the last 50 lines of logs from all services and exits with code 1, marking the GitHub Actions run as **failed**. This gives you immediate visibility into what went wrong.

---

## Required GitHub Secrets

| Secret Name | Used In | Purpose |
|---|---|---|
| `AWS_ACCESS_KEY_ID` | Jobs 1 & 2 | IAM access key for authenticating with AWS on the GitHub runner |
| `AWS_SECRET_ACCESS_KEY` | Jobs 1 & 2 | IAM secret key paired with the access key |
| `EC2_HOST` | Job 3 | Public IP or hostname of your EC2 instance |
| `EC2_USER` | Job 3 | SSH username (typically `ubuntu` or `ec2-user`) |
| `EC2_SSH_KEY` | Job 3 | Private SSH key for connecting to the EC2 instance |
| `ECR_REGISTRY_URI` | Job 3 | ECR registry base URL (e.g., `123456789.dkr.ecr.us-east-1.amazonaws.com`) |

### Secrets You Currently Have But the Workflow Doesn't Use

| Secret Name | Status |
|---|---|
| `AWS_REGION` | Unused — the region is hardcoded in the workflow as `us-east-1` |
| `ECR_BACKEND_URI` | Unused — the workflow constructs image URIs from the ECR login output + repository name env vars |
| `ECR_FRONTEND_URI` | Unused — same as above |

### Secret You Need to Add

| Secret Name | Status |
|---|---|
| `ECR_REGISTRY_URI` | **Missing** — required by the deploy job's ECR login command on the EC2 instance |

---

## Visual Pipeline Flow

```
Push to main / Manual trigger
         │
         ▼
  ┌──────────────────────────────────────┐
  │         Parallel Build Phase         │
  │                                      │
  │  ┌──────────────┐ ┌──────────────┐   │
  │  │ build-backend│ │build-frontend│   │
  │  │              │ │              │   │
  │  │ 1. Checkout  │ │ 1. Checkout  │   │
  │  │ 2. AWS Auth  │ │ 2. AWS Auth  │   │
  │  │ 3. ECR Login │ │ 3. ECR Login │   │
  │  │ 4. Build     │ │ 4. Build     │   │
  │  │ 5. Push      │ │ 5. Push      │   │
  │  └──────┬───────┘ └──────┬───────┘   │
  │         │                │           │
  └─────────┼────────────────┼───────────┘
            │                │
            ▼                ▼
      Both must succeed (needs)
                 │
                 ▼
  ┌──────────────────────────────┐
  │       deploy-ec2             │
  │                              │
  │  1. SSH into EC2             │
  │  2. git pull latest code     │
  │  3. ECR login on EC2         │
  │  4. Pull new images          │
  │  5. docker compose up        │
  │  6. Prune old images         │
  │  7. Health check             │
  │     ├─ ✅ Success → Done     │
  │     └─ ❌ Fail → Dump logs   │
  └──────────────────────────────┘
```

---

## Key Concepts Recap

- **ECR (Elastic Container Registry):** AWS's private Docker image storage. Your images are pushed here by the GitHub runner and pulled from here by the EC2 instance.
- **Commit SHA tagging:** Every build is tagged with the git commit hash, giving you an immutable record of exactly which code is in each image. You can roll back by redeploying a previous SHA.
- **`:latest` tag:** A convenience tag that always points to the newest image. The EC2 deployment pulls `:latest` via `docker compose pull`.
- **Health check:** Acts as a deployment gate — if the app doesn't respond correctly after deploy, the workflow fails and you're alerted immediately.