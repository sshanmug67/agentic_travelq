# nginx/default.conf — Line by Line Explanation

## Lines 12-14 — Upstream (backend address)
```nginx
upstream fastapi_backend {
    server backend:8000;
}
```
Tells Nginx "the backend lives at `backend:8000`." The name `backend` is the
service name from `docker-compose.prod.yml`. Docker's internal DNS resolves it
to the container's auto-assigned IP (e.g., 172.18.0.3). If you scaled to
multiple backend containers, you'd add more `server` lines here and Nginx
would load-balance across them.

---

## Lines 16-18 — Listen on port 80
```nginx
listen 80;
server_name _;
```
Accepts all HTTP traffic on port 80. `_` is a wildcard — matches any hostname
(`localhost`, `52.90.123.45`, `travelq.yourdomain.com`). When HTTPS is added
later, a `listen 443 ssl` block will be added here.

---

## Lines 21-24 — Security Headers
```nginx
add_header X-Frame-Options "SAMEORIGIN" always;
add_header X-Content-Type-Options "nosniff" always;
add_header X-XSS-Protection "1; mode=block" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
```
Added to every response sent to the browser:

| Header | Prevents |
|---|---|
| `X-Frame-Options: SAMEORIGIN` | Other sites embedding your app in `<iframe>` (clickjacking) |
| `X-Content-Type-Options: nosniff` | Browser guessing file types (won't treat `.txt` as JS) |
| `X-XSS-Protection: 1; mode=block` | Browser's built-in XSS filter blocks suspicious scripts |
| `Referrer-Policy` | Controls how much URL info leaks when navigating to other sites |

Falls under **Security pillar** of AWS Well-Architected Framework.

---

## Lines 27-38 — Gzip Compression
```nginx
gzip on;
gzip_vary on;
gzip_min_length 256;
gzip_types text/css application/json application/javascript ...;
```
Compresses responses before sending to browser. A 500KB React bundle becomes
~150KB gzipped. Faster page loads, less bandwidth.

- `gzip_min_length 256` — don't compress tiny responses (overhead not worth it)
- `gzip_vary on` — tells caches that gzipped and non-gzipped versions exist
- `gzip_types` — only compress these file types (images are already compressed)

---

## Lines 41-47 — React Frontend (static files)
```nginx
location / {
    root /usr/share/nginx/html;
    index index.html;
    try_files $uri $uri/ /index.html;
}
```
- `root` — where the built React files live (copied from Stage 1 of Dockerfile)
- `index` — serve `index.html` by default
- **`try_files` is critical for React Router:**

```
User visits: travelq.com/trips/123

Without try_files:
  Nginx looks for /usr/share/nginx/html/trips/123
  File doesn't exist → 404 error ❌

With try_files:
  Nginx looks for /usr/share/nginx/html/trips/123 → not found
  Tries /trips/123/ (directory) → not found
  Falls back to /index.html → React loads ✅
  React Router reads URL, renders /trips/123 page
```

React is a Single Page Application — only ONE real HTML file exists.
All routes (`/trips/123`, `/search`, `/results`) are handled by JavaScript
in the browser. Nginx must serve `index.html` for any path that isn't a real file.

---

## Lines 50-54 — Static Asset Caching
```nginx
location /assets/ {
    root /usr/share/nginx/html;
    expires 1y;
    add_header Cache-Control "public, immutable";
}
```
Vite generates filenames with content hashes: `main.a1b2c3.js`

- Code changes → hash changes → filename changes → cache busts automatically
- Safe to cache for 1 year because the filename itself changes on new deploys

```
First visit:   Browser downloads main.a1b2c3.js (500KB)
Second visit:  Cached copy used (0KB, instant)
After deploy:  New file main.x7y8z9.js → downloads fresh
```

---

## Lines 58-78 — API Proxy (reverse proxy to FastAPI)
```nginx
location /api/ {
    proxy_pass http://fastapi_backend;
    ...
}
```
Any request starting with `/api/` gets forwarded to FastAPI backend.
This is the **core of the single-origin architecture**:

```
Browser URL                        What Nginx does
─────────────────────────────────  ────────────────────────────
travelq.com/                       Serves React (index.html)
travelq.com/trips/123              Serves index.html → React Router
travelq.com/api/trips/search       Proxies → backend:8000
travelq.com/api/trips/health       Proxies → backend:8000
```

**Same domain = no CORS issues!** Browser thinks everything comes from
one server. Nginx silently forwards `/api/*` requests to a different container.

### Proxy Headers (lines 63-67)
```nginx
proxy_set_header Host $host;
proxy_set_header X-Real-IP $remote_addr;
proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Proto $scheme;
```
Pass real client info to FastAPI:

| Header | Purpose |
|---|---|
| `Host` | Original hostname browser used (e.g., travelq.com) |
| `X-Real-IP` | Client's actual IP (not Nginx container's 172.18.x.x) |
| `X-Forwarded-For` | Full chain of proxies the request passed through |
| `X-Forwarded-Proto` | Whether client used `http` or `https` |

Without these, FastAPI would think every request came from Nginx's container IP.

### Timeouts (lines 70-72)
```nginx
proxy_read_timeout 120s;
proxy_connect_timeout 30s;
proxy_send_timeout 120s;
```
Default Nginx timeout is 60s. Your Autogen agents (flight + hotel + weather +
events + places running in parallel via orchestrator) can take longer.
120s prevents Nginx from cutting off long agent requests.

### Buffering (lines 75-77)
```nginx
proxy_buffering on;
proxy_buffer_size 128k;
proxy_buffers 4 256k;
```
Nginx collects the full response from FastAPI before sending to browser.
Larger buffers (128k/256k vs default 4k/8k) handle your AI agent responses —
a full itinerary with flights, hotels, restaurants, activities, weather
can be a large JSON payload.

---

## Lines 81-84 — Block Hidden Files
```nginx
location ~ /\. {
    deny all;
    return 404;
}
```
Blocks any request for files starting with `.` (like `.env`, `.git`, `.htaccess`).
Without this, someone could try `travelq.com/.env` and potentially see your API keys.

The `~` means regex matching. `/\.` matches any path containing `/.` (a dot after a slash).