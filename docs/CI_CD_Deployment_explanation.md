# deploy.yml — Deep Dive Explanation + CI/CD Guide

---

## Part 1: What is CI/CD?

### The Problem CI/CD Solves

Without CI/CD, every time you change code, you'd do this manually:

```
1. git push
2. SSH into EC2
3. git pull
4. docker compose build
5. docker compose up -d
6. Check health
7. Pray it worked

Manual, error-prone, tedious
```

With CI/CD, you do this:

```
1. git push
2. Done.

GitHub Actions handles the rest automatically.
```

### CI/CD Stands For

**CI = Continuous Integration**
Every time code is pushed, it's automatically built and tested.
"Does the new code even work? Can it compile/build without errors?"

**CD = Continuous Deployment**
After CI passes, the code is automatically deployed to production.
"Push the working code live — no human needed."

```
Developer → git push → CI (Build & Test) → CD (Deploy) → Live on EC2
                         automated            automated
```

### How GitHub Actions Fits In

GitHub Actions is GitHub's built-in CI/CD platform. It runs your
workflow on **GitHub's own servers** (called "runners") — not on
your machine, and not on EC2.

```
Your PC                    GitHub Runners              Your EC2
(just pushes code)         (does the heavy lifting)    (receives the deploy)

git push ──────────────►   1. Checkout code
                           2. Login to AWS
                           3. Build Docker image
                           4. Push image to ECR
                           5. SSH into EC2 ──────────►  Pull latest code
                                                        Restart containers
                                                        Health check
```

GitHub provides **2,000 free minutes/month** for private repos
(unlimited for public repos). Each workflow run takes ~4-5 minutes,
so you get roughly 400+ free deploys per month.

### Key CI/CD Vocabulary

| Term | Meaning |
|------|---------|
| **Workflow** | The entire automation file (deploy.yml) |
| **Job** | A group of steps that run on the same machine |
| **Step** | A single task within a job (checkout, build, etc.) |
| **Runner** | The GitHub-hosted VM that executes the workflow |
| **Trigger** | What starts the workflow (push, manual, schedule) |
| **Action** | A reusable plugin (e.g., `actions/checkout@v4`) |
| **Secret** | Encrypted variable stored in GitHub settings |
| **Artifact** | Output from a build (e.g., Docker image) |

---

## Part 2: The Complete deploy.yml File

```yaml
# .github/workflows/deploy.yml
name: Deploy TravelQ

on:
  push:
    branches: [main]
  workflow_dispatch:

env:
  AWS_REGION: us-east-1
  ECR_REPOSITORY: travelq-backend

jobs:
  build-backend:
    name: Build & Push Backend
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: ${{ env.AWS_REGION }}

      - name: Login to Amazon ECR
        id: login-ecr
        uses: aws-actions/amazon-ecr-login@v2

      - name: Build and push Docker image
        env:
          ECR_REGISTRY: ${{ steps.login-ecr.outputs.registry }}
          IMAGE_TAG: ${{ github.sha }}
        run: |
          cd backend
          docker build --platform=linux/amd64 \
            -t $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG \
            -t $ECR_REGISTRY/$ECR_REPOSITORY:latest .
          docker push $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG
          docker push $ECR_REGISTRY/$ECR_REPOSITORY:latest

  deploy-ec2:
    name: Deploy to EC2
    runs-on: ubuntu-latest
    needs: build-backend
    steps:
      - name: Deploy via SSH
        uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.EC2_HOST }}
          username: ec2-user
          key: ${{ secrets.EC2_SSH_KEY }}
          script: |
            set -e
            cd ~/agentic-travelq
            git pull origin main
            aws ecr get-login-password --region us-east-1 | \
              docker login --username AWS --password-stdin \
              ${{ secrets.AWS_ACCOUNT_ID }}.dkr.ecr.us-east-1.amazonaws.com
            docker compose -f docker-compose.prod.yml pull backend
            docker compose -f docker-compose.prod.yml up -d --build
            docker image prune -f
            sleep 10
            if curl -sf http://localhost/health > /dev/null; then
              echo "Deployment successful! TravelQ is healthy."
            else
              echo "Health check failed!"
              docker compose -f docker-compose.prod.yml logs --tail=50
              exit 1
            fi
```

---

## Part 3: Line-by-Line Breakdown

---

### File Location

