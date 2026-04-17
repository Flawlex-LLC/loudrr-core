# Loudrr - Application Documentation

**Last Updated**: February 19, 2026

---

## Application Overview

**Loudrr** is a Telegram-based mini-app platform for X/Twitter engagement rewards. Users earn "karma" by engaging with posts, then spend karma to promote their own content.

```
User engages with X posts -> Earns karma -> Spends karma to promote own posts
```

**Key Features**: TweetScout scoring, Twitter API verification, queue-based claims, LOUD UGC rewards, waitlist system, referral system, campaigns/giveaways

---

## Architecture

```
+-------------------+---------------------+----------------------+
|  Landing Page     |   Main Mini App     |   Telegram Bot       |
|  (Next.js 16)     |   (Next.js 16)      |   (python-telegram)  |
|  Port 3001        |   Port 3000         |   Webhook/Polling    |
|  loudrr.com       |   app.loudrr.com    |   t.me/loudrr_bot    |
+-------------------+---------------------+----------------------+
                              |
                +-------------v--------------+
                |   BACKEND API (Django)     |
                |   Django REST Framework    |
                |   Port 8000                |
                +-------------+--------------+
                              |
          +-------------------+--------------------+
          |                   |                    |
    +-----v-----+      +------v------+     +------v-----+
    | PostgreSQL|      |    Redis    |     |  Celery    |
    | (Supabase)|      |   Cache +   |     |  Workers   |
    |           |      |   Broker    |     |            |
    +-----------+      +-------------+     +------------+
```

### Data Flows

**Waitlist Flow**:
```
Landing Page (Telegram CTA button) -> t.me/loudrr_bot
    -> User sends /start -> Bot sends welcome + "Open App" button
    -> User opens mini app -> WaitlistRegistrationScreen
    -> User submits email + X link + optional referral_code
    -> POST /api/miniapp/waitlist/register/
    -> Backend creates WaitlistEntry (SUBMITTED directly, no PENDING)
    -> Auto-generates personal referral_code on save
    -> OutboxEvent created via signal -> Celery sends waitlist card via Telegram
    -> User sees WaitlistPendingScreen (card image + Copy/X Share/TG Share buttons)
    -> Admin approves in Django admin
    -> Signal fires -> OutboxEvent for Telegram notification
    -> Signal fires -> ReferralService.increment_referral_count() (if referrer)
    -> User opens mini app -> User account created
```

**Engagement Flow**:
```
User opens mini app -> /session/start/ -> Get all available posts
    -> User clicks post -> /session/click/ -> Creates Engagement (verified=False)
    -> User engages on X -> Returns to app
    -> After 10+ engagements -> /session/queue-claim/
    -> Creates VerificationBatch (PENDING) -> Celery task queued
    -> Phase 1: VerificationService calls Twitter API (no DB locks)
    -> Phase 2: SettlementService atomic DB writes (no external calls)
    -> Credits awarded with tier multiplier, escrow deducted atomically
    -> User notified via polling /claims/history/
```

**Post Submission Flow**:
```
User submits X link -> /post/submit/
    -> Extract tweet_id from URL
    -> Fetch tweet content via Twitter API (validates ownership by x_user_id)
    -> Deduct karma (configurable min/max range) from user as escrow
    -> Create Post with cached tweet content
    -> Post appears in other users' feeds
    -> Escrow depleted per engagement -> Post auto-completes at zero
    -> Expired posts (POST_EXPIRY_HOURS) refunded via Celery beat
```

### Architecture Patterns

| Pattern | File | Purpose |
|---------|------|---------|
| **Transactional Outbox** | [core/services/outbox.py](backend/core/services/outbox.py) | Reliable notification delivery via OutboxEvent table |
| **Two-Phase Verification** | [miniapp/views.py](backend/miniapp/views.py) | Phase 1: API calls (no locks), Phase 2: atomic DB writes |
| **Circuit Breaker** | [core/circuit_breakers.py](backend/core/circuit_breakers.py) | Protect against Twitter API failures (pybreaker) |
| **Business Invariants** | [core/invariants.py](backend/core/invariants.py) | Runtime business rule checks (preconditions/postconditions) |
| **Django-Rules** | [core/rules.py](backend/core/rules.py) | Declarative permission predicates |
| **Django-FSM** | [core/models.py](backend/core/models.py) | State machines for WaitlistEntry and Post |
| **Signals + on_commit** | [core/signals.py](backend/core/signals.py) | OutboxEvent creation after DB commit |
| **Idempotency Keys** | [core/services/credits.py](backend/core/services/credits.py) | Prevent duplicate transactions via unique constraint |
| **Row-Level Locking** | [core/services/credits.py](backend/core/services/credits.py) | select_for_update() on all credit operations |
| **Dynamic Settings** | [core/services/settings.py](backend/core/services/settings.py) | Django-Constance for runtime config from admin |
| **Soft Delete** | [loud/models.py](backend/loud/models.py) | django-safedelete on LoudSubmission |

