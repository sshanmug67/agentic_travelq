# deploy-aws-ec2.yml — Dual Branch Workflow Explained

---

## What Changed (Before vs After)

```
BEFORE (single environment):                AFTER (dual environment):
─────────────────────────────               ─────────────────────────────
Trigger:  main only                         Trigger:  main AND dev
Tags:     :latest, :sha                     Tags:     :main-latest, :main-sha
                                                      :dev-latest, :dev-sha
Target:   EC2_HOST (one server)             Target:   EC2_HOST_PROD (main)
                                                      EC2_HOST_DEV  (dev)
```

---

## Section-by-Section Walkthrough

---

### Header & Trigger

```yaml                                       # EXPLANATION
name: Deploy TravelQ — AWS EC2                # Display name in GitHub Actions UI

on:
  push:
    branches: [main, dev]                     # ← CHANGED: was [main] only
                                              # Now triggers on BOTH branches
                                              # Push to main → builds + deploys to Prod EC2
                                              # Push to dev  → builds + deploys to Dev EC2
                                              # Push to any other branch → nothing happens
  workflow_dispatch:                           # Manual "Run workflow" button still works
```

**Key change:** Adding `dev` to the branches list is what enables the entire dual-environment pipeline.

---

### Global Variables

```yaml                                       # EXPLANATION
env:
  AWS_REGION: us-east-1                       # Same as before — no change
  ECR_BACKEND_REPOSITORY: travelq-backend     # Same ECR repo for both environments
  ECR_FRONTEND_REPOSITORY: travelq-frontend   # Tags separate them, not repos
```

**No change here.** Both environments share the same two ECR repos. The branch prefix in the tag (`main-latest` vs `dev-latest`) is what separates them.

---

### Job 1: Build & Push Backend

```yaml                                       # EXPLANATION
  build-backend:
    name: Build & Push Backend
    runs-on: ubuntu-latest

    steps:
      - name: Checkout code                   # Same — clones the repo
        uses: actions/checkout@v4

      - name: Configure AWS credentials       # Same — authenticates with AWS
        uses: aws-actions/configure-aws-credentials@v4
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: ${{ env.AWS_REGION }}

      - name: Login to Amazon ECR             # Same — authenticates Docker with ECR
        id: login-ecr
        uses: aws-actions/amazon-ecr-login@v2
```

**No changes above** — checkout, AWS auth, and ECR login are identical.

```yaml                                       # EXPLANATION
      - name: Build and push Backend image
        env:
          ECR_REGISTRY: ${{ steps... }}
          BRANCH: ${{ github.ref_name }}      # ← NEW: captures which branch triggered this
                                              #   If you pushed to main → BRANCH="main"
                                              #   If you pushed to dev  → BRANCH="dev"
          SHA: ${{ github.sha }}
        run: |
          SHORT_SHA=${SHA:0:7}                # First 7 chars of commit hash (e.g., ca85a10)
          cd backend
```

**Key addition:** `BRANCH: ${{ github.ref_name }}` — this is the variable that drives everything. GitHub automatically sets `github.ref_name` to the branch that was pushed.

```yaml                                       # EXPLANATION
          docker build --platform=linux/amd64 \
            -t $ECR_REGISTRY/$ECR_BACKEND_REPOSITORY:${BRANCH}-latest \
                                              # ← CHANGED: was just ":latest"
                                              # Now: ":main-latest" or ":dev-latest"
                                              # This means Prod and Dev images
                                              # coexist in the SAME ECR repo

            -t $ECR_REGISTRY/$ECR_BACKEND_REPOSITORY:${BRANCH}-${SHORT_SHA} .
                                              # ← CHANGED: was ":full-sha"
                                              # Now: ":main-ca85a10" or ":dev-ca85a10"
                                              # Allows rollback to specific commits
                                              # per environment

          docker push ...${BRANCH}-latest
          docker push ...${BRANCH}-${SHORT_SHA}
```

**Before vs After example:**

```
BEFORE (push to main):          AFTER (push to main):         AFTER (push to dev):
  :latest                         :main-latest                  :dev-latest
  :abc123...full-sha              :main-ca85a10                 :dev-ca85a10
```

---

### Job 2: Build & Push Frontend

