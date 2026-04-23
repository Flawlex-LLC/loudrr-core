# Loudrr — World-Class Small Team Production Checklist

**Reference operators:** Pieter Levels (solo, $3M ARR, single VPS), DHH/37signals (monolith, Kamal, no k8s), Plausible (60M pageviews/mo on small team), Linear (outsource ops to managed services).

**Philosophy:** Boring tech. Monolith first. Vertical scale before horizontal. Skip every pattern that requires a 50-person team to maintain.

**Target:** Robust + scalable to **1000 concurrent users**, runnable by 1-3 people.

---

## The lean stack (everything Loudrr needs)

| Layer | Choice | Cost (monthly) |
|-------|--------|---------------|
| VPS | Hetzner CPX31 (8GB RAM, 4 vCPU, NVMe) | ~€10 |
| Orchestration | Coolify (self-hosted, on the same box) | €0 |
| App | Django monolith, Gunicorn 4 workers × 4 threads | €0 |
| Worker | django-q2 qcluster (2 workers) | €0 |
| DB | Postgres 16 + **PgBouncer transaction mode** | €0 |
| Cache + queue broker | Redis 7 | €0 |
| Frontend | Next.js (built into Docker, served via Node) | €0 |
| CDN + DDoS | Cloudflare (free tier) | €0 |
| Errors | Sentry (free tier: 5k events/mo) | €0 |
| Uptime | UptimeRobot (free tier: 50 monitors, 5min interval) | €0 |
| Alerts → Telegram | **Sentry native Telegram Alerts Bot** + UptimeRobot Telegram integration | €0 |
| Backups | Backblaze B2 (S3-compatible, ~$0.005/GB) | <€1 |

**Total: ~€11/month** for the entire production stack handling 1000 concurrent users.

---

## The lean 25-item launch checklist

### Bot/notification safety (Days 1-2) — your #1 reputation risk
1. OutboxEvent unique constraint (event_type + reference_id) so duplicates can't exist
2. `NOTIFICATIONS_PAUSED` Constance kill switch in `OutboxService.process_event()`
3. NotificationSent audit table + 24h dedup check before sending
4. Telegram webhook update_id dedup via Redis (24h TTL)
5. Per-user notification rate limit: 5/hour via Redis INCR

### Critical code hardening (Days 3-4)
6. `@has_perm` decorators on every mutation endpoint (currently zero)
7. `IntegrityError → 400` wrappers on register/link/submit endpoints
8. ENCRYPTION_KEY in .env.example + startup assertion (fail fast if unset)
9. Wire the 3 circuit breakers to actual API calls (Twitter, TweetScout, Telegram)
10. Rotate the X Client Secret you pasted in chat

### Data integrity (Day 5)
11. Convert User/WaitlistEntry/Post/Engagement to `SafeDeleteModel`
12. `DATABASES['default']['ATOMIC_REQUESTS'] = True`
13. Switch CACHES from `LocMemCache` to `django-redis`

### Infrastructure for 1000 concurrent (Day 6)
14. **PgBouncer in transaction mode** in Coolify, point Django at port 6432:
    ```
    max_client_conn = 1000
    default_pool_size = 25
    min_pool_size = 5
    reserve_pool_size = 5
    ```
    In Django settings: `CONN_MAX_AGE = 0`, `DISABLE_SERVER_SIDE_CURSORS = True`
