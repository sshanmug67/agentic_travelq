# ec2-setup.sh — Deep Dive Explanation

## What Is This File?

A **one-time setup script** you run on a brand new EC2 instance. A fresh Amazon Linux EC2 has nothing installed — no Docker, no Git, nothing. This script installs everything TravelQ needs. You run it once, then never again.

---

## How To Use It

```
Step 1: Copy script from your machine to EC2
  scp -i your-key.pem ec2-setup.sh ec2-user@YOUR_IP:~/

Step 2: SSH into EC2
  ssh -i your-key.pem ec2-user@YOUR_IP

Step 3: Run it
  chmod +x ec2-setup.sh && ./ec2-setup.sh

Step 4: Log out and back in (for Docker permissions)
  exit
  ssh -i your-key.pem ec2-user@YOUR_IP
```

- `scp` = Secure Copy — copies a file over SSH from your machine to the EC2 instance
- `chmod +x` = Make the file executable (Linux requires this for scripts)

---

## Line-by-Line Breakdown

---

### The Shebang — `#!/bin/bash`

This tells Linux which interpreter to use. `/bin/bash` means "use the Bash shell." Without it, Linux might try a different shell and commands could behave differently.

---

### `set -e`

**"Exit immediately if ANY command fails."** Without this, the script would continue even if Docker failed to install — `systemctl start docker` would also fail, and you'd get a cascade of confusing errors. With `set -e`, it stops at the first failure so you know exactly what went wrong.

> This is a bash best practice for setup scripts.

---

### `sudo yum update -y`

Updates all system packages to latest versions. Like **Windows Update** but for Linux.

