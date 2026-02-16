# amplify.yml — Deep Dive Explanation

---

## Part 1: Where Does Amplify Fit In Our Architecture?

TravelQ has two separate applications — a React frontend and a
FastAPI backend. They're deployed to **different AWS services**:

```
┌──────────────────────────────────────────────────────────┐
│                    TravelQ Architecture                    │
│                                                          │
│   FRONTEND (React + Vite)         BACKEND (FastAPI)      │
│   ─────────────────────           ─────────────────      │
│   Deployed to: AWS Amplify        Deployed to: EC2       │
│   Served via: CloudFront CDN      Served via: Nginx      │
│   CI/CD: Amplify auto-build       CI/CD: GitHub Actions  │
│   Config: amplify.yml             Config: deploy-aws-ec2 │
│                                                          │
│   User's browser loads            Frontend calls          │
│   HTML/CSS/JS from Amplify  ───►  backend API on EC2     │
└──────────────────────────────────────────────────────────┘
```

### Why Not Put Everything on EC2?

You could — and our `docker-compose.prod.yml` actually includes a
frontend container served through Nginx. But Amplify is the
production-standard approach because:

```
Frontend on EC2 (via Nginx):         Frontend on Amplify:
──────────────────────────           ─────────────────────
Served from one server               Served from CloudFront CDN
  in us-east-1                         (400+ edge locations worldwide)

User in Tokyo: ~200ms                User in Tokyo: ~20ms
User in London: ~100ms               User in London: ~10ms
User in Virginia: ~10ms              User in Virginia: ~10ms

Single point of failure              Globally distributed, redundant
EC2 goes down = frontend gone        EC2 goes down = frontend still works
                                       (shows "API unavailable" gracefully)

You manage SSL, caching, gzip        Amplify handles all of that
Manual deploys or CI/CD              Auto-deploys on git push
```

### The Two Separate CI/CD Pipelines

This is important — TravelQ has **two independent deployment paths**:

```
Pipeline 1: Backend (GitHub Actions)
────────────────────────────────────
git push main
  → GitHub Actions runs deploy-aws-ec2.yml
  → Builds Docker image
  → Pushes to ECR
  → SSHs into EC2
  → Restarts containers

Pipeline 2: Frontend (Amplify)
──────────────────────────────
git push main
  → Amplify detects changes in frontend/ directory
  → Reads amplify.yml for build instructions
  → Runs npm ci + npm run build
  → Deploys dist/ to CloudFront CDN

Both trigger on the same git push, but run independently.
Backend failure does NOT block frontend deploy (and vice versa).
```

---

## Part 2: What Is AWS Amplify?

Amplify is AWS's **static site hosting service**. Think of it as
Vercel or Netlify, but built into AWS.

For a React/Vite app, the production build output is just static
files — HTML, CSS, JavaScript. There's no server needed to "run"
React. A browser downloads these files and React runs entirely
in the user's browser.

```
npm run build
  └── creates dist/ folder
       ├── index.html          (2 KB)
       ├── assets/
       │   ├── index-a1b2c3.js (250 KB)  ← your React app
       │   ├── index-d4e5f6.css (15 KB)  ← your styles
       │   └── vendor-g7h8i9.js (180 KB) ← react, libraries
       └── favicon.ico

Total: ~450 KB of static files
```

Amplify takes these static files and:
1. Uploads them to S3 (storage)
2. Puts CloudFront CDN in front (global distribution)
3. Handles SSL certificates automatically
4. Provides custom domain support
5. Auto-deploys when you push to GitHub

---

## Part 3: What Is amplify.yml?

This file tells Amplify **how to build your React app**. It's the
equivalent of `deploy-aws-ec2.yml` for GitHub Actions, but much
simpler because Amplify only needs to do one thing: build static files.

### File Location

```
AGENTIC_TRAVELQ/
├── frontend/
│   ├── amplify.yml          ← THIS FILE
│   ├── src/
│   ├── package.json
│   └── ...
```

---

## Part 4: The Complete amplify.yml File