15. Gunicorn config: `workers = 4`, `threads = 4`, `worker_class = sync` (don't switch to ASGI/Uvicorn unless you add long-polling)
16. Postgres tuning (in Coolify or `postgresql.conf`):
    - `max_connections = 200` (let PgBouncer handle the rest)
    - `shared_buffers = 2GB` (25% of 8GB)
    - `work_mem = 16MB`
    - `effective_cache_size = 6GB`

### Backups (Day 7)
17. Coolify scheduled daily `pg_dump` → Backblaze B2 (30-day retention)
18. **Restore drill the same week** — download backup, restore to local, smoke test
19. Hetzner disk alert at 75%

### Observability + Telegram alerts (Day 8) ⭐ DETAILED BELOW
20. Sentry backend SDK + frontend SDK
21. **Sentry → Telegram Alerts Bot** (native integration, see setup below)
22. UptimeRobot ping `/health/` every 5 min → Telegram on down
23. Custom Telegram channel for app-level alerts (OutboxEvent failures, refunds, verification requests)

### Security baseline (Day 9)
24. `python manage.py check --deploy` zero warnings + `DEBUG=False` + `SECURE_SSL_REDIRECT` + `SECURE_HSTS_SECONDS=31536000` + cookie secure flags
25. Cloudflare proxy ON for `loudrr.com` (DDoS + SSL)

### Pre-launch (Day 10)
- Privacy policy + ToS pages (1 page each, plain text is fine)
- Final smoke test on staging (full happy path)
- Deploy to prod, watch for 1 hour

**That's it. 10 days. €11/month. 1000 concurrent capacity.**

---

## ⭐ Telegram ops alerts setup (the way pros do it, reusable for client projects)

You'll have **3 alert channels** in Telegram, each routed differently:

### Channel 1: `Loudrr • Errors` — wired to Sentry (5 min setup)

1. Create a private Telegram group called `Loudrr • Errors`
2. In Sentry: **Settings → Integrations → Telegram Alerts Bot** → **Add Installation**
3. Sentry walks you through adding `@SentryAlerts_bot` to your Telegram group as admin
4. Configure alert rules: **Settings → Alerts → New Alert Rule**:
   - Condition: `An issue is seen more than 5 times in 1 minute`
   - Action: send to Telegram → your group
   - Add another: `An issue is unresolved AND happens in production environment` → Telegram

This alone covers 80% of "prod is broken" notifications.

### Channel 2: `Loudrr • Uptime` — wired to UptimeRobot (5 min setup)

1. Same pattern: create Telegram group `Loudrr • Uptime`
2. In UptimeRobot: **My Settings → Add Alert Contact → Telegram**
3. Follow their wizard — they have you message `@uptimerobot_bot`, paste a code, done
4. Add this alert contact to all monitors (`/health/`, `loudrr.com/`, `dev-api.loudrr.com/health/`)

### Channel 3: `Loudrr • App Events` — your own bot, app-level events (1 hour setup)

For business-level alerts that aren't errors (X verification request created, refund issued, daily reset failed, etc.) — use your own bot. Add a helper:

```python
# backend/core/services/ops_alerts.py
import httpx
from django.conf import settings

OPS_CHANNEL_CHAT_ID = getattr(settings, "OPS_TELEGRAM_CHAT_ID", "")

def alert(message: str, severity: str = "info"):
    """Post to ops Telegram channel. Fire-and-forget; never raises.

    severity: 'info' | 'warn' | 'critical'
    """
    if not OPS_CHANNEL_CHAT_ID or not settings.TELEGRAM_BOT_TOKEN:
        return
    icon = {"info": "ℹ️", "warn": "⚠️", "critical": "🚨"}.get(severity, "")
    text = f"{icon} *Loudrr* — {message}"
    try:
        httpx.post(
            f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": OPS_CHANNEL_CHAT_ID, "text": text, "parse_mode": "Markdown"},
            timeout=5,
        )
    except Exception:
        pass  # never let alerts break the request
```

Setup:
1. Create Telegram group `Loudrr • App Events`, add your bot as admin
2. Get the chat_id: send a message in the group, then GET `https://api.telegram.org/bot<TOKEN>/getUpdates` and find `chat.id` (negative number)
3. Add to `.env`: `OPS_TELEGRAM_CHAT_ID=-100xxxxxxxxxx`

Use it sparingly — only for events YOU should know about as the operator:

```python
from core.services.ops_alerts import alert

# In XVerificationRequest creation:
alert(f"New X verification request from @{username} (claimed @{claimed})")

# In refund logic:
alert(f"Refunded {amount} karma to @{user.x_username} (post {post.id} expired)", severity="warn")

# In a try/except for critical paths:
alert(f"Daily credit reset FAILED: {e}", severity="critical")
```

### Why three channels not one

- **Errors** spam fast (10 errors = 10 messages) — keep separate so it doesn't drown out other signals
- **Uptime** is binary (down/up) — also separate for quick visual scan
- **App Events** is the curated channel you actually read every morning with coffee — high signal, low volume

This pattern is **reusable for every client project**:
- Each client gets their own Sentry project + own Telegram groups + own UptimeRobot monitors
- The `ops_alerts.alert()` helper is copy-paste-able to every Django/Node project
- Setup is ~30 min per new client

---

## What we deliberately skip (and why)

| Thing | Why we skip |
|-------|-------------|
| Kubernetes / k8s / Helm | A 1-3 person team can't maintain it. Coolify on a single box covers everything until 10k+ users. |
| Microservices | DHH writeup ([How to recover from microservices](https://world.hey.com/dhh/how-to-recover-from-microservices-ce3803cc)) and Amazon Prime Video's reversal proves it for our scale. |
| Datadog / New Relic full APM | $$$. Sentry traces cover what we need until ~10k MAU. |
| Multi-region active-active | Pick one region (Hetzner Helsinki or Falkenstein), accept the tradeoff. Real users are in 1-3 timezones early on. |
| Separate staging cluster | Use a `staging.loudrr.com` subdomain on the same box with a separate Coolify stack. Same code, different env. |
| Custom Prometheus/Grafana | Coolify's built-in panel + Sentry covers it. |
| Kafka, RabbitMQ | Redis + django-q2 (which we have) handles 1000s of jobs/sec, fine for our scale. |
| Cypress E2E in CI | 5-min manual smoke covers same ground for first 1000 users. Add Cypress when bugs justify it. |
| Locust load test for 100 users | We won't see that traffic for months. Don't optimize for hypothetical traffic. |
| GDPR export/delete endpoints | "Email hello@loudrr.com" works for first 1000 users. Build endpoints when EU traffic is real. |
| Strict CSP with nonces | 4 hours of work, breaks third-party scripts. X-Frame-Options + HSTS covers 90% of CSP value. |

---

## Postgres tuning for 1000 concurrent (the actual numbers)

This is the part most teams get wrong. With PgBouncer transaction mode:

```ini
# pgbouncer.ini
[databases]
loudrr = host=postgres port=5432 dbname=loudrr

[pgbouncer]
listen_port = 6432
listen_addr = *
auth_type = md5
pool_mode = transaction
max_client_conn = 1000
default_pool_size = 25
min_pool_size = 5
reserve_pool_size = 5
server_idle_timeout = 600
```

```python
# Django settings.py
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'HOST': 'pgbouncer',  # not postgres directly!
        'PORT': '6432',       # PgBouncer port
        # ... rest from env
        'CONN_MAX_AGE': 0,                    # required for PgBouncer transaction mode
        'DISABLE_SERVER_SIDE_CURSORS': True,  # required for transaction mode
        'OPTIONS': {
            'connect_timeout': 5,
        },
    }
}

# Atomic per request — every API call is its own DB transaction
DATABASES['default']['ATOMIC_REQUESTS'] = True
```

```bash
# postgresql.conf (or via Coolify env vars on the Postgres service)
max_connections = 200
shared_buffers = 2GB         # 25% of 8GB RAM
effective_cache_size = 6GB   # ~75% of 8GB RAM
work_mem = 16MB
maintenance_work_mem = 512MB
random_page_cost = 1.1       # NVMe SSD
effective_io_concurrency = 200
```

This config supports **1000 client connections sharing 25 actual Postgres backends**. Tested pattern from Aiven and Supabase docs.

### Gotchas (the kind that bite you in prod)

- `CONN_MAX_AGE > 0` + transaction pooling = connection state leaks between requests. **Always 0**.
- `LISTEN/NOTIFY` doesn't work in transaction mode — don't use Postgres pub/sub via PgBouncer
- Server-side cursors break — pagination via cursor doesn't work; use offset/limit
- Prepared statements break — Django handles this if `DISABLE_SERVER_SIDE_CURSORS=True`

---

## Sentry alert rules that actually matter (copy this config)

In Sentry → Alerts → Create Alert Rule:

| Rule | Condition | Action |
|------|-----------|--------|
| **Spike** | `event.count` > 50 in 5 min in `production` | Telegram → Errors channel |
| **New issue in prod** | `is:unresolved AND environment:production` first seen | Telegram → Errors |
| **Critical level** | `level:fatal` | Telegram → Errors (critical icon) |
| **5xx storm** | `event.type:transaction AND http.status_code:>=500` count > 10/5min | Telegram → Errors |

Don't create more than 4-5 alerts. Alert fatigue = ignored alerts.

---

## What "robust" actually means at this scale

1. **No silent failures**: every error reaches Sentry, every downtime reaches UptimeRobot, every business event reaches Telegram
2. **No unrecoverable state**: backups + soft delete + DB constraints
3. **Bounded blast radius**: rate limits, kill switches, circuit breakers
4. **Fast rollback**: Coolify "rollback to previous deployment" works in <2 min
5. **Real-time visibility**: 3 Telegram channels you check while drinking coffee — if all 3 are silent, prod is fine

That's the whole game. Everything else is enterprise theater.

---

## Reusable snippets for client projects

These are the things that transfer to every project you build:

1. The `ops_alerts.alert()` helper above
2. The Sentry alert rule table
3. The PgBouncer + Postgres config
4. The Coolify backup → B2 setup
5. The 25-item launch checklist (drop Loudrr-specific items, keep the structure)

Save those somewhere as your "studio playbook" — it'll save you 1-2 weeks per client.

---

## Sources

- DHH: [How to recover from microservices](https://world.hey.com/dhh/how-to-recover-from-microservices-ce3803cc), [Introducing Kamal](https://world.hey.com/dhh/introducing-kamal-9330a267)
- [levels.io](https://levels.io/) tech stack
- [Plausible: Elixir in Production](https://serokell.io/blog/elixir-in-production-plausible-analytics)
- [Sentry official Telegram Alerts Bot](https://docs.sentry.io/organization/integrations/notification-incidents/telegram-alerts-bot/)
- [Aiven PgBouncer guide](https://aiven.io/docs/products/postgresql/concepts/pg-connection-pooling)
- [Django + PgBouncer pitfalls](https://dev.to/artemooon/django-pgbouncer-in-production-pitfalls-fixes-and-survival-tricks-3jib)
- [Coolify backup strategy](https://massivegrid.com/blog/coolify-backup-strategy/)