---

## Tech Stack

### Backend
- **Django 5.2** + Django REST Framework 3.16
- **PostgreSQL 16+** (hosted on Supabase)
- **Redis 7+** (Celery broker + cache)
- **Celery 5.6** (async task processing)
- **python-telegram-bot 21.11**
- **Python 3.12** (required - 3.14 has compatibility issues with numpy/Pillow)

### Backend Libraries
- **django-fsm**: State machines for WaitlistEntry and Post
- **django-auditlog**: Tracks ALL model changes (admin, API, bot, etc.)
- **rules**: Declarative object permissions
- **django-safedelete**: Soft delete (LOUD submissions)
- **django-structlog**: Structured JSON logging in production
- **django-constance**: Dynamic settings from admin panel
- **django-waffle**: Feature flags
- **pybreaker**: Circuit breakers for external APIs
- **django-jazzmin**: Admin UI theme (dark mode)
- **drf-spectacular**: OpenAPI 3.0 schema generation
- **whitenoise**: Static file serving in production
- **django-cors-headers**: CORS configuration
- **django-log-request-id**: Request tracing
- **Pillow + numpy**: Image generation for Telegram cards

### Frontend (Mini App - port 3000)
- **Next.js 16.1** with React 19, TypeScript 5
- **Tailwind CSS 4** with `@tailwindcss/postcss`
- **Framer Motion**: Animations
- **Radix UI Colors**: Design tokens
- **React Compiler** (babel-plugin-react-compiler)
- Uses Next.js API routes as proxy to Django backend in production

### Frontend (Landing Page - port 3001)
- **Next.js** with React, TypeScript
- **AudioWaveGL**: WebGL audio visualizer component
- API routes for card image generation (approval + waitlist cards)

### External APIs
- **Twitter API** (twitterapi.io): Engagement verification, tweet content fetch, user info
- **TweetScout** (api.tweetscout.io): X account scoring and profile data
- **Telegram Bot API**: Bot interactions and notifications

---

## Database Models

### Core App ([core/models.py](backend/core/models.py))

**User** - Custom user model (`AUTH_USER_MODEL = "core.User"`, table: `users`)
- `id` UUID primary key
- `telegram_id` BigInteger (unique, login via TelegramIDBackend)
- `telegram_username`, `telegram_photo_url`, `display_name`
- `x_username` CharField (not unique - duplicates exist in production)
- `email` EmailField (unique, nullable - for superuser login)
- **Credits**: `credits`, `total_credits_earned`, `total_credits_spent` (Decimal 12,4)
- **Daily limits**: `daily_credits_earned` (Decimal, max 500 hard cap), `daily_earned_reset_at`
- **Engagement**: `total_engagements`, `total_posts`, `current_streak`, `longest_streak`, `last_engagement_date`
- **Honesty**: `honesty_score` (0-50, drops on failed verification)
- **TweetScout**: `tweetscout_score` (Float), `tier` (computed property), `tier_multiplier` (computed property)
- **Sponsored XP**: `sponsored_xp`, `total_sponsored_xp_earned`, `sponsored_engagements`
- **Referrals**: `referral_code` (auto-generated 8-char), `referred_by` (self FK), `total_referrals`
- **Flags**: `is_whitelisted`, `is_banned`, `ban_reason`, `loud_access`, `has_claimed_bonus`
- **Constraints**: credits >= 0, earned >= spent, no self-referral, honesty 0-50, daily earned max 500, not banned AND whitelisted

**Transaction** (table: `transactions`) - Audit trail for all credit changes
- Types: EARNED, SPENT, PURCHASED, SPONSORED_REWARD, REFUND, PENALTY, ADMIN_GRANT, ADMIN_REVOKE
- `idempotency_key` unique constraint per (user, type, key) - prevents duplicate transactions
- `amount` (positive for gains, negative for losses), `balance_after`