```
AGENTIC_TRAVELQ/
├── .github/
│   └── workflows/
│       └── deploy.yml     ← THIS FILE
```

GitHub automatically detects any `.yml` file inside `.github/workflows/`
and registers it as a workflow. The folder structure is mandatory —
GitHub won't find it anywhere else.

---

### Trigger — `on:` (Lines 3–6)

```yaml
on:
  push:
    branches: [main]
  workflow_dispatch:
```

| Trigger | What It Does |
|---------|--------------|
| `push: branches: [main]` | Runs automatically when you push to `main` |
| `workflow_dispatch` | Adds a "Run workflow" button in GitHub UI |

**Important:** Pushing to other branches (feature branches, dev) does
NOT trigger deployment. Only `main` deploys to production.

This is a safety measure. You can develop on feature branches freely
without accidentally deploying half-finished work.

```
git push origin feature/new-ui     → Nothing happens (safe)
git push origin main               → Auto-deploy triggered
```

`workflow_dispatch` is useful for re-deploying without a code change,
or for debugging the workflow itself.

---

### Global Variables — `env:` (Lines 8–10)

```yaml
env:
  AWS_REGION: us-east-1
  ECR_REPOSITORY: travelq-backend
```

Variables available to ALL jobs and steps. Avoids hardcoding
`us-east-1` and `travelq-backend` in multiple places.

If you ever change regions or rename the ECR repo, you only
update it here — not in every step.

---

### Job 1: Build & Push Backend

---

#### Job Configuration (Lines 13–16)

```yaml
jobs:
  build-backend:
    name: Build & Push Backend
    runs-on: ubuntu-latest
```

| Part | Meaning |
|------|---------|
| `build-backend` | Internal job ID (used by other jobs to reference it) |
| `name` | Display name shown in GitHub Actions UI |
| `runs-on: ubuntu-latest` | Run on a GitHub-hosted Ubuntu VM |

The GitHub runner is a **fresh, clean Linux VM** that GitHub provides.
It has Docker, AWS CLI, Node.js, Python, and common tools pre-installed.
After the workflow finishes, the VM is destroyed — nothing persists.

---

#### Step 1: Checkout Code

```yaml
- name: Checkout code
  uses: actions/checkout@v4
```

Clones your GitHub repo onto the runner VM. `actions/checkout` is
GitHub's official checkout action. `@v4` means version 4.

Think of it as running `git clone your-repo` on the runner.

Without this step, the runner has no code to build.

---

#### Step 2: Configure AWS Credentials

```yaml
- name: Configure AWS credentials
  uses: aws-actions/configure-aws-credentials@v4
  with:
    aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
    aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
    aws-region: ${{ env.AWS_REGION }}
```

Sets up AWS CLI on the runner with your IAM credentials.

**`${{ secrets.XXX }}`** reads from GitHub Secrets — encrypted values
stored in your repo settings (Settings → Secrets and variables → Actions).

GitHub **never exposes** these in logs. Even if a step tries to `echo`
a secret, GitHub masks it with `***`.

**These are NOT your OpenAI/Amadeus API keys.** These are IAM credentials
specifically for the GitHub runner to interact with AWS services (ECR, EC2).

---

#### Step 3: Login to Amazon ECR

```yaml
- name: Login to Amazon ECR
  id: login-ecr
  uses: aws-actions/amazon-ecr-login@v2
```

Authenticates Docker on the runner with your ECR (Elastic Container Registry).

**ECR** is AWS's private Docker Hub — it stores your Docker images securely.
Only your AWS account can push/pull images from it.

`id: login-ecr` gives this step a name so later steps can reference
its output. Specifically, the next step uses:
```
${{ steps.login-ecr.outputs.registry }}
```
which resolves to something like:
```
589516862821.dkr.ecr.us-east-1.amazonaws.com
```

---

#### Step 4: Build and Push Docker Image

```yaml
- name: Build and push Docker image
  env:
    ECR_REGISTRY: ${{ steps.login-ecr.outputs.registry }}
    IMAGE_TAG: ${{ github.sha }}
  run: |
    cd backend
    docker build --platform=linux/amd64 \
      -t $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG \
      -t $ECR_REGISTRY/$ECR_REPOSITORY:latest .
    docker push $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG
    docker push $ECR_REGISTRY/$ECR_REPOSITORY:latest
```

This is the **core build step**. Let's break it down piece by piece:

