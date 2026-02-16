# TravelQ AWS Deployment — Step by Step
# ==========================================

## What You're Building

```
Currently (your desktop):                    After deployment (AWS):

PowerShell 1 → Redis container              ┌─ EC2 Instance ────────────────┐
PowerShell 2 → celery -A celery_app worker  │                               │
PowerShell 3 → uvicorn api.main:app         │  docker compose up -d         │
Browser      → npm run dev (:5173)          │    ├── nginx     (:80)        │
                                            │    ├── backend   (:8000)      │
http://localhost:5173                       │    ├── celery    (worker)     │
                                            │    └── redis     (:6379)      │
                                            └───────────────────────────────┘

                                            https://travelq.yourdomain.com
```


## File Placement Guide

Copy these files into your project:

```
AGENTIC_TRAVELQ/
│
├── backend/
│   ├── Dockerfile              ← UPDATE with backend_Dockerfile
│   ├── .dockerignore           ← NEW (from backend_.dockerignore)
│   ├── agents/
│   ├── api/
│   ├── services/
│   ├── celery_app.py
│   ├── requirements.txt
│   └── ...
│
├── frontend/
│   ├── Dockerfile.prod         ← NEW (from frontend_Dockerfile.prod)
│   ├── .dockerignore           ← NEW (from frontend_.dockerignore)
│   ├── nginx/
│   │   └── default.conf        ← NEW (from nginx_default.conf)
│   ├── amplify.yml             ← NEW (optional, for Amplify hosting)
│   ├── src/
│   ├── package.json
│   └── ...
│
├── .github/
│   └── workflows/
│       └── deploy.yml          ← NEW (from deploy.yml)
│
├── docker-compose.prod.yml     ← NEW (production stack)
├── .env.prod.example           ← NEW (environment template)
├── .env.prod                   ← CREATE from .env.prod.example (DO NOT commit)
├── docker-compose.yml          ← KEEP (your existing dev compose)
└── .gitignore                  ← UPDATE (add .env.prod)
```


## Step 0: Prerequisites

On your local machine, make sure you have:
- [ ] AWS CLI v2 installed (`aws --version`)
- [ ] AWS CLI configured (`aws configure` — use your IAM credentials)
- [ ] Docker Desktop running
- [ ] Git (project pushed to GitHub)

```bash
# Verify AWS CLI
aws sts get-caller-identity
# Should show your account ID
```


## Step 1: Add Files to Your Project (Local)

### 1.1 Copy deployment files into your project
Place each file as shown in the File Placement Guide above.

### 1.2 Create the nginx directory inside frontend
```bash
mkdir -p frontend/nginx
# Copy nginx_default.conf → frontend/nginx/default.conf
```

### 1.3 Create .env.prod from the example
```bash
cp .env.prod.example .env.prod
# Edit .env.prod with your actual API keys
```

### 1.4 Update .gitignore
Add these lines to your root `.gitignore`:
```
.env.prod
.env.local
```

### 1.5 Verify your backend entry point
Your FastAPI app is in `backend/main.py`, so the Dockerfile CMD uses `main:app`.
This is because the Dockerfile `WORKDIR` is `/app` and all backend code is copied there,
so `main.py` is at `/app/main.py` inside the container → Gunicorn loads `main:app`.


## Step 2: Test Locally (Before Touching AWS)

This is important — test the production docker-compose on your machine first.

```powershell
# From the project root (AGENTIC_TRAVELQ/)
docker compose -f docker-compose.prod.yml up -d --build
```

Wait ~60 seconds, then check:
```powershell
# Check all 4 containers are running
docker compose -f docker-compose.prod.yml ps

# Check health
curl http://localhost/api/trips/health

# Check the frontend loads
# Open http://localhost in your browser
```

