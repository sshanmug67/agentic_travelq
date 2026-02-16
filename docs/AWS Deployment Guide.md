# TravelQ — AWS Deployment Guide

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                     USERS / RECRUITERS                   │
│                    travelq.yourdomain.com                │
└──────────────┬──────────────────────┬───────────────────┘
               │                      │
         ┌─────▼─────┐         ┌─────▼──────┐
         │  Route 53  │         │    ACM     │
         │   (DNS)    │         │  (SSL/TLS) │
         └─────┬─────┘         └────────────┘
               │
    ┌──────────▼──────────┐
    │   AWS Amplify       │
    │   (React Frontend)  │
    │   - Global CDN      │
    │   - Auto CI/CD      │
    │   - HTTPS           │
    └──────────┬──────────┘
               │ /api/* proxy
    ┌──────────▼──────────────────────────────────────┐
    │              EC2 Instance (t3.small)             │
    │  ┌────────────────────────────────────────────┐  │
    │  │         Docker Compose Stack               │  │
    │  │                                            │  │
    │  │  ┌──────────┐  ┌────────────┐             │  │
    │  │  │  Nginx   │  │  FastAPI   │             │  │
    │  │  │ (Reverse │──│  Backend   │             │  │
    │  │  │  Proxy)  │  │  :8000     │             │  │
    │  │  │  :80/:443│  └─────┬──────┘             │  │
    │  │  └──────────┘        │                     │  │
    │  │                ┌─────▼──────┐              │  │
    │  │                │   Celery   │              │  │
    │  │                │   Worker   │              │  │
    │  │                └─────┬──────┘              │  │
    │  │                      │                     │  │
    │  │                ┌─────▼──────┐              │  │
    │  │                │   Redis    │              │  │
    │  │                │   :6379    │              │  │
    │  │                └────────────┘              │  │
    │  └────────────────────────────────────────────┘  │
    └──────────────────────┬───────────────────────────┘
                           │
                ┌──────────▼──────────┐
                │   Supabase Cloud    │
                │   (PostgreSQL DB)   │
                │   - Auth            │
                │   - Realtime        │
                │   - Storage         │
                └─────────────────────┘
```

## AWS Services Used

| Service | Purpose | Cost |
|---------|---------|------|
| **Amplify** | React frontend hosting, CDN, CI/CD | Free tier (1000 build min/mo) |
| **EC2** (t3.small) | Backend + Redis + Celery | Free tier 12 months (t3.micro) or ~$15/mo for t3.small |
| **ECR** | Docker image registry | Free tier (500MB) |
| **Route 53** | Custom domain DNS | ~$0.50/month per hosted zone |
| **ACM** | SSL/TLS certificates | Free |
| **Secrets Manager** | API keys storage | Free tier (30 days), then ~$0.40/secret/mo |
| **CloudWatch** | Monitoring & logs | Free tier (10 custom metrics) |
| **Supabase Cloud** | PostgreSQL database | Free tier (500MB, 2 projects) |

**Estimated monthly cost:** $0 - $20/month (depending on EC2 tier)

---

## Prerequisites

- AWS Account with Solutions Architect-level access
- AWS CLI v2 installed and configured
- Docker & Docker Compose installed locally
- Node.js 18+ and npm
- Git
- A registered domain name (optional but recommended)

---

## Phase 1: Prepare Docker Images

### 1.1 Backend Dockerfile

Your existing `backend/Dockerfile` should look like this (update if needed):

```dockerfile
# backend/Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for Docker layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run with Gunicorn + Uvicorn workers
CMD ["gunicorn", "api.main:app", \
     "-k", "uvicorn.workers.UvicornWorker", \
     "--workers", "2", \
     "--bind", "0.0.0.0:8000", \
     "--timeout", "120", \
     "--access-logfile", "-"]
```

### 1.2 Frontend Dockerfile (for building static assets)

Create `frontend/Dockerfile.prod`:

```dockerfile
# frontend/Dockerfile.prod
# Build stage
FROM node:18-alpine AS build

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .

# Build with production API URL
ARG VITE_API_URL
ENV VITE_API_URL=${VITE_API_URL}

RUN npm run build

# Production stage - Nginx to serve static files
FROM nginx:alpine

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx/default.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
```

### 1.3 Nginx Reverse Proxy Config

Create `nginx/default.conf`:

```nginx
upstream fastapi {
    server backend:8000;
}

server {
    listen 80;
    server_name _;

    # Frontend static files
    location / {
        root /usr/share/nginx/html;
        index index.html;
        try_files $uri $uri/ /index.html;
    }

    # API proxy
    location /api/ {
        proxy_pass http://fastapi;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
        proxy_connect_timeout 120s;
    }

    # Health check endpoint
    location /health {
        proxy_pass http://fastapi/health;
    }
}
```

### 1.4 Production Docker Compose

Create `docker-compose.prod.yml` at the project root:

```yaml
version: '3.8'

services:
  # Nginx Reverse Proxy + Frontend
  nginx:
    build:
      context: ./frontend
      dockerfile: Dockerfile.prod
      args:
        VITE_API_URL: ${VITE_API_URL:-/api}
    ports:
      - "80:80"
      - "443:443"
    depends_on:
      backend:
        condition: service_healthy
    restart: always
    networks:
      - travelq-network

  # FastAPI Backend
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    env_file:
      - .env.prod
    environment:
      - REDIS_URL=redis://redis:6379/0
      - CELERY_BROKER_URL=redis://redis:6379/0
      - CELERY_RESULT_BACKEND=redis://redis:6379/0
    expose:
      - "8000"
    depends_on:
      redis:
        condition: service_healthy
    restart: always
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    networks:
      - travelq-network

  # Celery Worker
  celery_worker:
    build:
      context: ./backend
      dockerfile: Dockerfile
    command: celery -A celery_app worker --loglevel=info --concurrency=2
    env_file:
      - .env.prod
    environment:
      - REDIS_URL=redis://redis:6379/0
      - CELERY_BROKER_URL=redis://redis:6379/0
      - CELERY_RESULT_BACKEND=redis://redis:6379/0
    depends_on:
      redis:
        condition: service_healthy
      backend:
        condition: service_healthy
    restart: always
    networks:
      - travelq-network

  # Redis
  redis:
    image: redis:7-alpine
    command: redis-server --maxmemory 256mb --maxmemory-policy allkeys-lru
    expose:
      - "6379"
    volumes:
      - redis-data:/data
    restart: always
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - travelq-network

networks:
  travelq-network:
    driver: bridge

volumes:
  redis-data:
```

### 1.5 Production Environment File

Create `.env.prod.example`:

```bash
# ============================================
# TravelQ Production Environment Variables
# ============================================

# --- Application ---
APP_ENV=production
DEBUG=false
LOG_LEVEL=INFO

# --- API Keys ---
OPENAI_API_KEY=sk-xxxx
AMADEUS_API_KEY=your_amadeus_key
AMADEUS_API_SECRET=your_amadeus_secret
GOOGLE_PLACES_API_KEY=your_google_places_key

# --- Redis ---
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

# --- Supabase (future) ---
# SUPABASE_URL=https://your-project.supabase.co
# SUPABASE_ANON_KEY=your_anon_key
# SUPABASE_SERVICE_KEY=your_service_key

# --- CORS ---
CORS_ORIGINS=https://travelq.yourdomain.com,https://www.travelq.yourdomain.com

# --- Frontend ---
VITE_API_URL=/api
```

---

## Phase 2: Set Up AWS Infrastructure

### 2.1 Create ECR Repository (for storing Docker images)

```bash
# Create ECR repository
aws ecr create-repository \
    --repository-name travelq-backend \
    --region us-east-1

# Login to ECR
aws ecr get-login-password --region us-east-1 | \
    docker login --username AWS --password-stdin \
    YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com
```

### 2.2 Build & Push Docker Image

```bash
# Build backend image
cd backend
docker build --platform=linux/amd64 -t travelq-backend .

# Tag for ECR
docker tag travelq-backend:latest \
    YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/travelq-backend:latest

# Push to ECR
docker push \
    YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/travelq-backend:latest
```

### 2.3 Launch EC2 Instance

```bash
# Create a security group
aws ec2 create-security-group \
    --group-name travelq-sg \
    --description "TravelQ Application Security Group"

# Add inbound rules
aws ec2 authorize-security-group-ingress \
    --group-name travelq-sg \
    --protocol tcp --port 22 --cidr YOUR_IP/32     # SSH (your IP only)

aws ec2 authorize-security-group-ingress \
    --group-name travelq-sg \
    --protocol tcp --port 80 --cidr 0.0.0.0/0      # HTTP

aws ec2 authorize-security-group-ingress \
    --group-name travelq-sg \
    --protocol tcp --port 443 --cidr 0.0.0.0/0     # HTTPS

# Launch EC2 instance (Amazon Linux 2023, t3.small recommended)
aws ec2 run-instances \
    --image-id ami-0c7217cdde317cfec \
    --instance-type t3.small \
    --key-name your-key-pair \
    --security-groups travelq-sg \
    --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=TravelQ-Backend}]' \
    --block-device-mappings '[{"DeviceName":"/dev/xvda","Ebs":{"VolumeSize":20,"VolumeType":"gp3"}}]'
```

### 2.4 Configure EC2 Instance

SSH into the instance and run:

```bash
#!/bin/bash
# ec2-setup.sh - Run on EC2 instance

# Update system
sudo yum update -y

# Install Docker
sudo yum install -y docker
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker ec2-user

# Install Docker Compose v2
sudo mkdir -p /usr/local/lib/docker/cli-plugins
sudo curl -SL https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64 \
    -o /usr/local/lib/docker/cli-plugins/docker-compose
sudo chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

# Install AWS CLI (if not present)
sudo yum install -y aws-cli

# Install Git
sudo yum install -y git

# Login to ECR
aws ecr get-login-password --region us-east-1 | \
    docker login --username AWS --password-stdin \
    YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com

# Clone repository
git clone https://github.com/YOUR_USERNAME/agentic-travelq.git
cd agentic-travelq

# Create .env.prod from example
cp .env.prod.example .env.prod
# Edit with your actual API keys
nano .env.prod

# Start the application
docker compose -f docker-compose.prod.yml up -d

echo "✅ TravelQ is running on port 80!"
```

### 2.5 Allocate Elastic IP (persistent public IP)

```bash
# Allocate Elastic IP
aws ec2 allocate-address --domain vpc

# Associate with your instance
aws ec2 associate-address \
    --instance-id i-YOUR_INSTANCE_ID \
    --allocation-id eipalloc-YOUR_ALLOCATION_ID
```

---

## Phase 3: Frontend Deployment with AWS Amplify

### 3.1 Set Up Amplify

1. Go to AWS Amplify Console → **New app** → **Host web app**
2. Connect your GitHub repository
3. Select the `frontend` directory as the app root
4. Configure build settings:

Create `frontend/amplify.yml`:

```yaml
version: 1
frontend:
  phases:
    preBuild:
      commands:
        - npm ci
    build:
      commands:
        - echo "VITE_API_URL=$VITE_API_URL" >> .env.production
        - npm run build
  artifacts:
    baseDirectory: dist
    files:
      - '**/*'
  cache:
    paths:
      - node_modules/**/*