| Part | Meaning |
|------|---------|
| `sudo` | Run as administrator (ec2-user isn't root) |
| `yum` | Amazon Linux package manager (like `apt` on Ubuntu) |
| `-y` | Auto-confirm — "yes to all" without prompting |

A fresh EC2 might have security vulnerabilities in pre-installed packages. Always update first.

---

### Install Docker (Lines 22–26)

```bash
sudo yum install -y docker
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker ec2-user
```

| Command | What It Does |
|---------|--------------|
| `yum install -y docker` | Downloads and installs Docker |
| `systemctl start docker` | Starts Docker service **right now** |
| `systemctl enable docker` | Auto-start Docker on every boot (survives reboot) |
| `usermod -aG docker ec2-user` | Adds ec2-user to the "docker" group |

#### Why `start` AND `enable`?

Two separate concepts:

- `start` = turn it on **now** (won't survive reboot)
- `enable` = auto-start on every future boot

You need both. `start` for immediate use, `enable` so it persists.

#### Why `usermod -aG docker ec2-user`?

By default, only `root` can run Docker. This grants `ec2-user` permission:

```bash
# Without usermod:
sudo docker compose up -d      # annoying — needs sudo every time

# With usermod (after re-login):
docker compose up -d            # clean — no sudo needed
```

**Flags explained:**

- `-a` = **append** (add to group without removing from other groups)
- `-G` = **supplementary group** (the docker group)

Without `-a`, the user would be **removed** from all other groups — very bad.

> **Critical:** You must **log out and back in** after running the script. Group membership only takes effect on a new session.

---

### Install Docker Compose v2 (Lines 29–33)

```bash
sudo mkdir -p /usr/local/lib/docker/cli-plugins
sudo curl -SL "https://github.com/docker/compose/releases/latest/download/docker-compose-linux-$(uname -m)" \
    -o /usr/local/lib/docker/cli-plugins/docker-compose
sudo chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
```

Docker Compose v2 is a **plugin** for Docker (not a separate binary like v1 was).

| Part | Meaning |
|------|---------|
| `mkdir -p` | Create the plugins directory. `-p` prevents error if it exists |
| `curl -SL` | Download the binary. `-S` = show errors, `-L` = follow redirects |
| `$(uname -m)` | Auto-detects CPU architecture — `x86_64` or `aarch64` |
| `-o ...` | Save to Docker's plugin directory |
| `chmod +x` | Make the binary executable |

#### v1 vs v2 — What Changed?

```
Old (v1):  docker-compose up -d     ← separate binary, hyphen
New (v2):  docker compose up -d      ← Docker plugin, space
```

v2 is faster and is the current standard. Our `docker-compose.prod.yml` uses v2 syntax.

---

### Install Git and htop (Line 37)

```bash
sudo yum install -y git htop
```

| Tool | Purpose |
|------|---------|
| `git` | Clone your GitHub repo onto EC2 |
| `htop` | Interactive process/memory monitor (like **Task Manager** for Linux) |

`htop` is useful for monitoring container memory on your t3.small (2GB RAM):

```
  PID USER      VIRT    RES  %CPU  %MEM  COMMAND
  123 root      850M   450M   2.1  22.5  docker-backend
  124 root      200M   120M   0.5   6.0  celery-worker
  125 root       50M    25M   0.1   1.2  redis-server
  126 root      100M    60M   0.3   3.0  nginx
```

---

### Install Certbot for SSL (Line 41)

```bash
sudo yum install -y certbot || echo "Certbot install skipped (can install later)"
```

- **Certbot** = free Let's Encrypt SSL certificate tool (gives your site HTTPS)
- `||` is a fallback — if certbot fails to install, it prints a message instead of crashing
- **Short-circuit evaluation:** `command1 || command2` runs `command2` only if `command1` fails
- SSL setup happens separately later, so this isn't critical during initial provisioning

---

### Configure Docker Log Rotation (Lines 45–55)

```bash
sudo tee /etc/docker/daemon.json > /dev/null <<DAEMON_CFG
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
DAEMON_CFG
sudo systemctl restart docker
```

Creates a Docker config that sets **default log rotation** for ALL containers.

| Part | Meaning |
|------|---------|
| `tee` | Writes to a file (needs `sudo` to write to `/etc/`) |
| `> /dev/null` | Suppresses `tee`'s echo to terminal |
| `<<DAEMON_CFG ... DAEMON_CFG` | **"Here document"** — everything between the markers becomes file content |
| `systemctl restart docker` | Reload Docker with new config |

#### What the Config Does

| Setting | Meaning |
|---------|---------|
| `log-driver: json-file` | Use JSON format for logs (Docker default, but explicit) |
| `max-size: 10m` | Each log file maxes at 10 MB |
| `max-file: 3` | Keep only 3 rotated files per container |

Each container uses at most **30 MB** of disk for logs (3 × 10 MB).

#### Why This Matters — A LOT

```
Without log rotation:                With log rotation:

Day 1:   backend.log  =   50 MB     backend-0.log  =  10 MB (current)
Day 7:   backend.log  =  500 MB     backend-1.log  =  10 MB (previous)
Day 30:  backend.log  =    3 GB     backend-2.log  =  10 MB (oldest)
Day 90:  backend.log  =   15 GB     Total: 30 MB forever
Day 100: DISK FULL — everything crashes
```

> Without this, a runaway container could fill the entire 20GB disk. This is one of the most common production incidents — great to mention in interviews!

This is a safety net — even if a container in docker-compose doesn't specify its own logging options, it still gets rotation from this daemon config.

---

### Create App Directory (Line 58)

```bash
mkdir -p ~/agentic-travelq
```

Creates the directory where you'll clone your GitHub repo. `~` expands to `/home/ec2-user/`. `-p` means "don't error if it already exists."

---

### Post-Setup Instructions (Lines 60–80)

The `echo` statements at the end are just printed reminders of what to do next — they don't execute anything. A nice UX touch so you don't have to go back to the docs.

---

## Before & After: What Your EC2 Looks Like

```
Before ec2-setup.sh:              After ec2-setup.sh:

EC2 (bare Amazon Linux)           EC2 (ready for TravelQ)
├── /usr/bin/                      ├── /usr/bin/
│   └── (basic tools only)        │   ├── docker
│                                  │   ├── git
│                                  │   └── htop
│                                  ├── /usr/local/lib/docker/cli-plugins/
│                                  │   └── docker-compose
│                                  ├── /etc/docker/
│                                  │   └── daemon.json (log rotation)
│                                  ├── /home/ec2-user/
│                                  │   └── agentic-travelq/ (empty, ready)
│                                  └── Docker service: running + enabled

No Docker                          Docker ready
No Git                             Git ready
No Compose                         Compose ready
No log safety                      Log rotation configured
```

---

## Key Concepts Summary

| Concept | What It Means | Why It Matters |
|---------|---------------|----------------|
| `set -e` | Stop on first error | Prevents cascading failures |
| `systemctl start` | Start service now | Immediate availability |
| `systemctl enable` | Start on boot | Survives reboots |
| `usermod -aG` | Add user to group | No `sudo` for Docker |
| `daemon.json` | Docker global config | Log rotation prevents disk-full crashes |
| `chmod +x` | Make file executable | Required for Linux scripts |
| `scp` | Secure copy over SSH | Transfer files to EC2 |
| Here document (`<<EOF`) | Inline file content | Write config files from scripts |

---

## Interview-Ready Talking Points

1. **"I wrote a provisioning script for EC2"** — shows infrastructure automation
2. **"I configured log rotation to prevent disk-full incidents"** — shows production awareness
3. **"I used `set -e` for fail-fast behavior"** — shows bash best practices
4. **"Docker Compose v2 as a plugin vs v1 standalone"** — shows you're current
5. **"Group permissions with usermod so we don't need sudo"** — shows Linux security awareness
