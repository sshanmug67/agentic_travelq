# Migrate React Frontend to AWS Amplify — Step-by-Step Guide

**Domain:** `agentic-travelq.com` (Route 53)  
**Strategy:** Dev first → then Prod

---

## Architecture Overview

### Before (Current)
```
User → EC2 (Nginx container) → serves React static files + proxies to backend API
```

### After (Target)
```
User → Amplify CDN (React app) → calls → EC2 Backend API
         ↑                                    ↑
   agentic-travelq.com              api.agentic-travelq.com
   dev.agentic-travelq.com          api-dev.agentic-travelq.com
```

---

## Phase 0: Prepare Your React App

### 0.1 — Update API Base URL to Use Environment Variables

In your React app, make sure all API calls use an environment variable instead of a hardcoded URL.

**Create/update `.env.development` (for local dev):**
```env
REACT_APP_API_BASE_URL=http://localhost:8000
```

> If using **Vite** instead of CRA, prefix with `VITE_` instead of `REACT_APP_`:
> ```env
> VITE_API_BASE_URL=http://localhost:8000
> ```

**Update your API service/config file** (example):
```javascript
// src/config.js or src/api/client.js

// For Create React App:
const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000';

// For Vite:
// const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export default API_BASE_URL;
```

**Update all fetch/axios calls:**
```javascript
import API_BASE_URL from './config';

// Before:
// fetch('http://3.226.2.116:8000/api/search')

// After:
fetch(`${API_BASE_URL}/api/search`)
```

### 0.2 — Verify Build Works Locally

```bash
cd your-frontend-repo

# For CRA:
npm run build
# Output → build/

# For Vite:
npm run build
# Output → dist/
```

Make sure the build completes without errors.

### 0.3 — Commit and Push Changes

```bash
git add .
git commit -m "Use environment variable for API base URL"
git push origin dev
```

---

## Phase 1: Deploy Dev Branch to Amplify

### Step 1 — Create Amplify App

1. Go to **AWS Console** → **AWS Amplify**
2. Click **"Create new app"**
3. Select **GitHub** as your source provider
4. Authorize AWS to access your GitHub account (if not already done)
5. Select your **frontend repository**
6. Select the **`dev`** branch
7. Click **Next**

### Step 2 — Configure Build Settings

Amplify will auto-detect React. Verify or update the build settings:

**For Create React App:**
```yaml
version: 1
frontend:
  phases:
    preBuild:
      commands:
        - npm ci
    build:
      commands:
        - npm run build
  artifacts:
    baseDirectory: build
    files:
      - '**/*'
  cache:
    paths:
      - node_modules/**/*
```

**For Vite:**
```yaml
version: 1
frontend:
  phases:
    preBuild:
      commands:
        - npm ci
    build:
      commands:
        - npm run build
  artifacts:
    baseDirectory: dist
    files:
      - '**/*'
  cache:
    paths:
      - node_modules/**/*
```

### Step 3 — Set Environment Variables in Amplify

1. In the Amplify app settings, go to **"Environment variables"**
2. Add:

| Variable | Value |
|----------|-------|
| `REACT_APP_API_BASE_URL` | `https://api-dev.agentic-travelq.com` |

> For Vite, use `VITE_API_BASE_URL` instead.

3. Click **Save**

### Step 4 — Deploy

1. Click **"Save and deploy"**
2. Amplify will build and deploy your app
3. You'll get a temporary URL like: `https://dev.d1abc2def3.amplifyapp.com`
4. **Test this URL** to make sure the app loads

---

## Phase 1B: Configure DNS for Dev

### Step 5 — Add Custom Domain in Amplify