**WaitlistEntry** (table: `waitlist_entries`) - FSM-managed waitlist
- Status: SUBMITTED -> APPROVED/REJECTED (django-fsm transitions, no PENDING state)
- `email` (unique), `telegram_id` (unique), `x_link` (X profile URL), `x_username`
- X profile data: `x_display_name`, `x_followers_count`, `x_avatar_url`, `x_is_verified`
- Referral tracking: `referrer` FK, `referral_code_used`, `referral_code` (auto-generated 8-char uppercase, unique)
- Approval: `approved_at`, `approved_by`, `created_user` (OneToOne to User)

**XProfile** (table: `x_profiles`) - OneToOne with User, all TweetScout data
- `x_user_id`, `username`, `display_name`, `bio`
- `followers_count`, `following_count`, `tweets_count`, `score`
- `avatar_url`, `banner_url`, `is_verified`, `can_dm`, `x_created_at`
- `raw_tweetscout_data` JSONField (complete API response)

**OutboxEvent** (table: `outbox_events`) - Transactional outbox pattern
- Event types: TELEGRAM_NOTIFY, WAITLIST_APPROVED, WAITLIST_SUBMITTED, CREDITS_EARNED, POST_COMPLETED, CAMPAIGN_WINNER, TWEETSCOUT_FETCH
- Status: PENDING -> PROCESSING -> SENT/FAILED
- `payload` JSONField, `retry_count`, `max_retries` (default 3)

**Other**: `AuditLog`, `XPTransaction`, `SiteSetting`, `FeatureInterest`

### Posts App ([posts/models.py](backend/posts/models.py))

**Post** (table: `posts`) - User-submitted X posts for engagement
- `user` FK, `x_link`, `tweet_id`
- Status: ACTIVE -> COMPLETED/CANCELLED (FSM transitions)
- `escrow` / `initial_escrow` (Decimal 12,4) - credits locked for distribution
- Cached tweet content: `tweet_text`, `tweet_author_name`, `tweet_author_username`, `tweet_author_avatar`, `tweet_media` (JSON), `tweet_created_at`
- `is_sponsored` flag, `redirect_token` (unique, for tracking URLs)
- `platform` (TELEGRAM or WEB)
- Constraints: escrow >= 0, escrow <= initial, completed/cancelled must have zero escrow

**Engagement** (table: `engagements`) - User engagement with a post
- Unique constraint on (user, post) - one engagement per user per post
- `verified` / `credit_granted` booleans, `like_verified`, `reply_verified`
- `verification_data` JSONField
- Constraint: can't grant credit without verification

**SponsoredPost** (table: `sponsored_posts`) - Sponsored post configuration
- OneToOne with Post, `sponsor_name`, `credit_reward`, `total_budget`, `remaining_budget`

**Campaign** (table: `campaigns`) - Raffle/giveaway system
- Types: RAFFLE, SCORE_BASED; Status: DRAFT, ACTIVE, COMPLETED, CANCELLED
- Winner methods: RANDOM, WEIGHTED_XP, WEIGHTED_SCORE, FIRST_COME
- Eligibility criteria: min XP, engagements, posts, streak, TweetScout score, X linked

**CampaignEntry** (table: `campaign_entries`) - User entry in campaign
- `eligibility_snapshot` JSONField, `is_winner`, `prize_claimed`, `payout_amount`

**VerificationBatch** (table: `verification_batches`) - Async verification queue
- `engagement_ids` JSONField, Status: PENDING -> PROCESSING -> COMPLETED/FAILED
- Results: `passed`, `failed`, `credits_awarded`, `message`

### Loud App ([loud/models.py](backend/loud/models.py))

**LoudProject** (table: `loud_projects`) - Admin-created UGC campaigns
- `name`, `slug` (unique), `description`, `logo_url`
- `starts_at`, `ends_at`, `min_tweetscout_score`, `max_submissions_per_user`
- `reward_pool` (display text), `is_active`

**LoudSubmission** (table: `loud_submissions`) - SafeDeleteModel (soft delete)
- `user`, `project`, `x_link`, `tweet_id` (globally unique)
- `points_awarded`, `tweetscout_score_at_submission` (snapshot for audit)

**LoudLeaderboardEntry** (table: `loud_leaderboard`) - Denormalized leaderboard
- Unique (project, user), `total_points`, `submission_count`
- Updated atomically via F() expressions

**LoudPointAdjustment** (table: `loud_point_adjustments`) - Admin point changes audit

---

## Services Layer

### [core/services/credits.py](backend/core/services/credits.py) - CreditService
- `earn()`: Grant credits with daily cap, idempotency, row locking
- `spend()`: Deduct credits with balance check, idempotency
- `refund()`: Return credits (e.g., cancelled post)
- `apply_penalty()`: Deduct for failed audit
- `admin_grant()`: Admin grants (bypasses daily cap)
- All operations are `@transaction.atomic` with `select_for_update()`