Identical pattern to Job 1, just builds from `frontend/` with `Dockerfile.prod` and the `VITE_API_URL=/api` build arg. Same branch-prefixed tagging.

---

### Job 3: Deploy to EC2 (The Big Change)

This is where the magic happens — the same job deploys to different servers based on the branch.

```yaml                                       # EXPLANATION
  deploy-ec2:
    name: Deploy to EC2
    runs-on: ubuntu-latest
    needs: [build-backend, build-frontend]    # Waits for BOTH builds to finish
                                              # (same as before)
```

#### Step 1: Choose the target server

```yaml                                       # EXPLANATION
      - name: Set target EC2 host based on branch
        run: |
          if [ "${{ github.ref_name }}" = "main" ]; then
            echo "EC2_HOST=${{ secrets.EC2_HOST_PROD }}" >> $GITHUB_ENV
                                              # ← main branch → use Prod EC2 IP
            echo "DEPLOY_ENV=prod" >> $GITHUB_ENV
                                              # ← label for log messages
          else
            echo "EC2_HOST=${{ secrets.EC2_HOST_DEV }}" >> $GITHUB_ENV
                                              # ← dev branch → use Dev EC2 IP
            echo "DEPLOY_ENV=dev" >> $GITHUB_ENV
          fi
          echo "BRANCH=${{ github.ref_name }}" >> $GITHUB_ENV
                                              # ← pass branch name to next step
```

**This is the routing logic.** It's a simple if/else:
- `main` → SSH into `EC2_HOST_PROD`
- anything else → SSH into `EC2_HOST_DEV`

The `>> $GITHUB_ENV` syntax makes these variables available to ALL subsequent steps in the job.

**BEFORE:** The deploy step had `host: ${{ secrets.EC2_HOST }}` hardcoded — only one server.
**AFTER:** The host is dynamically set based on which branch was pushed.

---

#### Step 2: SSH into the chosen EC2 and deploy

```yaml                                       # EXPLANATION
      - name: Deploy via SSH
        uses: appleboy/ssh-action@v1
        with:
          host: ${{ env.EC2_HOST }}           # ← CHANGED: was ${{ secrets.EC2_HOST }}
                                              # Now uses the dynamically set variable
                                              # from the previous step
          username: ${{ secrets.EC2_USER }}    # Same — ec2-user
          key: ${{ secrets.EC2_SSH_KEY }}      # Same — shared SSH key
          envs: BRANCH                        # ← NEW: passes BRANCH variable into
                                              # the SSH session so the remote script
                                              # knows which branch it's deploying
```

**Inside the SSH script (runs ON the EC2 instance):**

```bash                                       # EXPLANATION
            set -e                            # Exit on any error (same as before)

            echo "🚀 Deploying TravelQ       # Log message now includes environment
              (${{ env.DEPLOY_ENV }})          # (prod or dev) and branch name
              from branch: $BRANCH"

            cd ~/agentic_travelq

            git fetch origin $BRANCH          # ← CHANGED: was "git pull origin main"
            git checkout $BRANCH              # ← NEW: switch to correct branch
            git pull origin $BRANCH           # Pull latest code for this branch
                                              #
                                              # BEFORE: always pulled main
                                              # AFTER:  pulls whichever branch triggered
                                              #
                                              # Prod EC2 will always be on main
                                              # Dev EC2 will always be on dev
```

```bash                                       # EXPLANATION
            # Login to ECR                    # Same as before — authenticate Docker
            aws ecr get-login-password ... | docker login ...

            # Set image tags for this branch
            export BACKEND_TAG=${BRANCH}-latest
            export FRONTEND_TAG=${BRANCH}-latest
                                              # ← NEW: tag variables
                                              # On Prod: BACKEND_TAG="main-latest"
                                              # On Dev:  BACKEND_TAG="dev-latest"

            # Pull branch-specific images
            docker pull .../travelq-backend:${BACKEND_TAG}
            docker pull .../travelq-frontend:${FRONTEND_TAG}
                                              # ← CHANGED: was pulling ":latest"
                                              # Now pulls the branch-specific tag
                                              # Prod pulls main-latest
                                              # Dev pulls dev-latest
```

