# Loudrr - Complete Developer Documentation

> **Attention Marketplace** - A community engagement platform where users earn karma by engaging with X/Twitter posts and spend karma to get engagement on their own posts.

**Last Updated:** January 2026
**Status:** Production Ready (v1.2)

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
13. [Known Issues & Edge Cases](#13-known-issues--edge-cases)
14. [Cost Estimation](#14-cost-estimation)
15. [Development Setup](#15-development-setup)
16. [Deployment (Production)](#16-deployment-production)
17. [Quick Reference](#17-quick-reference)
18. [Files to Delete](#18-files-to-delete)

---

## 1. Product Overview

### What is Loudrr?

Loudrr is a **karma-based attention marketplace** built as a Telegram Mini App. Users:

1. **Earn karma** by engaging with other users' X/Twitter posts (like + reply)
2. **Spend karma** to get engagement on their own posts
3. **Level up** through tiers based on their TweetScout score
4. **Earn more** with tier-based multipliers (1.0x to 1.35x)

### Core Mechanics

| Concept | Description |
|---------|-------------|
| **Karma** | In-app currency with 4 decimal precision (displays 2 decimals) |
| **Escrow** | When submitting a post, karma is locked and distributed to engagers |
| **Engagement** | Clicking a post link, liking, and replying on X (verification checks reply only) |
| **Tiers** | Anon -> Normie -> Degen -> Based -> Legend -> OG -> GOAT (based on TweetScout) |
| **Multipliers** | Higher tiers earn more karma per engagement (1.0x to 1.35x) |
| **Verification** | 100% verification via `from:user conversation_id:tweet` query |

### Karma Economics

- **No inflation**: Escrow deducted = Karma earned (with multiplier)
- **Decimal precision**: 4 decimal places internally, 2 for display
- **Banker's rounding**: ROUND_HALF_EVEN for fairness
- **Example**: GOAT user earns 1.35 karma, escrow decreases by 1.35

---

## 2. Tech Stack

### Backend
| Component | Technology | Version |
|-----------|------------|---------|
| Framework | Django | 5.0 |
| API | Django REST Framework | 3.14 |
| Database | PostgreSQL | 15 (Supabase) |
| Task Queue | Celery | 5.3 |
| Cache | Redis | 7.x |
| Bot Framework | python-telegram-bot | v21 |
| Admin UI | Django Jazzmin | 3.0 |
| HTTP Client | httpx | sync |
| Audit | django-auditlog | 3.0 |
| Static Files | WhiteNoise | 6.x |

### Frontend
| Component | Technology |
|-----------|------------|
| Framework | Next.js 16.1.1 |
| Language | TypeScript 5 |
| Styling | Tailwind CSS 4 |
| UI | Custom glassmorphism (dark + orange #FF6B00) |
| Platform | Telegram Mini App |

### External APIs
| Service | Purpose | Cost |
|---------|---------|------|
| TweetScout | User score/tier (on X link only) | ~$0.01/call |
| twitterapi.io | Reply verification | 15 credits (~$0.00015)/call |

**Note**: Kaito.ai integration was **REMOVED**. All Kaito fields deleted.

---

## 3. Architecture

```
+-------------------------------------------------------------------+
|                        TELEGRAM                                    |
|  +--------------+                    +----------------------+      |
|  | Telegram Bot |<------------------>|  Telegram Mini App   |      |
|  | (Commands)   |                    |  (Web Interface)     |      |
|  +------+-------+                    +----------+-----------+      |
+---------|------------------------------------|---------------------|
          |                                    |
          v                                    v
+-------------------------------------------------------------------+
|                     BACKEND (Django)                               |
|  +--------------+  +--------------+  +----------------------+      |
|  |   Bot API    |  |  MiniApp API |  |    REST API          |      |
|  | /bot/        |  | /api/miniapp |  |    /api/             |      |
|  +------+-------+  +------+-------+  +----------+-----------+      |
|         |                 |                      |                 |
|         +---------------->|<---------------------+                 |
|                           v                                        |
|  +---------------------------------------------------------+      |
|  |                    SERVICES LAYER                        |      |
|  |  +-------------+ +-------------+ +-----------------+     |      |
|  |  | CreditSvc   | | PostSvc     | | EngagementSvc   |     |      |
|  |  | [ATOMIC]    | |             | | [ATOMIC]        |     |      |
|  |  +-------------+ +-------------+ +-----------------+     |      |
|  |  +-------------+ +-------------+ +-----------------+     |      |
|  |  | TweetScore  | | TwitterAPI  | | Settings        |     |      |
|  |  | (Tiers)     | | (Verify)    | | (Cached 5min)   |     |      |
|  |  +-------------+ +-------------+ +-----------------+     |      |
|  +---------------------------------------------------------+      |
+-------------------------------------------------------------------+
                           |
                           v
+-------------------------------------------------------------------+
|                    PostgreSQL (Supabase)                           |
|              DecimalField(max_digits=12, decimal_places=4)         |
+-------------------------------------------------------------------+
```

---

## 4. Directory Structure

```
reply-community-bot/
+-- backend/
|   +-- manage.py
|   +-- requirements.txt
|   +-- Dockerfile
|   |
|   +-- echo/                          # Django project config
|   |   +-- settings.py                # All config + ECHO_CONFIG
|   |   +-- urls.py                    # URL routing
|   |   +-- admin_site.py              # Custom admin site
|   |   +-- wsgi.py                    # WSGI entry point
|   |   +-- celery.py                  # Celery configuration
|   |
|   +-- core/                          # Users & credits app
|   |   +-- models.py                  # User, Transaction, XProfile, SiteSetting, XPTransaction
|   |   +-- admin.py                   # User admin (6 actions, color coding)
|   |   +-- backends.py                # TelegramIDBackend for auth
|   |   +-- services/
|   |   |   +-- credits.py             # CreditService [ATOMIC]
|   |   |   +-- engagements.py         # EngagementService [ATOMIC]
|   |   |   +-- posts.py               # PostService + feed scoring
|   |   |   +-- tweet_score.py         # Tier multipliers
|   |   |   +-- settings.py            # Cached SiteSettings
|   |   |   +-- tweetscout.py          # TweetScout API client
|   |   |   +-- twitter_verification.py # [OPTIMIZED] from:user query
|   |   |   +-- xp.py                  # XP service for sponsored
|   |   |   +-- x_url_resolver.py      # URL resolution
|   |   |   +-- gamification.py        # Stats & leaderboards
|   |   |   +-- campaigns.py           # Campaign/giveaway logic
|   |
|   +-- posts/                         # Posts & engagements
|   |   +-- models.py                  # Post, Engagement, SponsoredPost, Campaign, CampaignEntry, VerificationBatch
|   |   +-- admin.py                   # Post admin (custom form), Campaign admin
|   |   +-- tasks.py                   # Celery async verification
|   |
|   +-- miniapp/                       # Mini App API
|   |   +-- views.py                   # All MiniApp endpoints
|   |   +-- urls.py
|   |   +-- models.py                  # EMPTY (session models removed)
|   |
|   +-- bots/telegram/                 # Telegram bot [FUNCTIONAL]
|   |   +-- bot.py                     # Bot setup
|   |   +-- handlers.py                # 12 command handlers
|   |   +-- keyboards.py               # Inline keyboards
|   |   +-- image_utils.py             # PIL balance cards
|   |
|   +-- bots/discord/                  # [EMPTY - NOT IMPLEMENTED]
|   |   +-- __init__.py
|   |   +-- cogs/__init__.py
|   |
|   +-- redirects/                     # Redirect tracking
|   |   +-- views.py                   # Encrypted redirect handler
|   |   +-- urls.py
|   |   +-- models.py                  # EMPTY
|   |   +-- admin.py                   # EMPTY
|   |
|   +-- static/
|       +-- admin/css/loudrr-theme.css # Custom admin theme
|       +-- images/                    # Logo assets
|
+-- frontend/
|   +-- app/
|   |   +-- page.tsx                   # Main app (~2000 lines)
|   |   +-- layout.tsx
|   |   +-- globals.css
|   |   +-- api/miniapp/[...path]/route.ts
|   +-- lib/
|       +-- api.ts                     # API client + types
|       +-- telegram.ts                # Telegram SDK wrapper
|
+-- CLAUDE.md                          # This file
+-- .env                               # Environment variables (not committed)
```

---

## 5. Database Models

### Core Models (`backend/core/models.py`)

#### User
```python
class User(AbstractBaseUser, PermissionsMixin):
    id = UUIDField(primary_key=True)
    telegram_id = BigIntegerField(unique=True)
    telegram_username = CharField(max_length=50)
    telegram_photo_url = URLField(max_length=500)
    display_name = CharField(max_length=100)
    x_username = CharField(max_length=50)

    # Credits (Decimal - 4 places)
    credits = DecimalField(max_digits=12, decimal_places=4, default=Decimal('0'))
    total_credits_earned = DecimalField(...)
    total_credits_spent = DecimalField(...)
    daily_credits_earned = DecimalField(...)

    # Gamification
    total_engagements = IntegerField(default=0)
    total_posts = IntegerField(default=0)
    current_streak = IntegerField(default=0)
    longest_streak = IntegerField(default=0)
    tweetscout_score = FloatField(default=0)
    honesty_score = IntegerField(default=50)  # 0-50 range

    # XP (Sponsored)
    sponsored_xp = IntegerField(default=0)
    total_sponsored_xp_earned = IntegerField(default=0)
    sponsored_engagements = IntegerField(default=0)

    # Status
    is_banned = BooleanField(default=False)
    ban_reason = TextField(blank=True)

    class Meta:
        constraints = [
            CheckConstraint(check=Q(credits__gte=0), name='user_credits_non_negative'),
            CheckConstraint(check=Q(honesty_score__gte=0) & Q(honesty_score__lte=50), ...),
            CheckConstraint(check=Q(sponsored_xp__gte=0), ...),
        ]
```

#### XProfile
```python
class XProfile(Model):
    """X/Twitter profile from TweetScout - fetched ONCE on link."""
    user = OneToOneField(User, related_name="x_profile")
    x_user_id = CharField(max_length=50)      # Permanent Twitter ID
    username = CharField(max_length=50)        # @handle
    display_name = CharField(max_length=100)
    bio = TextField()
    followers_count = IntegerField(default=0)
    following_count = IntegerField(default=0)
    tweets_count = IntegerField(default=0)
    score = FloatField(default=0)              # TweetScout score
    avatar_url = URLField()
    banner_url = URLField()
    is_verified = BooleanField(default=False)
    can_dm = BooleanField(default=False)
    raw_tweetscout_data = JSONField()          # Full API response
    fetched_at = DateTimeField()
```

### Posts Models (`backend/posts/models.py`)

#### Post
```python
class Post(Model):
    id = UUIDField(primary_key=True)
    user = ForeignKey(User)
    x_link = URLField()
    tweet_id = CharField(max_length=50)

    # Cached tweet content
    tweet_text = TextField()
    tweet_author_name = CharField()
    tweet_author_username = CharField()
    tweet_author_avatar = URLField()
    tweet_media = JSONField(default=list)
    tweet_created_at = DateTimeField()

    # Escrow
    escrow = DecimalField(max_digits=12, decimal_places=4)
    initial_escrow = DecimalField(...)
    status = CharField(choices=['active', 'completed', 'cancelled'])
    is_sponsored = BooleanField(default=False)
    platform = CharField(choices=['telegram', 'discord', 'web'])
    redirect_token = CharField(unique=True)

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
    verification_data = JSONField(null=True)

    class Meta:
        constraints = [
            UniqueConstraint(fields=['user', 'post'], name='unique_user_post_engagement'),
            CheckConstraint(check=~Q(verified=False, credit_granted=True), name='engagement_credit_requires_verification'),
        ]
```

---

## 6. Backend Services

### Twitter Verification (`core/services/twitter_verification.py`)

**OPTIMIZED**: Uses `from:user conversation_id:tweet` for cost efficiency.

```python
class TwitterVerificationService:
    BASE_URL = "https://api.twitterapi.io/twitter"

    def verify_reply(self, tweet_id: str, x_username: str) -> dict:
        """
        Query: GET /tweet/advanced_search?query=from:{user} conversation_id:{tweet}

        Cost: 15 credits (~$0.00015) - FIXED regardless of tweet's reply count

        Returns:
        {
            "passed": bool,
            "reply_verified": bool,
            "like_verified": True,  # Always true (can't verify)
            "error": str or None,
            "skipped": bool
        }
        """

    def get_tweet_content(self, tweet_id: str) -> dict:
        """Fetch tweet for caching on submission. 15 credits."""

    def extract_tweet_id(self, url: str) -> str:
        """Extract ID from URL. No API call."""
```

### Tier/Multiplier System (`core/services/tweet_score.py`)

| TweetScout Score | Tier | Multiplier |
|------------------|------|------------|
| 0-99 | Anon | 1.00x |
| 100-199 | Normie | 1.10x |
| 200-399 | Degen | 1.15x |
| 400-599 | Based | 1.20x |
| 600-799 | Legend | 1.25x |
| 800-999 | OG | 1.30x |
| 1000+ | GOAT | 1.35x |

*All configurable via SiteSettings*

### CreditService (`core/services/credits.py`)

**ATOMIC**: All operations use `@transaction.atomic` + `select_for_update()`.

```python
class CreditService:
    @transaction.atomic
    def earn(amount, reference_id, reference_type, description) -> Transaction
    def spend(amount, ...) -> Transaction
    def refund(amount, ...) -> Transaction
    def apply_penalty(amount, ...) -> Transaction
    def admin_grant(amount, admin_id, description) -> Transaction
```

---

## 7. API Reference

### MiniApp API (`/api/miniapp/`)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/settings/` | GET | Get app settings |
| `/user/` | GET | Get user info + available_posts + engaged_today |
| `/user/stats/` | GET | Detailed stats |
| `/session/start/` | POST | Get posts to engage |
| `/session/click/` | POST | Record click |
| `/session/verify-return/` | POST | Mark return from X |
| `/session/complete/` | POST | Verify & award karma |
| `/post/submit/` | POST | Submit X post |
| `/x/link/` | POST | Link X account |
| `/claim/queue/` | POST | Queue async verification |
| `/claim/history/` | GET | Batch history |

---

## 8. Frontend Documentation

- **Theme**: Dark + orange (#FF6B00)
- **formatKarma()**: 2 decimals for fractional, none for whole
- **Karma slider**: 20-40 range
- **Progress bar**: engaged_today / (engaged_today + available_posts)

---

## 9. Telegram Bot

### Status: FUNCTIONAL

| Command | Description |
|---------|-------------|
| `/start` | Welcome + onboarding |
| `/help` | All commands |
| `/balance` | Visual balance card (PIL image) |
| `/stats` | User statistics |
| `/engage` | Open Mini App |
| `/feed [n]` | Get n posts (max 20) |
| `/post <url>` | Submit X post |
| `/leaderboard` | Top engagers |
| `/launch` | Pinnable "Play Now" message |
| `/give` | Admin: grant credits |

**Run**: `python manage.py run_telegram_bot`

---

## 10. Admin Panel

### Access
- **URL**: `/loudrr-admin/`
- **Theme**: Jazzmin darkly

### Registered Models

| App | Model | Editable | Notes |
|-----|-------|----------|-------|
| core | User | YES | 8 bulk actions |
| core | Transaction | READ-ONLY | Audit trail |
| core | SiteSetting | value only | No add/delete |
| core | XProfile | READ-ONLY | Auto-created |
| core | XPTransaction | READ-ONLY | Audit trail |
| posts | Post | YES | Custom creation form |
| posts | Engagement | Partial | View only |
| posts | SponsoredPost | YES | +XP badge posts |
| posts | Campaign | YES | Giveaways |
| posts | CampaignEntry | Partial | View + mark winners |

### NOT Registered (Gaps)
- `core.AuditLog` - Verification audits
- `posts.VerificationBatch` - Async batches

### Admin Actions

**User Admin:**
- Grant 10/50/100 credits
- Revoke 10 credits
- Grant 10/50 XP
- Fetch X Profile from TweetScout
- Ban/Unban users

**Campaign Admin:**
- Activate campaigns
- Select winners

### Admin Issues

| Issue | Impact |
|-------|--------|
| `user.get_streak_multiplier()` missing | Balance card errors |
| `/help` shows "80 karma" | Hardcoded, should be dynamic |
| AuditLog not registered | Can't view verification audits |
| VerificationBatch not registered | Can't view async batches |

---

## 11. Configuration

### SiteSettings (in DB, 5-min cache)

| Setting | Default | Description |
|---------|---------|-------------|
| CREDIT_PER_ENGAGEMENT | 1 | Base karma |
| POST_COST_MIN | 20 | Min escrow |
| POST_COST_MAX | 40 | Max escrow |
| DAILY_EARN_CAP | 999999 | Unlimited |
| MIN_ENGAGEMENTS_TO_CLAIM | 10 | Min to verify |
| MIN_SESSION_DURATION_SECONDS | 150 | Anti-gaming |
| SPONSORED_XP_PER_ENGAGEMENT | 5 | XP per +XP post |
| TIER_*_THRESHOLD | varies | Score thresholds |
| TIER_*_MULTIPLIER | 1.0-1.35 | Karma multipliers |

### Environment Variables

```bash
# Django
SECRET_KEY=...
DEBUG=False
ALLOWED_HOSTS=api.loudrr.com
ENCRYPTION_KEY=...           # For redirect URLs

# Database (Supabase)
DATABASE_URL=postgresql://...

# Redis
REDIS_URL=redis://...

# Telegram
TELEGRAM_BOT_TOKEN=...
ADMIN_TELEGRAM_IDS=123,456   # Comma-separated

# APIs
TWEETSCOUT_API_KEY=...
TWITTER_API_KEY=...          # twitterapi.io

# Frontend
MINIAPP_URL=https://app.loudrr.com
CORS_ALLOWED_ORIGINS=https://app.loudrr.com
```

---

## 12. Security & Robustness

### Atomic Transactions

| Service | Atomic | Method |
|---------|--------|--------|
| CreditService.earn() | YES | @transaction.atomic + select_for_update |
| CreditService.spend() | YES | @transaction.atomic + select_for_update |
| record_button_engagement() | YES | Lock Post -> User (order) |
| CompleteSessionView | YES | Locks posts sorted by pk |
| SubmitPostView | YES | @transaction.atomic |
| Celery _run_verification | YES | @transaction.atomic |

### Database Constraints

```python
# User
CheckConstraint(check=Q(credits__gte=0))
CheckConstraint(check=Q(honesty_score__gte=0) & Q(honesty_score__lte=50))

# Post
CheckConstraint(check=Q(escrow__gte=0))

# Engagement
UniqueConstraint(fields=['user', 'post'])
CheckConstraint(check=~Q(verified=False, credit_granted=True))
```

---

## 13. Known Issues & Edge Cases

### Karma Inflation/Deflation Risks

| Issue | Status | Details |
|-------|--------|---------|
| Multiplier mismatch | FIXED | Same karma_amount for escrow deduct + credit |
| Partial escrow | HANDLED | Skip if escrow < karma_amount |
| Race condition | LOW RISK | F() + escrow__gte filter |

### Potential Issues

1. **Honesty score range changed**: 0-10 -> 0-50
2. **Failed verification deletes engagement**: User can retry (gaming risk)
3. **API errors give benefit of doubt**: passed=True, skipped=True

### Telegram Bot Issues

1. `user.get_streak_multiplier()` method missing
2. `/help` hardcodes "80 karma"
3. `/balance` hardcodes daily cap 100

---

## 14. Cost Estimation

### twitterapi.io Pricing

| Item | Credits | USD |
|------|---------|-----|
| Per tweet returned | 15 | $0.00015 |
| Empty response | 15 (min) | $0.00015 |
| 1 USD | 100,000 | - |

### Monthly Cost Estimates

**Scenario: 1,000 active users, 100 posts/day**

| Approach | Calculation | Monthly Cost |
|----------|-------------|--------------|
| Old (fetch all replies) | 100 posts x 150 replies x $0.00015 x 30 | ~$67.50 |
| **New (from:user query)** | 100 posts x 100 engagers x $0.00015 x 30 | **~$45** |

**Per 100k verifications**: $15

---

## 15. Development Setup

```bash
# Backend
cd backend
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 8000

# Frontend
cd frontend
npm install
npm run dev

# Bot
cd backend
python manage.py run_telegram_bot

# Celery (optional)
cd backend
celery -A echo worker -l info
```

---

## 16. Deployment (Production)

### Infrastructure

| Component | Service | Details |
|-----------|---------|---------|
| **Server** | Hetzner VPS | 1 server, shared CPU |
| **Orchestration** | Coolify | Self-hosted PaaS |
| **Database** | Supabase PostgreSQL | External, Session Pooler |
| **Redis** | Coolify managed | For Celery + cache |
| **SSL** | Let's Encrypt | Auto via Traefik |
| **DNS** | Cloudflare | loudrr.com |

### Coolify Services (4 total)

| Service | Image | Watch Path | Port |
|---------|-------|------------|------|
| loudrr-backend | python:3.11-slim | `backend/**` | 8000 |
| loudrr-frontend | node:20 | `frontend/**` | 3000 |
| loudrr-bot | python:3.11-slim | `backend/**` | - |
| redis | redis:7-alpine | - | 6379 |

### Production URLs

| Service | URL |
|---------|-----|
| Frontend | https://app.loudrr.com |
| Backend API | https://api.loudrr.com |
| Django Admin | https://api.loudrr.com/loudrr-admin/ |
| Health Check | https://api.loudrr.com/health/ |

### Deployment Flow

1. Push to `main` on GitHub
2. Coolify webhook triggers rebuild
3. Watch paths determine which services rebuild
4. Zero-downtime with health checks

---

## 17. Quick Reference

### Key Files

| File | Purpose | Atomic |
|------|---------|--------|
| core/services/credits.py | Credit operations | YES |
| core/services/engagements.py | Engagement logic | YES |
| core/services/tweet_score.py | Tier multipliers | - |
| core/services/twitter_verification.py | Reply verification | - |
| miniapp/views.py | All API endpoints | PARTIAL |
| posts/tasks.py | Celery verification | YES |
| bots/telegram/handlers.py | Bot commands | NO |

### Cost Quick Reference

```
1 verification = 15 credits = $0.00015
1,000 verifications = $0.15
100,000 verifications = $15
```

---

## 18. Files to Delete

### Empty/Unused

| File | Reason |
|------|--------|
| `backend/bots/discord/` | Empty, Discord not implemented |
| `backend/miniapp/models.py` | Only stub function |
| `backend/redirects/models.py` | Empty |
| `backend/redirects/admin.py` | Empty |

### Removed Services

| Service | Status |
|---------|--------|
| Kaito.ai | REMOVED (migrations 0023, 0024) |
| EngagementSession model | REMOVED |
| SessionClick model | REMOVED |

---

**End of Documentation**
