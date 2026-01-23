# Loudrr - Complete Developer Documentation

> **Attention Marketplace** - A community engagement platform where users earn karma by engaging with X/Twitter posts and spend karma to get engagement on their own posts.

**Last Updated:** January 2026
**Status:** Production Ready (v1.1)

---

## Table of Contents

1. [Product Overview](#1-product-overview)
2. [Tech Stack](#2-tech-stack)
3. [Architecture](#3-architecture)
4. [Directory Structure](#4-directory-structure)
5. [Database Models](#5-database-models)
6. [Backend Services](#6-backend-services)
7. [API Reference](#7-api-reference)
8. [Frontend Documentation](#8-frontend-documentation)
9. [Telegram Bot](#9-telegram-bot)
10. [Admin Panel](#10-admin-panel)
11. [Configuration](#11-configuration)
12. [Security & Robustness](#12-security--robustness)
13. [Development Setup](#13-development-setup)
14. [Deployment (Production)](#14-deployment-production)
15. [Quick Reference](#15-quick-reference)

---

## 1. Product Overview

### What is Loudrr?

Loudrr is a **karma-based attention marketplace** built as a Telegram Mini App. Users:

1. **Earn karma** by engaging with other users' X/Twitter posts (like + reply)
2. **Spend karma** to get engagement on their own posts
3. **Level up** through tiers based on their TweetScout score
4. **Earn more** with tier-based multipliers (1.0x to 1.2x)

### Core Mechanics

| Concept | Description |
|---------|-------------|
| **Karma** | In-app currency with 4 decimal precision (displays 2 decimals) |
| **Escrow** | When submitting a post, karma is locked and distributed to engagers |
| **Engagement** | Clicking a post link, liking, and replying on X (verification checks reply only) |
| **Tiers** | Anon → Normie → Degen → Based → Legend → OG → GOAT (based on TweetScout) |
| **Multipliers** | Higher tiers earn more karma per engagement (1.0x to 1.2x) |
| **Verification** | Batch verification of 10 engagements, 3 randomly spot-checked |

### User Flow

```
1. User joins via Telegram → Auto-creates account with 0 karma
2. Links X/Twitter account → Gets TweetScout score → Tier assigned
3. Engages with posts → Earns karma (unlimited daily)
4. Submits own post (20-40 karma, user chooses) → Other users engage
5. Post completes when escrow reaches 0
```

### Karma Economics

- **No inflation**: Escrow deducted = Karma earned (with multiplier)
- **Decimal precision**: 4 decimal places internally, 2 for display
- **Banker's rounding**: ROUND_HALF_EVEN for fairness
- **Example**: GOAT user earns 1.20 karma, escrow decreases by 1.20

---

## 2. Tech Stack

### Backend
| Component | Technology |
|-----------|------------|
| Framework | Django 5.0 |
| API | Django REST Framework |
| Database | PostgreSQL (Supabase) |
| Task Queue | Celery + Redis |
| Bot Framework | python-telegram-bot v21 |
| Admin UI | Django Jazzmin |

### Frontend
| Component | Technology |
|-----------|------------|
| Framework | Next.js 16.1.1 |
| Language | TypeScript 5 |
| Styling | Tailwind CSS 4 |
| UI | Custom glassmorphism (dark + orange #FF6B00) |
| Platform | Telegram Mini App |

### External APIs
| Service | Purpose |
|---------|---------|
| TweetScout | User score/tier calculation |
| Kaito.ai | Yaps score (engagement quality) |
| twitterapi.io | Reply verification (likes private since 2024) |

---

## 3. Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        TELEGRAM                                  │
│  ┌──────────────┐                    ┌──────────────────────┐   │
│  │ Telegram Bot │◄──────────────────►│  Telegram Mini App   │   │
│  │ (Commands)   │                    │  (Web Interface)     │   │
│  └──────┬───────┘                    └──────────┬───────────┘   │
└─────────┼───────────────────────────────────────┼───────────────┘
          │                                       │
          ▼                                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                     BACKEND (Django)                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   │
│  │   Bot API    │  │  MiniApp API │  │    REST API          │   │
│  │ /bot/        │  │ /api/miniapp │  │    /api/             │   │
│  └──────┬───────┘  └──────┬───────┘  └──────────┬───────────┘   │
│         │                 │                      │               │
│         └────────────────►│◄─────────────────────┘               │
│                           ▼                                      │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                    SERVICES LAYER                        │    │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────────┐    │    │
│  │  │ CreditSvc   │ │ PostSvc     │ │ EngagementSvc   │    │    │
│  │  │ (Decimal)   │ │             │ │ (Multipliers)   │    │    │
│  │  └─────────────┘ └─────────────┘ └─────────────────┘    │    │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────────┐    │    │
│  │  │ TweetScore  │ │ Kaito       │ │ Settings        │    │    │
│  │  │ (Tiers)     │ │             │ │ (Cached)        │    │    │
│  │  └─────────────┘ └─────────────┘ └─────────────────┘    │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                    PostgreSQL (Supabase)                         │
│              DecimalField for all karma values                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4. Directory Structure

```
reply-community-bot/
├── backend/
│   ├── manage.py
│   ├── requirements.txt
│   │
│   ├── echo/                          # Django project config
│   │   ├── settings.py                # ECHO_CONFIG defaults
│   │   ├── urls.py
│   │   ├── admin_site.py
│   │   └── wsgi.py
│   │
│   ├── core/                          # Users & credits app
│   │   ├── models.py                  # User (DecimalField), Transaction, SiteSetting
│   │   ├── admin.py                   # User admin + cache clearing
│   │   ├── services/
│   │   │   ├── credits.py             # CreditService (Decimal math)
│   │   │   ├── engagements.py         # With tier multipliers
│   │   │   ├── posts.py               # PostService + feed scoring
│   │   │   ├── tweet_score.py         # Tier calculation + multipliers
│   │   │   ├── settings.py            # Cached SiteSettings
│   │   │   ├── tweetscout.py          # TweetScout API
│   │   │   ├── kaito.py               # Kaito API
│   │   │   └── twitter_verification.py
│   │   └── migrations/
│   │       ├── 0017_convert_karma_to_decimal.py
│   │       ├── 0018_update_tier_multipliers.py
│   │       └── 0019_post_cost_range_settings.py
│   │
│   ├── posts/                         # Posts & engagements
│   │   ├── models.py                  # Post (DecimalField escrow), Engagement
│   │   └── migrations/
│   │       └── 0005_convert_karma_to_decimal.py
│   │
│   ├── miniapp/                       # Mini App API
│   │   ├── views.py                   # All MiniApp endpoints
│   │   └── urls.py
│   │
│   └── bots/telegram/                 # Telegram bot
│       ├── bot.py
│       └── handlers.py
│
├── frontend/
│   ├── app/
│   │   ├── page.tsx                   # Main app (~2000 lines)
│   │   ├── layout.tsx
│   │   ├── globals.css
│   │   └── api/miniapp/[...path]/route.ts
│   │
│   └── lib/
│       ├── api.ts                     # API client + types
│       └── telegram.ts
│
└── CLAUDE.md                          # This file
```

---

## 5. Database Models

### Decimal Karma System

All karma-related fields use `DecimalField(max_digits=12, decimal_places=4)`:

```python
# User model
credits = DecimalField(max_digits=12, decimal_places=4, default=Decimal('0'))
total_credits_earned = DecimalField(...)
total_credits_spent = DecimalField(...)
daily_credits_earned = DecimalField(...)

# Post model
escrow = DecimalField(max_digits=12, decimal_places=4)
initial_escrow = DecimalField(...)

# Transaction model
amount = DecimalField(max_digits=12, decimal_places=4)
balance_after = DecimalField(...)
```

### Core Models (`backend/core/models.py`)

#### User
```python
class User(AbstractBaseUser, PermissionsMixin):
    # Identity
    id = UUIDField(primary_key=True)
    telegram_id = BigIntegerField(unique=True)
    telegram_username = CharField(max_length=50)
    display_name = CharField(max_length=100)
    x_username = CharField(max_length=50)

    # Credits (Decimal)
    credits = DecimalField(max_digits=12, decimal_places=4, default=Decimal('0'))
    total_credits_earned = DecimalField(...)
    total_credits_spent = DecimalField(...)
    daily_credits_earned = DecimalField(...)

    # Gamification
    total_engagements = IntegerField(default=0)
    current_streak = IntegerField(default=0)
    tweetscout_score = FloatField(default=0)
    honesty_score = IntegerField(default=10)  # 0-10, for verification

    # Constraints
    class Meta:
        constraints = [
            CheckConstraint(check=Q(credits__gte=0), name='user_credits_non_negative'),
        ]
```

#### SiteSetting
Runtime-configurable settings with caching.

```python
class SiteSetting(Model):
    key = CharField(max_length=100, unique=True)
    value = CharField(max_length=500)
    data_type = CharField(choices=['int', 'float', 'bool', 'str', 'decimal'])
    description = TextField()
    updated_by = ForeignKey(User, null=True)
```

### Posts Models (`backend/posts/models.py`)

#### Post
```python
class Post(Model):
    id = UUIDField(primary_key=True)
    user = ForeignKey(User)
    x_link = URLField()
    tweet_id = CharField(max_length=50)
    escrow = DecimalField(max_digits=12, decimal_places=4)
    initial_escrow = DecimalField(...)
    status = CharField(choices=['active', 'completed', 'cancelled'])

    class Meta:
        constraints = [
            CheckConstraint(check=Q(escrow__gte=0), name='post_escrow_non_negative'),
        ]
```

#### Engagement
```python
class Engagement(Model):
    user = ForeignKey(User)
    post = ForeignKey(Post)
    clicked_at = DateTimeField()
    verified = BooleanField(default=False)
    credit_granted = BooleanField(default=False)
    like_verified = BooleanField(default=False)
    reply_verified = BooleanField(default=False)

    class Meta:
        constraints = [
            UniqueConstraint(fields=['user', 'post'], name='unique_user_post_engagement'),
        ]
```

---

## 6. Backend Services

### Tier/Multiplier System (`core/services/tweet_score.py`)

```python
from decimal import Decimal, ROUND_HALF_EVEN

KARMA_QUANTIZE = Decimal('0.0001')  # 4 decimal places

def calculate_engagement_karma(base_amount: Decimal, tweetscout_score: float) -> tuple[Decimal, Decimal]:
    """Calculate karma with tier multiplier."""
    multiplier = get_tweet_score_multiplier(tweetscout_score)
    karma = (base_amount * multiplier).quantize(KARMA_QUANTIZE, rounding=ROUND_HALF_EVEN)
    return karma, multiplier
```

| TweetScout Score | Tier | Multiplier |
|------------------|------|------------|
| 0-99 | Anon | 1.00x |
| 100-199 | Normie | 1.03x |
| 200-399 | Degen | 1.06x |
| 400-599 | Based | 1.10x |
| 600-799 | Legend | 1.14x |
| 800-999 | OG | 1.17x |
| 1000+ | GOAT | 1.20x |

*All multipliers configurable via SiteSettings*

### CreditService (`core/services/credits.py`)

Handles all credit operations with Decimal math.

```python
class CreditService:
    def earn(self, amount: Decimal, reference_id, reference_type, description) -> Transaction
    def spend(self, amount: Decimal, ...) -> Transaction
    def refund(self, amount: Decimal, ...) -> Transaction
    def apply_penalty(self, amount: Decimal, ...) -> Transaction
```

### Settings Service (`core/services/settings.py`)

Cached settings with 5-minute TTL, cleared on admin save.

```python
def get_setting(key: str, default=None):
    """
    Get setting from cache or database.

    Args:
        key: Setting key (e.g., 'DAILY_EARN_CAP')
        default: Default value if setting not found (optional)

    Returns:
        Setting value with proper type conversion, or default if not found

    Raises:
        KeyError: If setting not found and no default provided
    """
    cache_key = f'setting:{key}'
    value = cache.get(cache_key)
    if value is not None:
        return value

    try:
        setting = SiteSetting.objects.get(key=key)
        value = setting.get_value()
        cache.set(cache_key, value, 300)  # 5 min cache
        return value
    except SiteSetting.DoesNotExist:
        if default is not None:
            return default
        raise KeyError(f"Setting '{key}' not found")
```

### Twitter Verification Service (`core/services/twitter_verification.py`)

Verifies user engagements via twitterapi.io. **Only verifies replies** - Twitter made likes private in 2024.

```python
class TwitterVerificationService:
    """
    3 methods only (all sync):
    - verify_reply(tweet_id, x_username) → 1 API call
    - get_tweet_author(tweet_id) → 1 API call
    - extract_tweet_id(url) → no API call
    """

    def verify_reply(self, tweet_id: str, x_username: str) -> dict:
        """
        Returns:
        {
            "passed": bool,           # True if reply found
            "reply_verified": bool,   # Same as passed
            "like_verified": True,    # Always true (can't verify)
            "error": str or None,
            "skipped": bool           # True if no API key
        }
        """
```

**API Cost**: 1 call per verification (reply check only). With 3 random verifications per batch = 3 API calls per session completion.

---

## 7. API Reference

### MiniApp API (`/api/miniapp/`)

#### Get Settings
```
GET /api/miniapp/settings/

Response: {
  "post_cost_min": 20,
  "post_cost_max": 40
}
```

#### Get User Info
```
GET /api/miniapp/user/

Response: {
  "id": "uuid",
  "display_name": "John",
  "credits": 150.25,              // Decimal
  "daily_earned": 45.50,          // Decimal
  "tweetscout_score": 450,
  "tier": "based",
  "available_posts": 12,          // Posts waiting to engage
  "engaged_today": 5,             // Engagements made today
  "honesty_score": 10
}
```

#### Submit Post
```
POST /api/miniapp/post/submit/
Body: {
  "x_link": "https://x.com/user/status/123",
  "karma_amount": 30              // User chooses 20-40
}

Response: {
  "success": true,
  "post_id": "uuid",
  "new_balance": 120.25,
  "escrow": 30
}
```

#### Start Engagement Session
```
POST /api/miniapp/session/start/

Response: {
  "posts": [...],                 // Up to 10 posts
  "pending_count": 5,             // User's unverified engagements
  "pending_post_ids": [...],
  "show_verification": true       // True if pending >= 10
}
```

#### Record Click
```
POST /api/miniapp/session/click/
Body: { "post_id": "uuid" }

Response: {
  "success": true,
  "engagement_id": "uuid",
  "pending_count": 6,
  "show_verification": false
}
```

#### Complete Session (Verify)
```
POST /api/miniapp/session/complete/

Response: {
  "success": true,
  "credits_awarded": 10.50,       // With multipliers
  "new_balance": 160.75,
  "pending_count": 0,
  "verification_results": [
    { "post_id": "uuid", "passed": true }
  ],
  "honesty_score": 10
}
```

### Verification Flow

1. User clicks 10 posts → Creates `Engagement` with `verified=False`
2. User clicks "Verify" → Backend fetches 10 oldest pending (FIFO)
3. 3 random engagements spot-checked via twitterapi.io (reply only - likes are private since 2024)
4. Credits awarded proportionally based on pass rate
5. Multiplier applied: `karma = base × tier_multiplier`
6. Same amount deducted from post escrow (no inflation)

**Note**: Twitter made likes private in 2024, so verification only checks replies. Like verification always returns `true`.

---

## 8. Frontend Documentation

### Key Features

- **Decimal display**: `formatKarma()` shows 2 decimals (or none for whole numbers)
- **Karma slider**: Users choose 20-40 karma for posts
- **Progress bar**: Shows engaged/available posts
- **Tab refresh**: User data refetched on Home tab switch

### formatKarma Utility

```typescript
function formatKarma(value: number): string {
  if (Number.isInteger(value)) {
    return value.toLocaleString();  // "150"
  }
  return value.toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });  // "1.03" or "1,234.56"
}
```

### Submit Modal with Slider

```typescript
// Karma amount defaults to minimum, user can slide to max
const minCost = settings?.post_cost_min ?? 20;
const maxCost = settings?.post_cost_max ?? 40;
const [karmaAmount, setKarmaAmount] = useState(minCost);

// Slider UI
<input type="range" min={minCost} max={maxCost} value={karmaAmount} />
```

### Home Tab Progress

```typescript
// Shows "Today's Progress: 5/12" with progress bar
const total = (user.engaged_today || 0) + (user.available_posts || 0);
const progress = user.engaged_today / total * 100;
```

### Design System

- **Theme**: Dark background with orange (#FF6B00) accent
- **Style**: Glassmorphism with backdrop blur
- **Classes**: `.gold-gradient-*` classes (legacy names, all use orange)

---

## 9. Telegram Bot

### Commands

| Command | Description |
|---------|-------------|
| `/start` | Initialize user, show main menu |
| `/balance` | Display credit balance |
| `/stats` | Show user stats & streak |
| `/post <url>` | Create a post |
| `/launch` | Open mini app |

### Run Bot
```bash
python manage.py run_telegram_bot
```

---

## 10. Admin Panel

### Access
- **URL**: `/loudrr-admin/`
- **Theme**: Jazzmin dark mode

### SiteSettings Management

All settings editable at `/loudrr-admin/core/sitesetting/`:

| Setting | Default | Description |
|---------|---------|-------------|
| `CREDIT_PER_ENGAGEMENT` | 1 | Base karma per engagement |
| `POST_COST_MIN` | 20 | Minimum karma for post |
| `POST_COST_MAX` | 40 | Maximum karma for post |
| `DAILY_EARN_CAP` | 999999 | Effectively unlimited |
| `VERIFICATION_BATCH_SIZE` | 10 | Engagements per verification |
| `VERIFICATION_SAMPLE_SIZE` | 3 | API spot-checks per batch |
| `TIER_*_MULTIPLIER` | 1.0-1.2 | Per-tier karma multipliers |

**Cache clearing**: Settings cache automatically cleared on admin save.

---

## 11. Configuration

### Key SiteSettings

```python
# Engagement
CREDIT_PER_ENGAGEMENT = 1          # Base karma (before multiplier)
DAILY_EARN_CAP = 999999            # Unlimited

# Post costs
POST_COST_MIN = 20                 # Min karma to submit post
POST_COST_MAX = 40                 # Max karma to submit post

# Verification
VERIFICATION_BATCH_SIZE = 10       # Engagements per batch
VERIFICATION_SAMPLE_SIZE = 3       # API checks per batch

# Tier multipliers (TweetScout score based)
TIER_ANON_MULTIPLIER = 1.00
TIER_NORMIE_MULTIPLIER = 1.03
TIER_DEGEN_MULTIPLIER = 1.06
TIER_BASED_MULTIPLIER = 1.10
TIER_LEGEND_MULTIPLIER = 1.14
TIER_OG_MULTIPLIER = 1.17
TIER_GOAT_MULTIPLIER = 1.20
```

### Environment Variables

```bash
# Django
SECRET_KEY=your-secret-key
DEBUG=False
ALLOWED_HOSTS=yourdomain.com

# Database
DATABASE_URL=postgresql://...

# Telegram
TELEGRAM_BOT_TOKEN=123456:ABC...

# External APIs
TWEETSCOUT_API_KEY=...
TWITTER_API_KEY=...

# Frontend
MINIAPP_URL=https://app.loudrr.com
```

---

## 12. Security & Robustness

### Concurrency Safety

| Pattern | Implementation |
|---------|----------------|
| Row locking | `select_for_update()` on User/Post |
| Atomic updates | `F()` expressions for decrements |
| FIFO ordering | `order_by('clicked_at')` for verification |
| Idempotency | `get_or_create` + IntegrityError handling |

### Database Constraints

```python
CheckConstraint(check=Q(credits__gte=0), name='user_credits_non_negative')
CheckConstraint(check=Q(escrow__gte=0), name='post_escrow_non_negative')
UniqueConstraint(fields=['user', 'post'], name='unique_user_post_engagement')
```

### Verification Anti-Gaming

- **Honesty score**: 0-10, decreases on failed verifications
- **First offense**: Warning only, score drops to 9
- **Repeat offenses**: Karma penalty + score reduction
- **Score < 7**: Higher penalties per failure

---

## 13. Development Setup

### Backend
```bash
cd backend
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

### Run Both + Bot
```bash
# Terminal 1: Backend
cd backend && python manage.py runserver 8000

# Terminal 2: Frontend
cd frontend && npm run dev

# Terminal 3: Bot
cd backend && python manage.py run_telegram_bot
```

---

## 14. Deployment (Production)

### Infrastructure
| Component | Service |
|-----------|---------|
| Server | Hetzner VPS |
| Orchestration | Coolify (self-hosted) |
| Database | Supabase PostgreSQL (external) |
| Redis | Coolify managed service |
| SSL | Let's Encrypt (auto via Traefik) |

### Production URLs
| Service | URL |
|---------|-----|
| Frontend (Mini App) | `https://app.loudrr.com` |
| Backend API | `https://api.loudrr.com` |
| Django Admin | `https://api.loudrr.com/loudrr-admin/` |
| Health Check | `https://api.loudrr.com/health/` |

### Coolify Services
| Service | Watch Path | Description |
|---------|------------|-------------|
| `loudrr-backend` | `backend/**` | Django + Gunicorn |
| `loudrr-frontend` | `frontend/**` | Next.js |
| `loudrr-bot` | `backend/**` | Telegram bot |
| Redis | - | Managed service |

### Backend Dockerfile
```dockerfile
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DJANGO_SETTINGS_MODULE=echo.settings

WORKDIR /app

RUN apt-get update && apt-get install -y gcc libpq-dev curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir gunicorn

COPY . .
RUN python manage.py collectstatic --noinput --clear 2>/dev/null || true

EXPOSE 8000

# Health check with 40s startup grace period
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health/ || exit 1

# Gunicorn with full logging
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "3", "--threads", "2", \
    "--timeout", "120", "--access-logfile", "-", "--error-logfile", "-", \
    "--capture-output", "--log-level", "info", "echo.wsgi:application"]
```

### Environment Variables (Production)
```bash
# Backend
DEBUG=False
SECRET_KEY=<secure-random-key>
DATABASE_URL=postgresql://user:pass@host:5432/db  # Supabase Session Pooler
REDIS_URL=redis://default:pass@redis-host:6379/0
ALLOWED_HOSTS=api.loudrr.com
CORS_ALLOWED_ORIGINS=https://app.loudrr.com
TELEGRAM_BOT_TOKEN=<bot-token>
TWEETSCOUT_API_KEY=<api-key>
TWITTER_API_KEY=<api-key>
MINIAPP_URL=https://app.loudrr.com

# Frontend
BACKEND_URL=https://api.loudrr.com
NEXT_PUBLIC_API_URL=https://api.loudrr.com
```

### Create Superuser (Production)
Run in Coolify terminal for backend container:
```bash
python manage.py createsuperuser
```

### Deployment Flow
1. Push to `main` branch on GitHub
2. Coolify auto-deploys services based on Watch Paths
3. Backend rebuilds only when `backend/**` changes
4. Frontend rebuilds only when `frontend/**` changes

---

## 15. Quick Reference

### Key Files

| File | Purpose |
|------|---------|
| `core/services/credits.py` | Decimal credit operations |
| `core/services/tweet_score.py` | Tier multipliers + karma calculation |
| `core/services/twitter_verification.py` | Reply verification via twitterapi.io |
| `core/services/settings.py` | Cached SiteSettings |
| `miniapp/views.py` | All MiniApp API endpoints |
| `frontend/app/page.tsx` | All frontend components |
| `frontend/lib/api.ts` | API client + types |

### Common Operations

```python
# Calculate karma with multiplier
from core.services.tweet_score import calculate_engagement_karma
from decimal import Decimal

karma, multiplier = calculate_engagement_karma(
    Decimal('1'),  # base amount
    user.tweetscout_score
)
# karma = Decimal('1.1000') for Based tier

# Get cached setting
from core.services.settings import get_setting
min_cost = get_setting('POST_COST_MIN')  # Returns int: 20
```

### Testing Checklist

- [ ] Decimal karma displays correctly (e.g., "1.03", "150")
- [ ] Tier multipliers apply in verification flow
- [ ] Post cost slider works (20-40 range)
- [ ] Progress bar shows engaged/available
- [ ] Admin setting changes reflect without rebuild
- [ ] Verification processes exact clicked posts (FIFO)

---

**End of Documentation**