```

### 3.2 Environment Variables in Amplify

In the Amplify Console, add:

| Variable | Value |
|----------|-------|
| `VITE_API_URL` | `https://api.travelq.yourdomain.com` |

### 3.3 Custom Domain (Amplify)

1. In Amplify → **Domain management** → **Add domain**
2. Enter `travelq.yourdomain.com`
3. Amplify will provision an SSL certificate via ACM automatically

---

## Phase 4: DNS & SSL Configuration

### 4.1 Route 53 Setup

```bash
# Create hosted zone (if you don't have one)
aws route53 create-hosted-zone \
    --name yourdomain.com \
    --caller-reference $(date +%s)

# Create A record for API pointing to EC2 Elastic IP
aws route53 change-resource-record-sets \
    --hosted-zone-id YOUR_ZONE_ID \
    --change-batch '{
      "Changes": [{
        "Action": "UPSERT",
        "ResourceRecordSet": {
          "Name": "api.travelq.yourdomain.com",
          "Type": "A",
          "TTL": 300,
          "ResourceRecords": [{"Value": "YOUR_ELASTIC_IP"}]
        }
      }]
    }'
```

### 4.2 SSL with Let's Encrypt (on EC2)

```bash
# Install Certbot on EC2
sudo yum install -y certbot

# Get SSL certificate
sudo certbot certonly --standalone \
    -d api.travelq.yourdomain.com \
    --agree-tos --email your@email.com

# Set up auto-renewal
echo "0 0 * * * root certbot renew --quiet" | sudo tee -a /etc/crontab
```