```yaml
# frontend/amplify.yml
# AWS Amplify build configuration for TravelQ React frontend

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
      - .npm/**/*
```

---

## Part 5: Line-by-Line Breakdown

---

### `version: 1`

Amplify build spec version. Currently only version 1 exists.
Always include it.

---

### `frontend:` Block

Tells Amplify this is a frontend application build. Amplify also
supports `backend:` blocks for Amplify Backend features, but we
don't use that — our backend is on EC2.

---

### Phase 1: `preBuild`

```yaml
preBuild:
  commands:
    - npm ci
```

Runs **before** the build starts. `npm ci` installs all dependencies
from `package-lock.json`.

**Why `npm ci` instead of `npm install`?**

```
npm install                          npm ci
───────────────────────              ───────────────────────
Reads package.json                   Reads package-lock.json
May update lock file                 Never modifies lock file
Resolves "latest" versions           Uses exact pinned versions
Can install different versions       Guarantees identical install
  on different machines                every single time

Good for: development                Good for: CI/CD builds
```

`npm ci` ensures your Amplify build uses the **exact same versions**
you tested locally. This is critical — a "latest" dependency update
in production could break your app.

`npm ci` also deletes `node_modules/` first and does a clean install,
which is more reliable for CI environments.

---

### Phase 2: `build`

```yaml
build:
  commands:
    - echo "VITE_API_URL=$VITE_API_URL" >> .env.production
    - npm run build
```

**Line 1 — Inject the backend URL:**

```bash
echo "VITE_API_URL=$VITE_API_URL" >> .env.production
```

This is the most important line. It creates a `.env.production` file
with your backend API URL. Let's break it down:

| Part | Meaning |
|------|---------|
| `echo "..."` | Print text |
| `VITE_API_URL=` | The variable name your React app reads |
| `$VITE_API_URL` | Reads the value from Amplify Environment Variables |
| `>>` | Append to file (create if doesn't exist) |
| `.env.production` | Vite's production environment file |

The `$VITE_API_URL` value comes from the **Amplify Console**, where
you set environment variables:

```
Amplify Console → App Settings → Environment Variables

Variable Name:    VITE_API_URL
Variable Value:   https://api.travelq.yourdomain.com
```

After this line runs, the file looks like:

```
# .env.production
VITE_API_URL=https://api.travelq.yourdomain.com
```

**Why this matters:** Your React code calls the backend like this:

```typescript
// In your React app
const API_URL = import.meta.env.VITE_API_URL;
const response = await fetch(`${API_URL}/api/trips/search`);
```

During development: `VITE_API_URL=http://localhost:8000`
In production:      `VITE_API_URL=https://api.travelq.yourdomain.com`

Without this line, your production frontend wouldn't know where
the backend lives.

**Why the VITE_ prefix?** Vite only exposes environment variables
that start with `VITE_` to the browser. This is a security measure —
it prevents accidentally leaking server-side secrets to the client.

```
VITE_API_URL=https://...     ← exposed to browser (intentional)
DATABASE_URL=postgres://...  ← NOT exposed (stays server-side)
SECRET_KEY=abc123            ← NOT exposed (stays server-side)
```

**Line 2 — Build the app:**

```bash
npm run build
```

Runs Vite's production build. This:
1. Compiles TypeScript → JavaScript
2. Bundles all React components into optimized chunks
3. Minifies CSS and JS (removes whitespace, shortens names)
4. Generates hashed filenames for cache-busting
5. Outputs everything to the `dist/` directory

```
Before build:                        After build:

frontend/                            frontend/dist/
├── src/                             ├── index.html
│   ├── App.tsx (50+ files)          ├── assets/
│   ├── components/                  │   ├── index-a1b2c3.js
│   ├── pages/                       │   ├── index-d4e5f6.css
│   └── ...                          │   └── vendor-g7h8i9.js
├── node_modules/ (500MB)            └── favicon.ico
└── package.json
                                     Total: ~450 KB
50+ source files, 500MB deps         3-4 optimized files, <1MB
```

---

### `artifacts`

```yaml
artifacts:
  baseDirectory: dist
  files:
    - '**/*'
```

Tells Amplify where to find the build output.

| Setting | Meaning |
|---------|---------|
| `baseDirectory: dist` | The built files are in the `dist/` folder |
| `files: '**/*'` | Upload everything inside `dist/` |

Amplify takes these files and deploys them to CloudFront CDN.
This is the final step — after this, your frontend is live.

---

### `cache`

```yaml
cache:
  paths:
    - node_modules/**/*
    - .npm/**/*
```

Tells Amplify to cache these directories between builds.

Without caching:
```
Build 1: npm ci installs 500MB of dependencies     → 45 seconds
Build 2: npm ci installs 500MB of dependencies     → 45 seconds
Build 3: npm ci installs 500MB of dependencies     → 45 seconds
```

With caching:
```
Build 1: npm ci installs from scratch              → 45 seconds
Build 2: npm ci checks cache, installs only new    → 10 seconds
Build 3: npm ci checks cache, installs only new    → 10 seconds
```

`node_modules/` is the installed packages, `.npm/` is npm's
internal download cache. Both are large and rarely change.

---

## Part 6: How Amplify Connects to GitHub

Unlike GitHub Actions (which uses a workflow file you write),
Amplify connects to GitHub through a **direct integration**
set up in the AWS Console:

```
Setup (done once in AWS Console):

1. Amplify Console → New App → Host Web App
2. Select GitHub → Authorize AWS
3. Pick repository: sshanmug67/agentic_travelq
4. Pick branch: main
5. Set app root: frontend/
6. Set environment variables (VITE_API_URL)
7. Deploy

After setup, Amplify watches your repo automatically.
```

Once connected, every push to `main` that changes files in
`frontend/` triggers an Amplify build automatically. You don't
need anything in `deploy-aws-ec2.yml` for the frontend —
that's why Job 3 in our CI/CD file says:

```yaml
# Job 3: Frontend deploys automatically via
# Amplify's GitHub integration (no action needed)
```

---

## Part 7: Amplify Build vs GitHub Actions Build

```
                    GitHub Actions              Amplify
                    (deploy-aws-ec2.yml)        (amplify.yml)
────────────────    ────────────────────        ────────────────
Builds what?        Backend Docker image        Frontend static files
Triggered by        .github/workflows/          Amplify GitHub integration
Runs on             GitHub Runner (Ubuntu VM)   Amplify Build Server
Pushes to           ECR (image registry)        CloudFront CDN
Deploys to          EC2 via SSH                 CloudFront (automatic)
Config file         deploy-aws-ec2.yml          amplify.yml
Config location     .github/workflows/          frontend/
Build time          3-5 minutes                 1-2 minutes
```

---

## Part 8: How Frontend Talks to Backend in Production

```
User's Browser
     │
     │ 1. Loads HTML/CSS/JS from Amplify CDN
     │    (travelq.yourdomain.com)
     │
     │ 2. React app starts running in browser
     │
     │ 3. User searches for a trip
     │
     │ 4. React calls: fetch("https://api.travelq.yourdomain.com/api/trips/search")
     │                        ↑
     │                  This URL came from VITE_API_URL
     │                  (injected during Amplify build)
     │
     ▼
EC2 (api.travelq.yourdomain.com)
     │
     │ 5. Nginx receives request → forwards to FastAPI
     │ 6. FastAPI → Celery → AI Agents → External APIs
     │ 7. Response sent back to browser
     │
     ▼
Browser renders the itinerary
```

**CORS Configuration:** Since frontend (travelq.yourdomain.com) and
backend (api.travelq.yourdomain.com) are on different subdomains,
FastAPI needs CORS configured to allow requests:

```python
# In your FastAPI backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://travelq.yourdomain.com"],
    allow_methods=["*"],
    allow_headers=["*"],
)
```

This is already handled in your `.env.prod`:
```
CORS_ORIGINS=https://travelq.yourdomain.com,http://localhost:5173
```

---

## Part 9: Amplify Environment Variables Setup

Set these in the Amplify Console (NOT in amplify.yml):

```
Amplify Console → App Settings → Environment Variables

┌──────────────────┬─────────────────────────────────────────┐
│ Variable Name    │ Value                                   │
├──────────────────┼─────────────────────────────────────────┤
│ VITE_API_URL     │ https://api.travelq.yourdomain.com      │
└──────────────────┴─────────────────────────────────────────┘
```

**Never put secrets in amplify.yml.** The file is committed to git
and visible to anyone with repo access. Environment variables in
the Amplify Console are encrypted and never exposed in build logs.

For TravelQ's frontend, `VITE_API_URL` is the only variable needed.
The frontend has no API keys — all sensitive calls (OpenAI, Amadeus,
Google Places) go through the backend.

---

## Part 10: Amplify vs Alternatives

```
Service         Strengths                          Best For
────────────────────────────────────────────────────────────
AWS Amplify     Native AWS, CDN, auto-SSL          AWS-native stacks
Vercel          Fastest DX, great Next.js support  Next.js projects
Netlify         Easy setup, form handling           Static sites, JAMstack
CloudFront+S3   Full control, cheapest at scale     Cost-sensitive, custom
GitHub Pages    Free, simple                        Docs, simple sites

For TravelQ: Amplify makes sense because backend is already on AWS.
Everything stays in one AWS account — billing, monitoring, DNS.
```

---

## Part 11: What the Build Process Looks Like

When Amplify runs, you can watch the build logs in the console:

```
Build Log:

[Amplify] Cloning repository...
[Amplify] Checking out branch: main
[Amplify] Navigating to app root: frontend/

[preBuild] Running: npm ci
[preBuild] added 287 packages in 12s

[Build] Running: echo "VITE_API_URL=https://api.travelq.yourdomain.com" >> .env.production
[Build] Running: npm run build
[Build] vite v6.x building for production...
[Build] ✓ 143 modules transformed
[Build] dist/index.html                  0.46 kB │ gzip: 0.30 kB
[Build] dist/assets/index-a1b2c3.css    15.23 kB │ gzip: 4.12 kB
[Build] dist/assets/index-d4e5f6.js    248.91 kB │ gzip: 79.34 kB
[Build] dist/assets/vendor-g7h8i9.js   182.44 kB │ gzip: 58.21 kB
[Build] ✓ built in 8.42s

[Deploy] Uploading artifacts...
[Deploy] Deploying to CloudFront...
[Deploy] ✅ Deployment complete!
[Deploy] https://main.d1234abcde.amplifyapp.com
```

Total build time: ~1-2 minutes.

---

## Part 12: Interview Questions & Answers

### Q: "Why did you use Amplify instead of serving the frontend from EC2?"

**A:** Performance and reliability. Amplify deploys to CloudFront CDN,
which has 400+ edge locations globally. A user in Tokyo gets the
frontend served from a nearby edge node in milliseconds, versus
making a round-trip to our EC2 in us-east-1. It also provides
separation of concerns — if the backend goes down, the frontend
still loads and can show a graceful error. Plus, Amplify handles
SSL, caching, and auto-deployment out of the box.

### Q: "How does your frontend know where the backend is?"

**A:** During the Amplify build, we inject the backend URL as an
environment variable. The `amplify.yml` build step writes
`VITE_API_URL` into `.env.production`, which Vite bakes into the
JavaScript bundle at build time. In the React code, we access it
via `import.meta.env.VITE_API_URL`. This means the backend URL is
determined at build time, not runtime.

### Q: "Why npm ci instead of npm install?"

**A:** Reproducibility. `npm ci` reads from `package-lock.json` and
installs exact versions, ensuring the production build uses
identical dependencies to what I tested locally. `npm install`
can resolve to different versions and even modify the lock file,
which introduces risk in CI/CD environments.

### Q: "How do you handle CORS with separate frontend and backend domains?"

**A:** The frontend on Amplify (travelq.yourdomain.com) and backend
on EC2 (api.travelq.yourdomain.com) are different origins, so
the browser enforces CORS. I configured FastAPI's CORSMiddleware
to explicitly allow the frontend origin. The allowed origins are
set through environment variables so they can differ between
development (localhost:5173) and production.

### Q: "What happens if the Amplify build fails?"

**A:** Amplify keeps the previous successful deployment live.
Users continue seeing the last working version while I debug
the build. Amplify provides full build logs in the console,
and I can also set up SNS notifications for build failures.
This is the same principle as our backend deploy — never take
down a working version due to a failed update.

### Q: "How do you manage environment-specific configurations?"

**A:** Environment variables in the Amplify Console for production,
and local `.env` files for development. The `VITE_` prefix ensures
only intended variables are exposed to the browser — Vite strips
anything without this prefix as a security measure. Sensitive keys
like OpenAI and Amadeus never touch the frontend; all API calls
go through the backend.

### Q: "Could you use Amplify for the backend too?"

**A:** Amplify does support backend functions (Lambda-based), but
TravelQ's backend needs long-running processes for AI agent
orchestration (up to 2 minutes per trip search), persistent
WebSocket connections for status polling, and Redis + Celery
for task queuing. These don't fit Lambda's 15-minute timeout
model or its stateless architecture. EC2 (Phase 1) or Fargate
(Phase 2) are better fits for this workload.

---

## Part 13: Key Concepts Summary

| Concept | What It Means | TravelQ Usage |
|---------|---------------|---------------|
| AWS Amplify | Static site hosting with CDN | Hosts React frontend |
| CloudFront | AWS CDN (400+ edge locations) | Serves frontend globally |
| amplify.yml | Build instructions for Amplify | Defines how to build React app |
| npm ci | Clean install from lock file | Reproducible dependency install |
| VITE_API_URL | Environment variable | Tells frontend where backend is |
| .env.production | Vite production env file | Created during build |
| dist/ | Vite build output | Static HTML/CSS/JS files |
| Artifacts | Build output files | What Amplify deploys to CDN |
| Cache | Preserved between builds | node_modules for faster builds |
| CORS | Cross-Origin Resource Sharing | Allows frontend→backend calls |



Step 1: Webhook received
─────────────────────────
GitHub sends POST to Amplify: "main branch updated"

Step 2: Amplify clones the repo
────────────────────────────────
git clone https://github.com/sshanmug67/agentic_travelq.git
git checkout main
cd frontend/          ← navigates to the app root you configured

Step 3: Amplify reads amplify.yml
──────────────────────────────────
Finds the build instructions

Step 4: preBuild phase
───────────────────────
npm ci                ← installs dependencies from package-lock.json

Step 5: build phase
────────────────────
echo "VITE_API_URL=..." >> .env.production
npm run build         ← tsc + vite build → creates dist/

Step 6: Amplify collects artifacts
───────────────────────────────────
Reads from amplify.yml:
  baseDirectory: dist
  files: '**/*'
Grabs everything from dist/

Step 7: Deploy to S3 + CloudFront
──────────────────────────────────
Uploads new files to S3
Invalidates CloudFront cache    ← tells CDN "forget the old files"
CDN edges pull fresh files from S3

Step 8: Live
─────────────
Users now get the new version



This means the same code works in both environments:
```
Development:
  .env.local → VITE_API_URL=http://localhost:8000
  baseURL becomes: http://localhost:8000/api
  Calls go to: http://localhost:8000/api/trips/search ✅

Production (Amplify):
  .env.production → VITE_API_URL=https://api.travelq.yourdomain.com
  baseURL becomes: https://api.travelq.yourdomain.com/api
  Calls go to: https://api.travelq.yourdomain.com/api/trips/search ✅

Production (EC2 with Nginx):
  No VITE_API_URL set → falls back to relative '/api'
  Calls go to: /api/trips/search (same origin, Nginx proxies) ✅