If something fails:
```powershell
# View logs
docker compose -f docker-compose.prod.yml logs backend
docker compose -f docker-compose.prod.yml logs celery_worker
docker compose -f docker-compose.prod.yml logs nginx

# Stop everything
docker compose -f docker-compose.prod.yml down
```

Fix any issues before moving to AWS.


## Step 3: Create AWS Resources

### 3.1 Create ECR Repository (stores your Docker images)

```bash
aws ecr create-repository \
    --repository-name travelq-backend \
    --region us-east-1

# Save the repositoryUri from the output — you'll need it
```

### 3.2 Create Security Group

```bash
# Create security group
aws ec2 create-security-group \
    --group-name travelq-sg \
    --description "TravelQ Application"

# Allow SSH (restrict to your IP!)
aws ec2 authorize-security-group-ingress \
    --group-name travelq-sg \
    --protocol tcp --port 22 --cidr $(curl -s ifconfig.me)/32

# Allow HTTP
aws ec2 authorize-security-group-ingress \
    --group-name travelq-sg \
    --protocol tcp --port 80 --cidr 0.0.0.0/0

# Allow HTTPS
aws ec2 authorize-security-group-ingress \
    --group-name travelq-sg \
    --protocol tcp --port 443 --cidr 0.0.0.0/0
```

### 3.3 Create Key Pair (for SSH access)

```bash
aws ec2 create-key-pair \
    --key-name travelq-key \
    --query 'KeyMaterial' \
    --output text > travelq-key.pem

# Set permissions (Mac/Linux)
chmod 400 travelq-key.pem

# On Windows PowerShell:
# icacls travelq-key.pem /inheritance:r /grant:r "$($env:USERNAME):(R)"
```

### 3.4 Launch EC2 Instance

```bash
# Amazon Linux 2023 AMI (us-east-1) — check AWS console for latest AMI ID
aws ec2 run-instances \
    --image-id ami-0c7217cdde317cfec \
    --instance-type t3.small \
    --key-name travelq-key \
    --security-groups travelq-sg \
    --block-device-mappings '[{"DeviceName":"/dev/xvda","Ebs":{"VolumeSize":20,"VolumeType":"gp3"}}]' \
    --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=TravelQ}]'

# Note the InstanceId from output
```

### 3.5 Allocate Elastic IP (so the IP doesn't change on reboot)

```bash
# Allocate
aws ec2 allocate-address --domain vpc
# Note the AllocationId

# Associate with your instance
aws ec2 associate-address \
    --instance-id i-YOUR_INSTANCE_ID \
    --allocation-id eipalloc-YOUR_ALLOCATION_ID

# Note the public IP — this is your permanent server address
```


## Step 4: Set Up EC2 Instance

### 4.1 SSH into your instance

```bash
ssh -i travelq-key.pem ec2-user@YOUR_ELASTIC_IP
```

### 4.2 Run the setup script

```bash
# Either copy and paste the ec2-setup.sh contents, or:
# From your local machine first:
#   scp -i travelq-key.pem ec2-setup.sh ec2-user@YOUR_IP:~/

chmod +x ec2-setup.sh
./ec2-setup.sh
```

### 4.3 Log out and back in (required for Docker group)

```bash
exit
ssh -i travelq-key.pem ec2-user@YOUR_ELASTIC_IP
```

### 4.4 Verify Docker works

```bash
docker --version
docker compose version
# Both should work without sudo
```


## Step 5: Deploy TravelQ on EC2

### 5.1 Clone your repository

```bash
cd ~
git clone https://github.com/YOUR_USERNAME/agentic-travelq.git
cd agentic-travelq
```

### 5.2 Create production environment file

```bash
cp .env.prod.example .env.prod
nano .env.prod
# Fill in your real API keys (OpenAI, Amadeus, Google Places)
# Save: Ctrl+O, Enter, Ctrl+X
```

### 5.3 Build and start everything

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

This will:
1. Build the FastAPI backend image
2. Build the React frontend + Nginx image
3. Pull Redis image
4. Start all 4 containers
5. Wait for health checks to pass