---

## Phase 5: Monitoring with CloudWatch

### 5.1 Install CloudWatch Agent on EC2

```bash
# Install agent
sudo yum install -y amazon-cloudwatch-agent

# Configure
sudo /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-config-wizard

# Start
sudo systemctl start amazon-cloudwatch-agent
sudo systemctl enable amazon-cloudwatch-agent
```

### 5.2 Create CloudWatch Dashboard

Create a dashboard that monitors:
- EC2 CPU/Memory utilization
- Docker container health
- API response times (from application logs)
- Redis memory usage

---

## Phase 6: CI/CD Pipeline (GitHub Actions)

Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy TravelQ to AWS

on:
  push:
    branches: [main]

env:
  AWS_REGION: us-east-1
  ECR_REPOSITORY: travelq-backend
  EC2_HOST: ${{ secrets.EC2_HOST }}

jobs:
  deploy-backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

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
          docker build -t $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG .
          docker build -t $ECR_REGISTRY/$ECR_REPOSITORY:latest .
          docker push $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG
          docker push $ECR_REGISTRY/$ECR_REPOSITORY:latest

      - name: Deploy to EC2
        uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.EC2_HOST }}
          username: ec2-user
          key: ${{ secrets.EC2_SSH_KEY }}
          script: |
            cd ~/agentic-travelq
            git pull origin main
            aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin ${{ secrets.ECR_REGISTRY }}
            docker compose -f docker-compose.prod.yml pull
            docker compose -f docker-compose.prod.yml up -d --build
            docker system prune -f

  deploy-frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      # Amplify auto-deploys from GitHub — this job is for manual triggers
      - name: Trigger Amplify build
        run: |
          aws amplify start-job \
            --app-id ${{ secrets.AMPLIFY_APP_ID }} \
            --branch-name main \
            --job-type RELEASE
