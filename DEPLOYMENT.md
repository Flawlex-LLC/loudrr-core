# Loudrr Deployment Guide - Hetzner + Coolify

## Overview

This guide covers deploying Loudrr (full stack) to a Hetzner server using Coolify.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    HETZNER SERVER                           │
│                                                             │
│  ┌────────────┐  ┌────────────┐  ┌───────────────────────┐ │
│  │  Frontend  │  │  Backend   │  │    Telegram Bot       │ │
│  │  (Next.js) │  │  (Django)  │  │    (Python)           │ │
│  │  :3000     │  │  :8000     │  │    Long-running       │ │
│  └────────────┘  └────────────┘  └───────────────────────┘ │
│        │               │                    │              │
│  ┌─────┴───────────────┴────────────────────┘              │
│  │                                                         │
│  │  ┌────────────┐  ┌────────────┐                        │
│  │  │ PostgreSQL │  │   Redis    │                        │
│  │  │   :5432    │  │   :6379    │                        │
│  │  └────────────┘  └────────────┘                        │
│  │                                                         │
│  └─────────────────────────────────────────────────────────│
│                     Coolify (Traefik)                      │
│                   SSL/Reverse Proxy                        │
└─────────────────────────────────────────────────────────────┘
```

## Prerequisites

1. **Hetzner Server**: Minimum CX21 (2 vCPU, 4GB RAM, 40GB SSD) - €5.18/month
2. **Domain**: Two subdomains:
   - `api.loudrr.com` → Backend
   - `app.loudrr.com` → Frontend
3. **Coolify**: Installed on your Hetzner server

---

## Step 1: Install Coolify on Hetzner

SSH into your Hetzner server:

```bash
curl -fsSL https://cdn.coollabs.io/coolify/install.sh | bash
```

Access Coolify at `http://your-server-ip:8000` and complete setup.

---

## Step 2: Add Git Repository

In Coolify:
1. **Sources** → **Add New Source**
2. Connect your GitHub/GitLab account
3. Select the `reply-community-bot` repository

---

## Step 3: Create Services in Coolify

### 3.1 PostgreSQL Database

1. **Services** → **Add New Service** → **Database** → **PostgreSQL**
2. Configure:
   - **Name**: `loudrr-db`
   - **Database**: `loudrr`
   - **Username**: `loudrr`
   - **Password**: (generate secure password)
3. Note the internal URL: `postgresql://loudrr:password@loudrr-db:5432/loudrr`

### 3.2 Redis

1. **Services** → **Add New Service** → **Database** → **Redis**
2. **Name**: `loudrr-redis`
3. Internal URL: `redis://loudrr-redis:6379`

### 3.3 Backend (Django API)

1. **Applications** → **Add New Application**
2. **Build Pack**: Dockerfile
3. **Dockerfile Location**: `backend/Dockerfile`
4. **Domain**: `api.loudrr.com`
5. **Port**: `8000`

**Environment Variables**:
```
SECRET_KEY=<generate-with-python>
DEBUG=False
DATABASE_URL=postgresql://loudrr:password@loudrr-db:5432/loudrr
REDIS_URL=redis://loudrr-redis:6379/0
ALLOWED_HOSTS=api.loudrr.com
CORS_ALLOWED_ORIGINS=https://app.loudrr.com,https://loudrr.com
TELEGRAM_BOT_TOKEN=<your-token>
TWEETSCOUT_API_KEY=<your-key>
TWITTER_API_KEY=<your-key>
MINIAPP_URL=https://app.loudrr.com
```

### 3.4 Frontend (Next.js)

1. **Applications** → **Add New Application**
2. **Build Pack**: Dockerfile
3. **Dockerfile Location**: `frontend/Dockerfile`
4. **Domain**: `app.loudrr.com`
5. **Port**: `3000`

**Environment Variables**:
```
NEXT_PUBLIC_API_URL=https://api.loudrr.com
```

### 3.5 Telegram Bot (Background Worker)

1. **Applications** → **Add New Application**
2. **Dockerfile Location**: `backend/Dockerfile`
3. **Custom Start Command**: `python manage.py run_telegram_bot`
4. **No domain** (background process)

Same environment variables as Backend.

---

## Step 4: Migrate Database from Supabase

### Option A: pg_dump/pg_restore