1. In your Amplify app, go to **"Hosting" → "Custom domains"**
2. Click **"Add domain"**
3. Select `agentic-travelq.com` from the dropdown (it will show since it's in Route 53)
4. Configure subdomains:
   - **`dev`** → points to `dev` branch
5. Click **"Configure domain"**
6. Amplify will automatically create the Route 53 records and provision an SSL certificate
7. Wait for SSL verification (can take 10-30 minutes)

### Step 6 — Point API Subdomain to Dev EC2

Go to **Route 53** → **Hosted zones** → `agentic-travelq.com`:

1. Click **"Create record"**
2. Configure:
   - **Record name:** `api-dev`
   - **Record type:** A
   - **Value:** `<Your Dev EC2 Elastic IP>` (e.g., `3.226.2.116`)
   - **TTL:** 300
3. Click **"Create records"**

---

## Phase 1C: Configure EC2 Backend for CORS & HTTPS

### Step 7 — Update CORS on Dev EC2 Backend

SSH into your Dev EC2 and update your backend to allow requests from the Amplify domain.

**For FastAPI:**
```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://dev.agentic-travelq.com",
        "http://localhost:3000",  # local dev
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**For Flask:**
```python
from flask_cors import CORS

CORS(app, origins=[
    "https://dev.agentic-travelq.com",
    "http://localhost:3000",
])
```

### Step 8 — Add SSL to Dev EC2 API (Required!)

Since Amplify serves your frontend over HTTPS, your API must also be HTTPS (browsers block mixed content).

**Option A: Use Nginx + Let's Encrypt (Recommended)**

SSH into Dev EC2:
```bash
# Install Certbot
sudo apt update
sudo apt install certbot python3-certbot-nginx -y

# Get SSL certificate
sudo certbot --nginx -d api-dev.agentic-travelq.com

# Auto-renewal
sudo certbot renew --dry-run
```

Update your Nginx config to proxy to your backend:
```nginx
server {
    listen 443 ssl;
    server_name api-dev.agentic-travelq.com;

    ssl_certificate /etc/letsencrypt/live/api-dev.agentic-travelq.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api-dev.agentic-travelq.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

server {
    listen 80;
    server_name api-dev.agentic-travelq.com;
    return 301 https://$host$request_uri;
}
```

Reload Nginx:
```bash
sudo nginx -t
sudo systemctl reload nginx
```

**Option B: Use AWS ALB with ACM certificate** (more AWS-native but more complex)

### Step 9 — Test Dev Deployment

1. Open `https://dev.agentic-travelq.com` — frontend should load from Amplify CDN
2. Test API calls — they should go to `https://api-dev.agentic-travelq.com` → Dev EC2
3. Check browser console for any CORS or mixed-content errors
4. Test all major features of your app

---

## Phase 2: Deploy Prod Branch to Amplify

Once dev is working, repeat for production.

### Step 10 — Add Prod Branch in Amplify

**Option A: Same Amplify app, add branch**
1. In your Amplify app, go to **"Hosting" → "Branches"**
2. Click **"Connect branch"**
3. Select `main` (or `prod`) branch
4. Set environment variable:

| Variable | Value |
|----------|-------|
| `REACT_APP_API_BASE_URL` | `https://api.agentic-travelq.com` |

5. Deploy

**Option B: Create a separate Amplify app for prod** (better isolation)
- Repeat Steps 1-4 but select the `main`/`prod` branch

### Step 11 — Configure Prod Custom Domain

In Amplify custom domains, add:
- **`agentic-travelq.com`** → `main` branch (root domain)
- **`www`** → redirect to `agentic-travelq.com`

### Step 12 — Point API to Prod EC2

In Route 53, create:
- **Record name:** `api`
- **Record type:** A
- **Value:** `<Your Prod EC2 Elastic IP>`
- **TTL:** 300

### Step 13 — Configure Prod EC2

Repeat Steps 7-8 on Prod EC2:
- Update CORS to allow `https://agentic-travelq.com`
- Install SSL for `api.agentic-travelq.com`

---

## Phase 3: Clean Up

### Step 14 — Remove Frontend from Docker

Once both environments are confirmed working:

1. Remove the Nginx frontend container from your `docker-compose.prod.yml`
2. Update EC2 security groups — you can close port 80/443 for direct frontend access if the EC2 only serves the API now (keep 443 open for `api.` subdomain)
3. Update any CI/CD pipelines to stop building/deploying the frontend container

### Step 15 — Verify CI/CD Auto-Deploy

Push a small change to `dev` branch and confirm:
- Amplify auto-detects the push
- Builds and deploys automatically
- Changes appear on `dev.agentic-travelq.com`

---

## Final DNS Summary (Route 53)

| Record | Type | Points To | Purpose |
|--------|------|-----------|---------|
| `agentic-travelq.com` | ALIAS | Amplify (prod) | Production frontend |
| `www.agentic-travelq.com` | CNAME | `agentic-travelq.com` | Redirect |
| `dev.agentic-travelq.com` | CNAME | Amplify (dev) | Dev frontend |
| `api.agentic-travelq.com` | A | Prod EC2 Elastic IP | Production API |
| `api-dev.agentic-travelq.com` | A | Dev EC2 Elastic IP | Dev API |

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| CORS errors in browser | Check `allow_origins` includes your Amplify domain with `https://` |
| Mixed content warnings | Your API must serve over HTTPS (see Step 8) |
| 404 on page refresh | Add Amplify redirect rule: `</^[^.]+$\|\.(?!(css\|gif\|ico\|jpg\|js\|png\|txt\|svg\|woff\|woff2\|ttf\|map\|json)$)([^.]+$)/>` → `/index.html` (200 rewrite) |
| Build fails in Amplify | Check Node version — add `nvm use 18` in preBuild commands |
| Environment vars not working | Amplify rebuilds are needed after changing env vars. Trigger a new build. |
| SSL certificate pending | Wait up to 30 min. Check Route 53 has the CNAME validation records. |