```

---

## Phase 7: Supabase Integration (Future)

When ready to connect Supabase:

### 7.1 Create Supabase Project

1. Go to [supabase.com](https://supabase.com) → New Project
2. Choose a region close to your EC2 (e.g., `us-east-1`)
3. Note your `Project URL` and `anon key`

### 7.2 Backend Integration

Install the Supabase Python client:

```bash
pip install supabase
```

Add to your backend services:

```python
# backend/services/supabase_service.py
from supabase import create_client, Client
import os

class SupabaseService:
    def __init__(self):
        self.client: Client = create_client(
            os.environ["SUPABASE_URL"],
            os.environ["SUPABASE_SERVICE_KEY"]
        )

    async def save_trip(self, trip_data: dict):
        return self.client.table("trips").insert(trip_data).execute()

    async def get_user_trips(self, user_id: str):
        return self.client.table("trips") \
            .select("*") \
            .eq("user_id", user_id) \
            .execute()
```

### 7.3 Database Schema

```sql
-- Supabase SQL Editor
CREATE TABLE trips (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID REFERENCES auth.users(id),
    origin TEXT,
    destination TEXT NOT NULL,
    start_date DATE,
    end_date DATE,
    travelers INT DEFAULT 1,
    budget DECIMAL,
    preferences JSONB DEFAULT '{}',
    itinerary JSONB DEFAULT '{}',
    status TEXT DEFAULT 'draft',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Enable Row Level Security
ALTER TABLE trips ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own trips"
    ON trips FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can create trips"
    ON trips FOR INSERT
    WITH CHECK (auth.uid() = user_id);
```

---

## Well-Architected Framework Analysis

### 1. Operational Excellence
- **CI/CD**: GitHub Actions automates build and deploy
- **Monitoring**: CloudWatch dashboards and alerts
- **Logging**: Centralized Docker logs via CloudWatch agent
- **IaC**: Docker Compose defines infrastructure as code

### 2. Security
- **Secrets Management**: API keys in AWS Secrets Manager (not in code)
- **Network**: Security groups limit access (SSH from your IP only)
- **HTTPS**: ACM certificates + Let's Encrypt
- **CORS**: Restricted to your domain
- **Supabase RLS**: Row Level Security on all tables

### 3. Reliability
- **Health Checks**: Docker healthchecks on all services
- **Auto-restart**: Docker restart policies
- **Elastic IP**: Persistent public IP survives reboots
- **Redis Persistence**: Volume-mounted data

### 4. Performance Efficiency
- **CDN**: Amplify serves frontend via CloudFront
- **Async**: FastAPI + Celery for non-blocking AI agent calls
- **Redis**: In-memory caching for trip status polling
- **Docker**: Lightweight containers, efficient resource use

### 5. Cost Optimization
- **Right-sized**: t3.small for backend (upgradeable)
- **Free Tiers**: Amplify, ACM, Supabase, CloudWatch basics
- **No over-provisioning**: Single EC2 runs full stack
- **Monitoring**: CloudWatch alerts on spend

---

## Resume Bullet Points

Use these on your resume:

> **TravelQ — AI-Powered Multi-Agent Travel Planning Platform**
> - Architected and deployed a full-stack AI travel application using React, FastAPI, and Microsoft Autogen multi-agent framework on AWS (Amplify, EC2, ECR, Route 53, ACM, CloudWatch)
> - Designed microservices architecture with Docker containerization, Nginx reverse proxy, Redis task queuing, and Celery workers for asynchronous AI agent orchestration
> - Implemented CI/CD pipeline via GitHub Actions with automated ECR image builds and zero-downtime EC2 deployments
> - Integrated 5+ external APIs (Amadeus, Google Places, Open-Meteo, Xotelo) through specialized AI agents for flights, hotels, restaurants, weather, and events
> - Applied AWS Well-Architected Framework principles: security groups, Secrets Manager, health checks, CloudWatch monitoring, and cost optimization
> - Tech: React, TypeScript, Tailwind CSS, FastAPI, Python, Autogen, Redis, Celery, Docker, Nginx, AWS (EC2, ECR, Amplify, Route 53, ACM, CloudWatch), Supabase

---

## Quick Deploy Checklist

- [ ] Update `backend/Dockerfile` (if needed)
- [ ] Create `frontend/Dockerfile.prod`
- [ ] Create `nginx/default.conf`
- [ ] Create `docker-compose.prod.yml`
- [ ] Create `.env.prod` with real API keys
- [ ] Create ECR repository
- [ ] Build & push Docker image to ECR
- [ ] Launch EC2 instance (t3.small)
- [ ] Install Docker & Docker Compose on EC2
- [ ] Clone repo and start services
- [ ] Allocate Elastic IP
- [ ] Set up Amplify for frontend
- [ ] Configure Route 53 DNS records
- [ ] Set up SSL certificates
- [ ] Configure CloudWatch monitoring
- [ ] Set up GitHub Actions CI/CD
- [ ] Test end-to-end
- [ ] Add "View Source on GitHub" button to app
- [ ] Update resume with project details