### [core/services/settlement.py](backend/core/services/settlement.py) - SettlementService
- Phase 2 of verification: atomic DB writes (no external calls)
- Handles escrow deduction + credit award per engagement with savepoints

### [core/services/verification.py](backend/core/services/verification.py) - VerificationService
- Phase 1 of verification: Twitter API calls (no DB locks)
- Batch verification of engagements

### [core/services/twitter_verification.py](backend/core/services/twitter_verification.py)
- `verify_reply()`: Check if user replied to tweet via Twitter API
- `get_tweet_content()`: Fetch tweet data for feed display
- `get_user_info()`: Fetch X profile for waitlist
- `extract_tweet_id()`: Parse tweet ID from URL

### [core/services/tweetscout.py](backend/core/services/tweetscout.py)
- `get_user_data()`: Fetch score + profile from TweetScout API
- Creates/updates XProfile with all data

### [core/services/tweet_score.py](backend/core/services/tweet_score.py)
- `get_tweet_score_tier()`: Maps score to tier name (anon/normie/degen/based/legend/og/goat)
- `get_tweet_score_multiplier()`: Maps score to karma multiplier (1.0x - 1.35x)
- `calculate_engagement_karma()`: Applies tier multiplier to base credit

### [core/services/referral.py](backend/core/services/referral.py) - ReferralService
- `validate_referral_code()`, `link_referrer_to_entry()`
- `increment_referral_count()`: Atomic F() increment with select_for_update
- `get_referral_stats()`: Returns code, links, counts

### [core/services/outbox.py](backend/core/services/outbox.py) - OutboxService
- `queue_waitlist_approved()`, `queue_waitlist_submitted()`
- `process_event()`: Routes events to handlers (Telegram notifications)

### [core/services/posts.py](backend/core/services/posts.py)
- `get_feed_posts()`: Returns active posts for user (excludes own posts, already engaged)
- `get_feed_count()`: Lightweight count for UI

### [core/services/xp.py](backend/core/services/xp.py) - XPService
- Sponsored XP management (non-spendable reputation score)

### [core/services/gamification.py](backend/core/services/gamification.py)
- Streak tracking and bonus calculation

### [core/services/campaigns.py](backend/core/services/campaigns.py)
- Campaign eligibility checking and winner selection

### [loud/services.py](backend/loud/services.py) - LoudService
- `get_live_projects()`, `can_submit()`, `submit()`
- `get_leaderboard()`, `get_user_entry()`, `get_project_stats()`
- `calculate_loud_points()`: TweetScout score / LOUD_POINTS_DIVISOR

---

## API Endpoints

### Authentication

All endpoints (except waitlist/health/settings) use Telegram Web App authentication:
```
Header: X-Telegram-Init-Data: <HMAC-signed init data>
```
- HMAC validated against bot token, auth_date expires after 24 hours
- In DEBUG mode: `?telegram_id=<id>` query param allowed for testing
- Load test mode: `X-Load-Test-Auth` + `X-Load-Test-User` headers (NEVER in production)

### Root URLs ([echo/urls.py](backend/echo/urls.py))

| Path | Description |
|------|-------------|
| `/health/` | Docker/K8s health check (checks DB connection) |
| `/admin/` | Django admin (default site) |
| `/api/schema/` | OpenAPI 3.0 schema (drf-spectacular) |
| `/api/docs/` | Swagger UI |
| `/api/redoc/` | ReDoc |
| `/api/miniapp/` | Mini app API |
| `/api/loud/` | LOUD UGC API |
| `/api/posts/` | Posts API |
| `/api/` | Core API |
| `/r/` | Redirect URLs (engagement tracking) |

### Miniapp Endpoints (`/api/miniapp/`) - [miniapp/urls.py](backend/miniapp/urls.py)

**Public (No Auth)**:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health/` | GET | Health check |
| `/settings/` | GET | App settings (post_cost_min, post_cost_max) |

**Waitlist (Rate Limited 5/hour per IP)**:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/waitlist/register/` | POST | Register from mini app (email + X link + referral_code). Returns referral_code. |
| `/waitlist/status/` | GET | Check status (approved/waitlisted/not_registered). Returns referral_code if waitlisted. |