**Environment variables for this step:**

| Variable | Resolves To | Source |
|----------|-------------|--------|
| `ECR_REGISTRY` | `589516862821.dkr.ecr.us-east-1.amazonaws.com` | From ECR login output |
| `IMAGE_TAG` | `a1b2c3d4e5f6` (git commit hash) | From `github.sha` |
| `ECR_REPOSITORY` | `travelq-backend` | From global `env` |

**The `docker build` command:**

```bash
cd backend
# Navigate into backend/ where the Dockerfile lives

docker build --platform=linux/amd64 \
# --platform=linux/amd64 forces building for Intel/AMD 64-bit
# EC2 uses amd64. Without this, if the runner were ARM-based,
# the image wouldn't work on EC2

  -t $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG \
# Tag 1: the full ECR path + git commit hash
# Example: 589516862821.dkr.ecr.us-east-1.amazonaws.com/travelq-backend:a1b2c3d4
# Every deploy gets a UNIQUE tag — enables rollbacks

  -t $ECR_REGISTRY/$ECR_REPOSITORY:latest .
# Tag 2: same image also tagged as "latest"
# Convenience tag that always points to newest build
```

**Why two tags?**

```
Tag 1 (commit hash):  travelq-backend:a1b2c3d4   ← unique, for rollbacks
Tag 2 (latest):       travelq-backend:latest      ← convenience, always newest

If deploy breaks:
  docker pull travelq-backend:previous-commit-hash   ← instant rollback
```

**The `docker push` commands:**

```bash
docker push $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG
docker push $ECR_REGISTRY/$ECR_REPOSITORY:latest
```

Uploads both tagged images to ECR. The image is now stored in AWS,
ready to be pulled by EC2.

---

### Job 2: Deploy to EC2

---

#### Job Configuration

```yaml
deploy-ec2:
  name: Deploy to EC2
  runs-on: ubuntu-latest
  needs: build-backend
```

| Part | Meaning |
|------|---------|
| `needs: build-backend` | **Wait for Job 1 to finish** before starting |
| `runs-on: ubuntu-latest` | Runs on a fresh runner (different VM from Job 1) |

`needs` creates a dependency chain:

```
build-backend ──(must succeed)──► deploy-ec2

If build fails → deploy never runs → EC2 stays on old version (safe)
```

---

#### Step 5: Deploy via SSH

```yaml
- name: Deploy via SSH
  uses: appleboy/ssh-action@v1
  with:
    host: ${{ secrets.EC2_HOST }}
    username: ec2-user
    key: ${{ secrets.EC2_SSH_KEY }}
    script: |
      ...commands...
```

`appleboy/ssh-action` is a popular community action that handles
SSH connections. It connects from the GitHub runner to your EC2 instance:

```
GitHub Runner ────SSH────► EC2 Instance
                           (runs the script commands)
```

| Parameter | Value | Meaning |
|-----------|-------|---------|
| `host` | `secrets.EC2_HOST` | Your EC2 Elastic IP address |
| `username` | `ec2-user` | Default user on Amazon Linux |
| `key` | `secrets.EC2_SSH_KEY` | Contents of your .pem file |

**`secrets.EC2_SSH_KEY`** is the entire contents of your `travelq-key.pem`
file — pasted into GitHub Secrets. Not the file path, the actual content.

---

#### The Deploy Script (Runs ON EC2)

Everything inside `script: |` runs on EC2, not the GitHub runner:

```bash
set -e
```
Same as ec2-setup.sh — stop on first error.

```bash
cd ~/agentic-travelq
git pull origin main
```
Navigate to the project and pull the latest code. This gets updated
docker-compose files, configs, etc. The Docker **image** comes from ECR,
but the compose file and other configs come from git.

```bash
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin \
  589516862821.dkr.ecr.us-east-1.amazonaws.com
```
Login to ECR from EC2 so Docker can pull the new image.
The `|` pipe passes the ECR password directly to `docker login`.
`--password-stdin` reads the password from the pipe (more secure than
passing it as a command line argument).

```bash
docker compose -f docker-compose.prod.yml pull backend
```
Pull the new backend image from ECR. Only pulls backend because
redis and nginx use public images that rarely change.

```bash
docker compose -f docker-compose.prod.yml up -d --build
```
Restart the stack with the new image.
- `-d` = detached mode (run in background)
- `--build` = rebuild any locally-built images