```bash
# Export from Supabase
pg_dump -h db.xxxx.supabase.co -U postgres -d postgres -F c -f backup.dump

# Copy to Hetzner
scp backup.dump root@your-server:/tmp/

# Restore to Coolify PostgreSQL
docker exec -i loudrr-db pg_restore -U loudrr -d loudrr --no-owner < /tmp/backup.dump
```

### Option B: Django dumpdata/loaddata

```bash
# Export (with Supabase connected)
python manage.py dumpdata --natural-foreign --natural-primary -e contenttypes -e auth.Permission > backup.json

# Import (on Hetzner)
python manage.py loaddata backup.json
```

---

## Step 5: Run Migrations

In Coolify, use **Execute Command** on the backend container:

```bash
python manage.py migrate
python manage.py createsuperuser
```

---

## Step 6: DNS Configuration

Add A records pointing to your Hetzner server IP:

| Subdomain | Type | Value |
|-----------|------|-------|
| `api.loudrr.com` | A | `your-server-ip` |
| `app.loudrr.com` | A | `your-server-ip` |

Coolify automatically provisions SSL via Let's Encrypt.

---

## Step 7: Health Checks

Verify deployment:
- Backend: `https://api.loudrr.com/health/` → `{"status": "healthy"}`
- Frontend: `https://app.loudrr.com` → App loads
- Bot: `/start` command works in Telegram

---

## Environment Variables Reference

| Variable | Service | Description |
|----------|---------|-------------|
| `SECRET_KEY` | Backend, Bot | Django secret |
| `DATABASE_URL` | Backend, Bot | PostgreSQL URL |
| `REDIS_URL` | Backend, Bot | Redis URL |
| `ALLOWED_HOSTS` | Backend | API domains |
| `CORS_ALLOWED_ORIGINS` | Backend | Frontend domains |
| `TELEGRAM_BOT_TOKEN` | Backend, Bot | Bot token |
| `TWEETSCOUT_API_KEY` | Backend, Bot | TweetScout key |
| `TWITTER_API_KEY` | Backend, Bot | Twitter API key |
| `MINIAPP_URL` | Backend, Bot | Frontend URL |
| `NEXT_PUBLIC_API_URL` | Frontend | Backend URL |

Generate keys:
```python
# SECRET_KEY
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"

# ENCRYPTION_KEY
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

---

## Monitoring

### Logs
```bash
docker logs -f loudrr-backend
docker logs -f loudrr-frontend
docker logs -f loudrr-bot
```

### Backups
```bash
# Automated PostgreSQL backup (add to crontab)
0 2 * * * docker exec loudrr-db pg_dump -U loudrr loudrr > /backups/loudrr_$(date +\%Y\%m\%d).sql
```

---

## Troubleshooting

### Backend not starting
- Check `docker logs loudrr-backend`
- Verify DATABASE_URL is correct
- Ensure PostgreSQL container is healthy

### CORS errors
- Add frontend domain to `CORS_ALLOWED_ORIGINS`
- Include both http and https variants

### Bot not responding
- Check `docker logs loudrr-bot`
- Verify TELEGRAM_BOT_TOKEN
- Ensure no webhook is configured (use polling)

### Database connection refused
- Verify PostgreSQL is running: `docker ps`
- Check internal network connectivity
- Verify credentials in DATABASE_URL

---

## Cost Comparison

| Resource | Hetzner | Previous (Supabase+Vercel) |
|----------|---------|---------------------------|
| Server | €5-10/mo | - |
| Database | Included | $25/mo (Supabase Pro) |
| Frontend | Included | $20/mo (Vercel Pro) |
| **Total** | **€5-10/mo** | **$45/mo** |

---

## Alternative: Docker Compose Deployment

Instead of individual services, deploy everything via docker-compose:

1. In Coolify, select **Docker Compose** build pack
2. Point to `docker-compose.yml` in repo root
3. Add environment variables in Coolify
4. Deploy

This starts all services (db, redis, backend, frontend, bot) together.

---

## Next Steps

1. ✅ Deploy to Hetzner
2. ✅ Migrate data from Supabase
3. ✅ Configure SSL
4. ✅ Test all features
5. 🔲 Set up automated backups
6. 🔲 Configure monitoring alerts
7. 🔲 Update Telegram bot webhook URL (if using webhooks)