**User (Telegram Auth)**:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/user/` | GET | Current user info (credits, tier, stats, feature flags) |
| `/user/stats/` | GET | Detailed stats (posts, engagements, recent activity) |
| `/user/link-x/` | POST | Link X account (fetches TweetScout, creates XProfile) |
| `/onboarding/complete/` | POST | Fetch TweetScout + activate (called once after approval) |
| `/referral/` | GET | Get referral code, stats, and shareable links |
| `/feature-interest/` | GET/POST | Register/check interest in upcoming features |

**Engagement (Telegram Auth)**:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/session/start/` | POST | Get all posts (pending first, then fresh) |
| `/session/click/` | POST | Record click, creates Engagement (verified=False) |
| `/session/verify-return/` | POST | Optional: confirm user returned from X |
| `/session/complete/` | POST | Synchronous verification + settlement |
| `/session/queue-claim/` | POST | Async verification (preferred - queues Celery task) |
| `/claims/history/` | GET | Verification batch history (polling for results) |
| `/post/submit/` | POST | Create post with escrow (validates tweet ownership) |

### LOUD Endpoints (`/api/loud/`) - [loud/urls.py](backend/loud/urls.py)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/projects/` | GET | List active projects with eligibility |
| `/submit/` | POST | Submit content (rate limited 10/min) |
| `/leaderboard/{slug}/` | GET | Project leaderboard (top 50) |

---

## Celery Tasks

### Core Tasks ([core/tasks.py](backend/core/tasks.py))

| Task | Schedule | Description |
|------|----------|-------------|
| `fetch_tweetscout_for_user` | On demand | Fetch TweetScout data for newly approved user |
| `process_pending_outbox_events` | Periodic (Beat) | Process OutboxEvents in batches of 50 |
| `process_single_outbox_event` | On demand | Immediate event processing |
| `cleanup_old_outbox_events` | Periodic (Beat) | Delete SENT events older than 30 days |
| `reset_daily_credits` | Daily midnight | Reset daily_credits_earned for all users |
| `retry_failed_outbox_events` | Periodic (Beat) | Reset failed events for retry |

### Posts Tasks ([posts/tasks.py](backend/posts/tasks.py))

| Task | Schedule | Description |
|------|----------|-------------|
| `process_verification_batch` | On demand | Async engagement verification + settlement |
| `expire_old_posts` | Periodic (Beat) | Expire old posts, refund escrow (batched, self-scheduling) |

---

## Telegram Bot

**Files**: [bots/telegram/handlers.py](backend/bots/telegram/handlers.py), [bots/telegram/bot.py](backend/bots/telegram/bot.py)

### Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome / deep link handler |
| `/launch` | Get pinnable "Open App" message |
| `/help` | Command list |

### Deep Links

```
t.me/loudrr_bot?start=ref_<CODE>    # Referral flow (stores code, opens mini app)
t.me/loudrr_bot?start=engage        # Open mini app
```

### Management Command

```bash
python manage.py run_telegram_bot  # Start bot in polling mode
```

### Other Management Commands

| Command | Description |
|---------|-------------|
| `run_telegram_bot` | Start Telegram bot |
| `seed_posts` | Seed test posts |
| `create_load_test_users` | Create users for load testing |
| `requeue_stuck_batches` | Fix stuck verification batches |
| `run_e2e_test` | End-to-end test |
| `run_integration_test` | Integration test |
| `full_system_test` | Full system test |
| `test_queue_system` | Test queue system |

---

## Django Admin

**URL**: `/admin/` (uses Jazzmin dark theme)

### Custom Admin Classes

- **UserAdmin**: Ban/whitelist actions, credit display, TweetScout data
- **WaitlistEntryAdmin**: Approve/reject actions, status filters, X profile preview
- **PostAdmin**: Status management, escrow tracking
- **EngagementAdmin**: Verification status
- **CampaignAdmin**: Campaign management with entry counts
- **LoudProjectAdmin**: Project CRUD with timing
- **LoudSubmissionAdmin**: Submission review, soft delete
- **LoudLeaderboardEntryAdmin**: Point adjustments

### Audit Trails

1. **Django LogEntry** (`/admin/`): Admin panel actions only (add/change/delete via admin UI)
2. **django-auditlog** (`/admin/`): ALL model changes from any source (admin, API, bot, signals)

---

## Dynamic Settings (Django-Constance)

Configurable via Django admin at `/admin/constance/config/`:

| Setting | Default | Description |
|---------|---------|-------------|
| `POST_COST` | 80 | Karma cost to create a post |
| `CREDIT_PER_ENGAGEMENT` | 1 | Base credit per engagement |
| `DAILY_EARN_CAP` | 160 | Max karma earnable per day |
| `MIN_SESSION_DURATION_SECONDS` | 30 | Anti-gaming: minimum time before claiming |
| `VERIFICATION_BATCH_SIZE` | 10 | Engagements per verification batch |
| `AUDIT_PROBABILITY` | 0.05 | Probability of random audit |
| `LOUD_DAILY_SUBMISSION_LIMIT` | 6 | Max LOUD submissions per day |
| `MAINTENANCE_MODE` | False | Enable maintenance mode |
| `REGISTRATION_OPEN` | True | Allow new registrations |
| `PRODUCTION_LOCK` | False | Block dangerous admin actions |

### Tier System (TweetScout score thresholds)

| Tier | Min Score | Multiplier |
|------|-----------|------------|
| Anon | 0 | 1.00x |
| Normie | 100 | 1.10x |
| Degen | 200 | 1.15x |
| Based | 400 | 1.20x |
| Legend | 600 | 1.25x |
| OG | 800 | 1.30x |
| GOAT | 1000 | 1.35x |

---

## Frontend Architecture

### Mini App ([frontend/](frontend/))

**Single-page app** with multiple sections rendered in one `page.tsx` (~72K tokens).

**Key Files**:
- [app/page.tsx](frontend/app/page.tsx) - Main app (all screens: feed, engage, post, profile, LOUD, waitlist, onboarding)
- [lib/api.ts](frontend/lib/api.ts) - API client with types (uses Telegram init data auth)
- [lib/telegram.ts](frontend/lib/telegram.ts) - Telegram Web App SDK helpers
- [app/api/miniapp/[...path]/route.ts](frontend/app/api/miniapp/[...path]/route.ts) - API proxy to Django backend
- [app/api/loud/[...path]/route.ts](frontend/app/api/loud/[...path]/route.ts) - LOUD API proxy
- [components/ui/](frontend/components/ui/) - Animated gradient, border beam, shimmer button

**API Proxying**: In production, frontend proxies API calls through Next.js API routes to avoid CORS issues. In dev, calls go directly to `localhost:8000`.

### Landing Page ([landing/](landing/))

- [app/page.tsx](landing/app/page.tsx) - Landing page with "Join on Telegram" CTA button
- [app/waitlist/[username]/page.tsx](landing/app/waitlist/[username]/page.tsx) - Waitlist share page with OG meta tags for X card previews
- [app/components/AudioWaveGL.tsx](landing/app/components/AudioWaveGL.tsx) - WebGL audio visualizer
- [app/api/cards/approval/route.tsx](landing/app/api/cards/approval/route.tsx) - Approval card image generation (@vercel/og, 1012x638)
- [app/api/cards/waitlist/route.tsx](landing/app/api/cards/waitlist/route.tsx) - Waitlist card image generation (@vercel/og, 1012x638)

---

## Referral System

**Files**: [core/services/referral.py](backend/core/services/referral.py), [core/rules.py](backend/core/rules.py)

### Flow

```
User A shares: loudrr.com/waitlist/<username> or t.me/loudrr_bot?start=ref_<CODE>
    -> User B opens Telegram -> Bot stores referral code
    -> User B registers in mini app (email + X link + referral_code)
    -> Backend validates referral_code against User AND WaitlistEntry tables
    -> Backend stores referral_code_used on WaitlistEntry, links entry.referrer (if User)
    -> Admin approves User B
    -> Signal fires -> ReferralService.increment_referral_count()
    -> User A's total_referrals incremented atomically (F() + select_for_update)
```

### Implementation Status

| Component | Status |
|-----------|--------|
| User.referral_code field | Done |
| User.referred_by FK | Done |
| User.total_referrals count | Done |
| WaitlistEntry.referrer FK | Done |
| WaitlistEntry.referral_code field | Done |
| Auto-generate codes on save (User + WaitlistEntry) | Done |
| Dual referral lookup (User + WaitlistEntry) | Done |
| ReferralService | Done |
| Django-rules predicates | Done |
| Signal: increment on approve | Done |
| /api/miniapp/referral/ endpoint | Done |
| WaitlistRegisterView referral_code | Done |
| Waitlist share page (landing/app/waitlist/[username]/) | Done |
| Waitlist OG card generation (landing/app/api/cards/waitlist/) | Done |
| WaitlistPendingScreen share buttons (Copy, X Post, TG Share) | Done |
| Bot ref_ deep link handling | Done |

---

## Environment Variables

### Backend `.env` (read from project root)