```bash                                       # EXPLANATION
            # Tag as 'latest' for docker-compose
            docker tag .../travelq-backend:${BACKEND_TAG} \
                       .../travelq-backend:latest
            docker tag .../travelq-frontend:${FRONTEND_TAG} \
                       .../travelq-frontend:latest
                                              # ← NEW: re-tags branch image as :latest
                                              #
                                              # WHY? docker-compose.prod.yml references
                                              # images as ":latest". Rather than changing
                                              # the compose file per environment, we just
                                              # re-tag the correct branch image as :latest
                                              # on each EC2.
                                              #
                                              # On Prod EC2: main-latest → latest
                                              # On Dev EC2:  dev-latest  → latest
                                              # docker-compose doesn't need to change!
```

```bash                                       # EXPLANATION
            # Restart services                # Same as before
            docker compose -f docker-compose.prod.yml up -d

            # Cleanup old images              # Same — removes unused images
            docker image prune -f

            # Verify health                   # Same health check, but log message
            sleep 15                          # now shows which environment
            if curl -sf http://localhost/api/trips/health > /dev/null; then
              echo "✅ Deployment successful! TravelQ (${{ env.DEPLOY_ENV }}) is healthy."
            else
              echo "❌ Health check failed!"
              docker compose -f docker-compose.prod.yml logs --tail=50
              exit 1
            fi
```

---

## Complete Flow Diagram

```
Developer pushes to main:
  ┌─────────────────────────────────────────────────────────────┐
  │ GitHub Actions Runner                                       │
  │                                                             │
  │  Job 1: Build backend → tag as main-latest → push to ECR   │
  │  Job 2: Build frontend → tag as main-latest → push to ECR  │
  │  Job 3: SSH into EC2_HOST_PROD                              │
  │           → git checkout main                               │
  │           → docker pull main-latest                         │
  │           → docker tag main-latest → latest                 │
  │           → docker compose up -d                            │
  │           → health check ✅                                  │
  └─────────────────────────────────────────────────────────────┘

Developer pushes to dev:
  ┌─────────────────────────────────────────────────────────────┐
  │ GitHub Actions Runner                                       │
  │                                                             │
  │  Job 1: Build backend → tag as dev-latest → push to ECR    │
  │  Job 2: Build frontend → tag as dev-latest → push to ECR   │
  │  Job 3: SSH into EC2_HOST_DEV                               │
  │           → git checkout dev                                │
  │           → docker pull dev-latest                          │
  │           → docker tag dev-latest → latest                  │
  │           → docker compose up -d                            │
  │           → health check ✅                                  │
  └─────────────────────────────────────────────────────────────┘
```

---

## Summary of All Changes

| Line/Section | Before | After | Why |
|---|---|---|---|
| `branches:` | `[main]` | `[main, dev]` | Enable dev branch CI/CD |
| Image tags | `:latest`, `:sha` | `:main-latest`, `:main-sha`, `:dev-latest`, `:dev-sha` | Separate images per environment in same ECR |
| Deploy target | `secrets.EC2_HOST` | `secrets.EC2_HOST_PROD` or `secrets.EC2_HOST_DEV` | Route to correct server |
| Git on EC2 | `git pull origin main` | `git checkout $BRANCH && git pull origin $BRANCH` | EC2 tracks its own branch |
| Docker pull | Pull `:latest` | Pull `:branch-latest`, re-tag as `:latest` | docker-compose.prod.yml stays unchanged |
| Health log | Generic message | Includes environment name (prod/dev) | Easier to identify in logs |

---

## GitHub Secrets Reference

| Secret | Used By | Value |
|---|---|---|
| `AWS_ACCESS_KEY_ID` | Jobs 1, 2 | IAM access key for ECR push |
| `AWS_SECRET_ACCESS_KEY` | Jobs 1, 2 | IAM secret key for ECR push |
| `EC2_HOST_PROD` | Job 3 (main branch) | Prod EC2 public IP |
| `EC2_HOST_DEV` | Job 3 (dev branch) | Dev EC2 public IP |
| `EC2_USER` | Job 3 | `ec2-user` |
| `EC2_SSH_KEY` | Job 3 | SSH private key (travelq-key) |
| `ECR_REGISTRY_URI` | Job 3 | `589516862821.dkr.ecr.us-east-1.amazonaws.com` |