```bash
docker image prune -f
```
Delete old, unused images. Without this, every deploy leaves behind
the previous image, and your 20GB disk fills up over time.
`-f` = force (don't ask for confirmation).

```bash
sleep 10
```
Wait 10 seconds for containers to fully start. FastAPI needs a moment
to initialize, connect to Redis, etc.

```bash
if curl -sf http://localhost/health > /dev/null; then
  echo "Deployment successful! TravelQ is healthy."
else
  echo "Health check failed!"
  docker compose -f docker-compose.prod.yml logs --tail=50
  exit 1
fi
```

**Health check** — the most important part of any deploy:

| Part | Meaning |
|------|---------|
| `curl -sf` | `-s` = silent, `-f` = fail on HTTP errors (4xx, 5xx) |
| `http://localhost/health` | Hits the backend health endpoint through nginx |
| `> /dev/null` | We only care if it succeeds, not the output |
| `exit 1` | If health check fails, mark the deploy as **failed** |

If the health check fails, the workflow shows a red X in GitHub,
and the last 50 lines of logs are printed for debugging.

---

## Part 4: GitHub Secrets Setup

You need to add 5 secrets to your GitHub repo:

**Location:** GitHub repo → Settings → Secrets and variables → Actions

| Secret Name | Value | Where You Get It |
|-------------|-------|------------------|
| `AWS_ACCESS_KEY_ID` | `AKIA...` | IAM console → Your user → Security credentials |
| `AWS_SECRET_ACCESS_KEY` | `wJalr...` | Same place (shown once when created) |
| `AWS_ACCOUNT_ID` | `589516862821` | `aws sts get-caller-identity` |
| `EC2_HOST` | `54.123.45.67` | Your Elastic IP from EC2 setup |
| `EC2_SSH_KEY` | `-----BEGIN RSA PRIVATE KEY-----\n...` | Contents of `travelq-key.pem` |

For `EC2_SSH_KEY`, open the .pem file in a text editor, copy the
**entire contents** (including the BEGIN/END lines), and paste it
into the secret value field.

---

## Part 5: The Full Deploy Timeline

```
0:00   You run: git push origin main
0:05   GitHub detects push to main, triggers workflow
0:10   Runner starts, checks out code
0:15   AWS credentials configured
0:20   ECR login successful
0:25   docker build starts (this takes 2-5 minutes)
3:00   Image built, pushing to ECR
3:30   Job 1 complete, Job 2 starts
3:35   SSH connection to EC2 established
3:40   git pull on EC2
3:45   ECR login on EC2
3:50   Pulling new image from ECR
4:00   docker compose up -d — containers restarting
4:10   Health check: curl http://localhost/health
4:15   ✅ Deploy complete!
```

**Total time: ~4-5 minutes from push to live.**

---

## Part 6: What Happens When Things Go Wrong

### Build Fails

```
Job 1: build-backend  →  ❌ FAILED (Dockerfile error)
Job 2: deploy-ec2     →  ⏭️ SKIPPED (needs: build-backend)

EC2: Still running the OLD version (safe!)
```

### Deploy Fails

```
Job 1: build-backend  →  ✅ SUCCESS
Job 2: deploy-ec2     →  ❌ FAILED (health check failed)

EC2: New containers started but unhealthy
Action: Check logs in GitHub Actions output, SSH in to debug
```

### How to Rollback

```bash
# SSH into EC2
ssh -i travelq-key.pem ec2-user@YOUR_IP

# Pull the previous working image by commit hash
docker pull 589516862821.dkr.ecr.us-east-1.amazonaws.com/travelq-backend:PREVIOUS_HASH

# Restart with old image
docker compose -f docker-compose.prod.yml up -d
```

---

## Part 7: Visual Summary

```
┌─────────────────────────────────────────────────────────────┐
│                    YOUR DEVELOPMENT FLOW                     │
│                                                             │
│   Code Change → git push main → GitHub Actions → Live App   │
│                                                             │
│   ┌──────────┐   ┌────────────────┐   ┌──────────────────┐ │
│   │  Your PC  │──►│  GitHub Runner  │──►│   EC2 Instance   │ │
│   │          │   │                │   │                  │ │
│   │ git push │   │ 1. Checkout    │   │ 1. git pull      │ │
│   │          │   │ 2. AWS Login   │   │ 2. ECR login     │ │
│   │ That's   │   │ 3. Build Image │   │ 3. Pull image    │ │
│   │ all you  │   │ 4. Push to ECR │   │ 4. Restart stack │ │
│   │ do!      │   │ 5. SSH to EC2  │   │ 5. Health check  │ │
│   └──────────┘   └────────────────┘   └──────────────────┘ │
│                                                             │
│              Image stored in ECR (container registry)        │
│              589516862821.dkr.ecr.us-east-1.amazonaws.com   │
└─────────────────────────────────────────────────────────────┘
```

---

## Part 8: CI/CD Interview Questions & Answers

### Q: "What is CI/CD and why did you use it?"

**A:** CI/CD automates the build and deploy process. CI (Continuous
Integration) ensures every code push is automatically built and
validated. CD (Continuous Deployment) takes it further by automatically
deploying to production. I used GitHub Actions because it integrates
directly with my GitHub repo — a push to main triggers the entire
pipeline: build the Docker image, push it to ECR, SSH into EC2,
and restart the containers with a health check.

### Q: "Walk me through your deployment pipeline."

**A:** When I push to main, GitHub Actions spins up a runner that
checks out my code, authenticates with AWS, builds the backend Docker
image, and pushes it to ECR with two tags — the commit SHA for
rollback capability and 'latest' for convenience. A second job then
SSHs into EC2, pulls the latest code and image, restarts the Docker
Compose stack, and runs a health check. If the health check fails,
the workflow fails and I get notified.

### Q: "How do you handle secrets in your pipeline?"

**A:** All sensitive values — AWS credentials, SSH keys, account IDs —
are stored as GitHub Encrypted Secrets. They're never hardcoded in
the workflow file, never exposed in logs (GitHub masks them with
asterisks), and are only accessible to workflows running in the repo.
The .pem key for EC2 SSH access is stored as a secret, not as a file
in the repository.

### Q: "What happens if a deploy fails?"

**A:** If the build fails, the deploy job is skipped entirely because
of the `needs` dependency — EC2 keeps running the old version safely.
If the deploy succeeds but the health check fails, the workflow is
marked as failed and I can see the last 50 lines of container logs
in the GitHub Actions output. For rollback, I can pull a previous
image from ECR using its commit hash tag.

### Q: "Why did you use two Docker image tags?"

**A:** The commit SHA tag gives every deploy a unique identifier for
rollback — if version `a1b2c3d4` breaks, I can instantly roll back
to `f5e6d7c8`. The 'latest' tag is a convenience pointer that always
references the newest build, which is what `docker compose pull` uses
by default.

### Q: "Why GitHub Actions instead of Jenkins or CodePipeline?"

**A:** For this project, GitHub Actions was the best fit because it's
built into GitHub (no extra infrastructure), has generous free tier
(2,000 minutes/month), has excellent AWS integration through official
actions, and the YAML configuration lives in the repo alongside the
code. Jenkins would require hosting my own CI server, and CodePipeline
adds AWS complexity that wasn't necessary for this scale.

### Q: "What would you change for a production enterprise setup?"

**A:** I'd add several things: a staging environment that deploys
first before production, automated tests in the CI step before
building, branch protection rules requiring PR reviews before merge
to main, container image vulnerability scanning, blue-green or
rolling deployments for zero-downtime updates, and monitoring/alerting
with CloudWatch or Datadog.

---

## Part 9: Key Concepts Summary

| Concept | What It Means | TravelQ Usage |
|---------|---------------|---------------|
| GitHub Actions | CI/CD platform built into GitHub | Runs our deploy.yml |
| Runner | VM that executes the workflow | ubuntu-latest (free) |
| Workflow | The YAML file defining automation | deploy.yml |
| Job | A group of steps on one machine | build-backend, deploy-ec2 |
| `needs` | Job dependency ordering | deploy waits for build |
| GitHub Secrets | Encrypted environment variables | AWS keys, SSH key |
| ECR | AWS private Docker image registry | Stores our backend image |
| `actions/checkout` | Clone repo onto runner | Official GitHub action |
| `appleboy/ssh-action` | SSH from runner to server | Community action |
| Health check | Verify app works after deploy | curl to /health endpoint |
| Image tagging | Label images for identification | commit SHA + latest |
| `--platform` | Force target CPU architecture | amd64 for EC2 |