First build takes ~5-10 minutes. Subsequent builds are much faster (Docker caching).

### 5.4 Verify everything is running

```bash
# Check container status (all should be "healthy" or "running")
docker compose -f docker-compose.prod.yml ps

# Check backend health
curl http://localhost/api/trips/health

# Expected response:
# {"status":"healthy","service":"TravelQ API","version":"3.0.0","redis":true,"celery":true}

# Check frontend loads
curl -s http://localhost | head -5
# Should show HTML content
```

### 5.5 View logs if something is wrong

```bash
# All logs
docker compose -f docker-compose.prod.yml logs -f

# Specific service
docker compose -f docker-compose.prod.yml logs backend -f
docker compose -f docker-compose.prod.yml logs celery_worker -f
docker compose -f docker-compose.prod.yml logs nginx -f
docker compose -f docker-compose.prod.yml logs redis -f
```


## Step 6: Access Your App

At this point, TravelQ is live at:

```
http://YOUR_ELASTIC_IP
```

Open it in a browser — you should see the TravelQ dashboard!


## Step 7: Custom Domain + HTTPS (Optional but Recommended)

### 7.1 Buy/use a domain (Route 53 or any registrar)

If using Route 53:
```bash
aws route53 create-hosted-zone --name yourdomain.com --caller-reference $(date +%s)
```

### 7.2 Point domain to EC2

Create an A record:
- Name: `travelq.yourdomain.com`
- Type: A
- Value: YOUR_ELASTIC_IP

### 7.3 Set up HTTPS with Let's Encrypt

```bash
# On EC2
sudo yum install -y certbot
sudo certbot certonly --standalone -d travelq.yourdomain.com
```

Then update nginx config to use SSL (I can help with this when you're ready).


## Step 8: Set Up CI/CD (Optional but Recommended)

### 8.1 Add GitHub Secrets

Go to your GitHub repo → Settings → Secrets and variables → Actions.
Add these secrets:

| Secret Name | Value |
|---|---|
| AWS_ACCESS_KEY_ID | Your IAM access key |
| AWS_SECRET_ACCESS_KEY | Your IAM secret key |
| AWS_ACCOUNT_ID | Your 12-digit account ID |
| EC2_HOST | Your Elastic IP |
| EC2_SSH_KEY | Contents of travelq-key.pem |

### 8.2 Push and deploy

Once secrets are set, every push to `main` will auto-deploy:
```bash
git add .
git commit -m "Add AWS deployment configs"
git push origin main
# GitHub Actions will build → push to ECR → deploy to EC2
```


## Useful Commands (Bookmark These)

```bash
# SSH into EC2
ssh -i travelq-key.pem ec2-user@YOUR_ELASTIC_IP

# Start all services
docker compose -f docker-compose.prod.yml up -d

# Stop all services
docker compose -f docker-compose.prod.yml down

# Restart a specific service
docker compose -f docker-compose.prod.yml restart backend

# View logs (follow mode)
docker compose -f docker-compose.prod.yml logs -f

# Rebuild after code changes
git pull origin main
docker compose -f docker-compose.prod.yml up -d --build

# Check resource usage
docker stats

# Clean up old images
docker system prune -f
```


## Troubleshooting

| Problem | Solution |
|---------|----------|
| Container exits immediately | Check logs: `docker compose logs backend` |
| Health check failing | Verify your FastAPI app path in Dockerfile CMD |
| Redis connection refused | Check Redis container is healthy: `docker compose ps` |
| Celery not picking up tasks | Check broker URL matches in .env.prod |
| Frontend shows blank page | Check nginx logs and verify `npm run build` works locally |
| 502 Bad Gateway | Backend isn't ready yet — wait 30s and retry |
| Can't SSH into EC2 | Check security group has port 22 open for your IP |
| Out of disk space | Run `docker system prune -af` |