```bash
# Django
SECRET_KEY=<generate-with-secrets.token_urlsafe>
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database (Supabase)
DATABASE_URL=postgresql://user:pass@host:5432/dbname

# Redis (Celery broker + cache)
REDIS_URL=redis://localhost:6379/0

# CORS
CORS_ALLOWED_ORIGINS=http://localhost:3000,https://app.loudrr.com

# Mini App URL
MINIAPP_URL=https://app.loudrr.com

# Telegram
TELEGRAM_BOT_TOKEN=<token>
TELEGRAM_BOT_USERNAME=loudrr_bot

# External APIs
TWITTER_API_KEY=<twitterapi.io key>
TWEETSCOUT_API_KEY=<tweetscout key>

# Encryption
ENCRYPTION_KEY=<32-byte-key>

# Load testing (NEVER enable in production)
LOAD_TEST_MODE=false
LOAD_TEST_SECRET=
```

### Frontend `.env`

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000/api/miniapp
NEXT_PUBLIC_DEBUG_TELEGRAM_ID=6451704338  # For local testing outside Telegram
```

---

## File Structure

```
loudrr/
+-- backend/
|   +-- echo/                    # Django project settings
|   |   +-- settings.py          # All config (INSTALLED_APPS, CONSTANCE, JAZZMIN, etc.)
|   |   +-- urls.py              # Root URL config + admin registrations
|   |   +-- admin_site.py        # Custom admin site
|   |   +-- celery.py            # Celery app config
|   +-- core/                    # Core app (users, transactions, waitlist)
|   |   +-- models.py            # User, Transaction, WaitlistEntry, XProfile, OutboxEvent, etc.
|   |   +-- admin.py             # Admin classes for core models
|   |   +-- signals.py           # Waitlist approval/submission signals (OutboxEvent pattern)
|   |   +-- tasks.py             # Celery tasks (outbox processing, daily reset, TweetScout fetch)
|   |   +-- rules.py             # Django-rules permission predicates
|   |   +-- guards.py            # Guard functions for business rules
|   |   +-- invariants.py        # Business invariant checks
|   |   +-- circuit_breakers.py  # pybreaker circuit breakers
|   |   +-- backends.py          # TelegramIDBackend (auth backend)
|   |   +-- services/
|   |   |   +-- credits.py       # CreditService (earn, spend, refund, penalty)
|   |   |   +-- settlement.py    # SettlementService (Phase 2: atomic DB writes)
|   |   |   +-- verification.py  # VerificationService (Phase 1: API calls)
|   |   |   +-- twitter_verification.py  # Twitter API wrapper
|   |   |   +-- tweetscout.py    # TweetScout API wrapper
|   |   |   +-- tweet_score.py   # Tier calculation and karma multipliers
|   |   |   +-- referral.py      # ReferralService
|   |   |   +-- outbox.py        # OutboxService (event routing)
|   |   |   +-- posts.py         # Feed post queries
|   |   |   +-- settings.py      # get_setting() helper (SiteSetting + Constance)
|   |   |   +-- xp.py            # XPService (sponsored XP)
|   |   |   +-- gamification.py  # Streaks and bonuses
|   |   |   +-- campaigns.py     # Campaign eligibility
|   |   |   +-- engagements.py   # Engagement helpers (encrypt_user_id)
|   |   |   +-- x_url_resolver.py # X URL parsing
|   |   +-- management/commands/  # seed_posts, run_e2e_test, etc.
|   |   +-- tests/               # Unit + integration + property-based tests
|   |   +-- api/                 # Core API endpoints
|   +-- miniapp/                 # Mini app API views
|   |   +-- views.py             # All endpoint views (MiniAppAuthMixin)
|   |   +-- urls.py              # URL routing
|   |   +-- schema.py            # DRF serializers for OpenAPI docs
|   +-- posts/                   # Post, Engagement, Campaign, VerificationBatch
|   |   +-- models.py
|   |   +-- admin.py
|   |   +-- tasks.py             # process_verification_batch, expire_old_posts
|   |   +-- api/                 # Posts API endpoints
|   +-- loud/                    # LOUD UGC feature
|   |   +-- models.py            # LoudProject, LoudSubmission, LoudLeaderboard
|   |   +-- views.py             # Projects, Submit, Leaderboard views
|   |   +-- services.py          # LoudService
|   |   +-- admin.py
|   |   +-- urls.py
|   +-- redirects/               # Engagement redirect tracking (/r/<token>/)
|   +-- bots/                    # Telegram bot
|   |   +-- telegram/
|   |   |   +-- bot.py           # Bot setup and configuration
|   |   |   +-- handlers.py      # Command and message handlers
|   |   |   +-- notifications.py # Notification sending (approval + waitlist card)
|   |   |   +-- image_utils.py   # Card image generation
|   |   +-- management/commands/
|   |       +-- run_telegram_bot.py  # Management command to start bot
|   +-- static/                  # Static files (Jazzmin theme CSS, logo)
+-- frontend/                    # Next.js mini app (port 3000)
|   +-- app/page.tsx             # Main SPA (all screens)
|   +-- app/api/                 # API proxy routes
|   +-- lib/api.ts               # API client with types
|   +-- lib/telegram.ts          # Telegram SDK helpers
|   +-- components/ui/           # UI components
+-- landing/                     # Next.js landing page (port 3001)
|   +-- app/page.tsx             # Landing page (Telegram CTA button)
|   +-- app/waitlist/[username]/page.tsx  # Waitlist share page with OG meta tags
|   +-- app/components/          # AudioWaveGL
|   +-- app/api/cards/           # Card image generation endpoints
|   |   +-- approval/route.tsx   # Approval card (@vercel/og)
|   |   +-- waitlist/route.tsx   # Waitlist card (@vercel/og)
+-- docker-compose.yaml          # Docker compose config
+-- Dockerfile                   # Docker build config
+-- dev.ps1                      # PowerShell dev startup (all 7 services)
+-- start-dev.bat                # Batch dev startup (3 services)
+-- deploy_coolify.py            # Coolify deployment script
```

---

## Security

- **Rate limiting**: 5 req/hour on waitlist (WaitlistThrottle), 10/min on LOUD submit
- **Auth**: HMAC-signed Telegram Web App init data with 24-hour expiry
- **Email validation**: Django EmailValidator (RFC 5322) + regex on frontend
- **Secure tokens**: `secrets.token_urlsafe(16)` for redirect tokens; `secrets.token_urlsafe(6)` for referral codes
- **SQL injection safe**: Django ORM parameterized queries
- **XSS safe**: React auto-escapes, no dangerouslySetInnerHTML
- **CORS**: Configured for production domains + Cloudflare tunnel regex
- **Audit logging**: django-auditlog tracks ALL model changes from ANY source
- **Idempotency**: Transaction idempotency keys prevent duplicate credit operations
- **Row-level locking**: select_for_update() on all credit operations prevents race conditions
- **Tweet ownership**: Validates tweet author ID matches user's stored x_user_id
- **Encryption**: User IDs encrypted in redirect URLs (ENCRYPTION_KEY)
- **Anti-gaming**: Minimum session duration, honesty score tracking
- **DB constraints**: CheckConstraints enforce business rules at database level

---

## Development

### Prerequisites

- **Python 3.12** (3.14 has compatibility issues with numpy/Pillow)
- **Node.js 20+**
- **Redis** (for Celery - `docker run --rm -p 6379:6379 redis:7`)
- **PostgreSQL** or Supabase connection

### Setup

```bash
# Backend
py -3.12 -m venv .venv
.venv\Scripts\activate  # Windows
pip install -r backend/requirements.txt
cd backend && python manage.py migrate

# Frontend
cd frontend && npm install

# Landing
cd landing && npm install
```

### Running Services

```bash
# Backend API (port 8000)
cd backend && python manage.py runserver 8000

# Celery worker
cd backend && celery -A echo worker -l info -P solo

# Celery beat (periodic tasks)
cd backend && celery -A echo beat -l info

# Telegram bot (polling mode)
cd backend && python manage.py run_telegram_bot

# Frontend mini app (port 3000)
cd frontend && npm run dev

# Landing page (port 3001)
cd landing && npm run dev

# Redis
docker run --rm -p 6379:6379 redis:7
```

Or use `.\dev.ps1` (PowerShell) to start all 7 services at once.

### Pre-commit Hooks

```bash
cd backend
pip install pre-commit
pre-commit install
```

Runs: ruff (lint/format), bandit (security), trailing-whitespace, detect-private-key

### API Documentation

- Swagger UI: http://localhost:8000/api/docs/
- ReDoc: http://localhost:8000/api/redoc/
- OpenAPI Schema: http://localhost:8000/api/schema/

---

## Deployment

- **Docker**: Dockerfile at root, docker-compose.yaml for multi-service setup
- **Coolify**: `deploy_coolify.py` for automated deployment to Coolify platform
- **Static files**: WhiteNoise serves static files in production
- **Frontend**: Next.js standalone output mode for Docker
