# Loudrr - Application Documentation

**Last Updated**: February 1, 2026

---

## Application Overview

**Loudrr** is a Telegram-based mini-app platform for X/Twitter engagement rewards. Users earn "karma" by engaging with posts, then spend karma to promote their own content.

```
User engages with X posts -> Earns karma -> Spends karma to promote own posts
```

**Key Features**: TweetScout scoring, Twitter API verification, queue-based claims, LOUD UGC rewards, whitelist system

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
    |  Database |      |   Cache +   |     |  Workers   |
    |           |      |   Broker    |     |            |
    +-----------+      +-------------+     +------------+
```

### Data Flows

**Waitlist Flow**:
```
Landing Page -> POST /api/miniapp/waitlist/submit/
    -> Backend creates WaitlistEntry (PENDING)
    -> Returns deep link: t.me/loudrr_bot?start=join_TOKEN
    -> User opens Telegram -> Bot links telegram_id
    -> User completes in mini app -> enters X username
    -> Entry becomes SUBMITTED -> Admin approves
    -> Signal fires -> Celery task -> Approval notification sent
    -> User opens mini app -> User account created
```

**Engagement Flow**:
```
User opens mini app -> /session/start/ -> Get 10 posts
    -> User clicks post -> /session/click/ -> Opens X
    -> User engages -> Returns -> /session/queue-claim/
    -> Celery worker verifies async (Twitter API)
    -> Credits awarded based on verification
```

### Architecture Patterns

| Pattern | File | Purpose |
|---------|------|---------|
| **Transactional Outbox** | [core/services/outbox.py](backend/core/services/outbox.py) | Reliable notification delivery |
| **Circuit Breaker** | [core/circuit_breakers.py](backend/core/circuit_breakers.py) | Protect against API failures |
| **Business Invariants** | [core/invariants.py](backend/core/invariants.py) | Runtime business rule checks |
| **Django-Rules** | [core/rules.py](backend/core/rules.py) | Declarative permission predicates |
| **Django-FSM** | [core/models.py](backend/core/models.py) | State machine for WaitlistEntry |
| **Signals + on_commit** | [core/signals.py](backend/core/signals.py) | Safe side effects after DB commit |

---

## Tech Stack

### Backend
- **Django 5.1.4** + Django REST Framework 3.15.2
- **PostgreSQL 16+**, **Redis 7+**, **Celery 5.4.0**
- **python-telegram-bot 21.10**

### Backend Libraries
- **django-fsm** / **django-fsm-log**: State machines with audit
- **rules**: Declarative permissions
- **django-safedelete**: Soft delete
- **django-structlog**: Structured logging
- **pydantic**: Request/response validation
- **pybreaker**: Circuit breakers
- **django-waffle**: Feature flags
- **django-auditlog**: Model change audit

### Frontend
- **Next.js 16** (Landing: port 3001, Mini App: port 3000)
- **Tailwind CSS 4.0**, **shadcn/ui**
- **WebGL + Three.js** for animations

### External APIs
- **Twitter API** (twitterapi.io): Engagement verification
- **TweetScout**: X account scoring
- **Telegram Bot API**: Bot interactions

---

## Database Models

### User ([core/models.py](backend/core/models.py))

```python
class User(AbstractBaseUser, PermissionsMixin):
    # Identifiers
    telegram_id = BigIntegerField(unique)
    telegram_username = CharField(50)
    x_username = CharField(50)
    display_name = CharField(100)

    # Credits (4 decimal places internally)
    credits = DecimalField(max_digits=12, decimal_places=4)
    total_credits_earned = DecimalField
    total_credits_spent = DecimalField
    daily_credits_earned = DecimalField  # Resets daily

    # Engagement
    total_engagements = IntegerField
    current_streak = IntegerField
    longest_streak = IntegerField
    honesty_score = IntegerField(default=50)  # 0-50

    # TweetScout
    tweetscout_score = DecimalField
    tier = property  # Calculated from score

    # Referrals
    referral_code = CharField(16, unique)  # Auto-generated
    referred_by = ForeignKey('self', null)
    total_referrals = PositiveIntegerField

    # Flags
    is_whitelisted = BooleanField
    is_banned = BooleanField
    loud_access = BooleanField

    # Constraints
    CheckConstraint("user_no_self_referral")
    CheckConstraint("user_total_referrals_non_negative")
    CheckConstraint("user_daily_credits_earned_valid_range")  # Max 500
```

### WaitlistEntry ([core/models.py](backend/core/models.py))

```python
class WaitlistEntry(models.Model):
    # Uses FSMField for status
    status = FSMField(choices=[PENDING, SUBMITTED, APPROVED, REJECTED])

    # Identifiers
    join_token = CharField(32, unique)  # For deep linking
    email = EmailField(unique)
    telegram_id = BigIntegerField(unique)
    x_username = CharField(50)

    # X profile data (fetched on submit)
    x_display_name = CharField
    x_followers_count = PositiveIntegerField
    x_avatar_url = URLField
    x_is_verified = BooleanField

    # Referral tracking
    referrer = ForeignKey(User, null)
    referral_code_used = CharField(16)

    # FSM transitions: submit(), approve(), reject()
```

### Post ([posts/models.py](backend/posts/models.py))

```python
class Post(models.Model):
    creator = ForeignKey(User)
    x_link = URLField(unique)
    tweet_id = CharField(30)

    # Escrow (uses FSM)
    escrow_initial = DecimalField
    escrow_remaining = DecimalField
    status = FSMField  # PENDING, ACTIVE, COMPLETED, CANCELLED

    # Cached tweet data
    tweet_text = TextField
    tweet_author_username = CharField
    tweet_media = JSONField

    # Constraints
    CheckConstraint("post_escrow_cannot_exceed_initial")
    CheckConstraint("post_completed_zero_escrow")
```

### Engagement ([posts/models.py](backend/posts/models.py))

```python
class Engagement(models.Model):
    user = ForeignKey(User)
    post = ForeignKey(Post)
    verified = BooleanField(default=False)
    like_verified = BooleanField
    reply_verified = BooleanField
    credit_granted = DecimalField

    class Meta:
        unique_together = [['user', 'post']]
        CheckConstraint("engagement_credit_requires_verification")
```

### Additional Models

- **XProfile**: OneToOne with User for detailed X profile data from TweetScout
- **SiteSetting**: Dynamic settings (key/value with typed values)
- **Transaction**: Credit transfers with idempotency_key
- **Campaign / CampaignEntry**: Raffle/giveaway system
- **VerificationBatch**: Queue-based verification batches
- **LoudProject / LoudSubmission**: UGC contest system
- **LoudLeaderboardEntry**: Denormalized leaderboard
- **OutboxEvent**: Transactional outbox for notifications

---

## API Endpoints

### Authentication

All endpoints (except waitlist) use Telegram Web App authentication:
```
Header: X-Telegram-Init-Data: <HMAC-signed init data>
```

### Miniapp Endpoints (`/api/miniapp/`)

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/health/` | GET | No | Health check |
| `/settings/` | GET | No | App settings |

**Waitlist (No Auth, Rate Limited 5/hour)**:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/waitlist/submit/` | POST | Join waitlist with email |
| `/waitlist/register/` | POST | Register Telegram + deep link |
| `/waitlist/complete/` | GET/POST | Complete with X username |
| `/waitlist/status/` | GET | Check waitlist status |
| `/waitlist/entry/` | GET | Get entry details |

**User (Auth Required)**:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/user/` | GET | Current user info |
| `/user/stats/` | GET | Detailed stats |
| `/user/link-x/` | POST | Link X account |
| `/onboarding/complete/` | POST | Fetch TweetScout + activate |
| `/referral/` | GET | Get referral code and stats |

**Engagement (Auth Required)**:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/session/start/` | POST | Get 10 posts to engage with |
| `/session/click/` | POST | Record click |
| `/session/queue-claim/` | POST | Submit for async verification |
| `/claims/history/` | GET | View claim history |
| `/post/submit/` | POST | Create post with escrow |

### LOUD Endpoints (`/api/loud/`)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/projects/` | GET | List active projects |
| `/submit/` | POST | Submit content |
| `/leaderboard/{slug}/` | GET | Project leaderboard |

---

## Telegram Bot

**File**: [backend/bots/telegram/handlers.py](backend/bots/telegram/handlers.py)

### Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome / deep link handler |
| `/launch` | Get pinnable "Open App" message |
| `/help` | Command list |

### Deep Links

```
t.me/loudrr_bot?start=join_<TOKEN>  # Waitlist flow
t.me/loudrr_bot?start=engage        # Open mini app
```

### Handlers

- **start_handler**: Welcome existing users or direct new users to website
- **handle_waitlist_join**: Process join_TOKEN deep links
- **handle_waitlist_x_username**: Collect X username in chat
- **message_handler**: Route messages (checks if collecting X username)
- **callback_handler**: Handle inline button callbacks

---

## Referral System

**Files**: [core/services/referral.py](backend/core/services/referral.py), [core/rules.py](backend/core/rules.py)

### Flow

```
User A shares: loudrr.com?ref=ABC123
    -> User B enters email
    -> Backend stores referral_code_used on WaitlistEntry
    -> User B completes registration -> entry.referrer = User A
    -> Admin approves User B
    -> Signal fires -> ReferralService.increment_referral_count()
    -> User A's total_referrals incremented atomically
```

### ReferralService Methods

- `validate_referral_code(code)` - Return referrer if valid
- `link_referrer_to_entry(entry, code)` - Link referrer (prevents self-referral)
- `increment_referral_count(entry)` - Atomic increment with F() and select_for_update
- `get_referral_links(user)` - Returns {code, web, telegram} links

### Implementation Status

| Component | Status |
|-----------|--------|
| User.referral_code field | Done |
| User.referred_by FK | Done |
| User.total_referrals count | Done |
| WaitlistEntry.referrer FK | Done |
| Auto-generate codes on save | Done |
| ReferralService | Done |
| Django-rules predicates | Done |
| Signal: increment on approve | Done |
| /api/miniapp/referral/ endpoint | Done |
| **Landing page ?ref= capture** | TODO |
| **WaitlistSubmitView referral_code** | TODO |

---

## Key Patterns

### Signals with transaction.on_commit

```python
@receiver(post_save, sender=WaitlistEntry, dispatch_uid="unique_id")
def send_notification(sender, instance, **kwargs):
    previous_status = getattr(instance, '_previous_status', None)
    if previous_status == WaitlistEntry.Status.APPROVED:
        return  # Already notified

    def notify():
        send_telegram_message.delay(instance.id)
    transaction.on_commit(notify)
```

### Circuit Breaker

```python
@twitter_breaker  # 5 failures -> open for 60s
def verify_engagement(tweet_id, user_id):
    return call_twitter_api(tweet_id, user_id)
```

### Business Invariants

```python
def earn(self, amount):
    check_precondition(amount > 0, "Amount must be positive")
    # ... business logic ...
    check_postcondition(self.user.credits >= 0, "Credits went negative")
```

---

## Environment Variables

### Backend `.env`

```bash
DEBUG=False
SECRET_KEY=<generate-with-secrets.token_urlsafe>
ALLOWED_HOSTS=api.loudrr.com
DATABASE_URL=postgres://user:pass@host:5432/loudrr
REDIS_URL=redis://redis:6379/0
CORS_ALLOWED_ORIGINS=https://loudrr.com,https://app.loudrr.com

TELEGRAM_BOT_TOKEN=<token>
TELEGRAM_BOT_USERNAME=loudrr_bot
MINIAPP_URL=https://app.loudrr.com

TWITTER_API_KEY=<key>
TWEETSCOUT_API_KEY=<key>
```

### Frontend `.env`

```bash
NEXT_PUBLIC_API_URL=https://api.loudrr.com
```

---

## File Structure

```
reply-community-bot/
+-- backend/
|   +-- echo/               # Django project settings
|   +-- core/               # User, WaitlistEntry, Transaction, signals
|   |   +-- services/       # credits.py, referral.py, outbox.py, tweetscout.py
|   |   +-- circuit_breakers.py, invariants.py, rules.py, guards.py
|   +-- miniapp/            # API views and URLs
|   +-- posts/              # Post, Engagement, Campaign models
|   +-- loud/               # LOUD projects and submissions
|   +-- bots/telegram/      # Bot handlers, notifications, image_utils
+-- frontend/               # Next.js mini app (port 3000)
+-- landing/                # Next.js landing page (port 3001)
```

---

## Security

- **Rate limiting**: 5 req/hour on waitlist (WaitlistThrottle)
- **Email validation**: Regex on frontend + backend
- **Secure tokens**: `secrets.token_urlsafe(16)`
- **SQL injection safe**: Django ORM parameterized queries
- **XSS safe**: React auto-escapes
- **CORS**: Configured for production domains
- **Auth**: HMAC-signed Telegram Web App init data
- **Audit logging**: django-auditlog tracks all model changes

---

## Development

### Pre-commit Hooks

```bash
cd backend
pip install pre-commit
pre-commit install
```

Runs: ruff (lint/format), bandit (security), trailing-whitespace, detect-private-key

### Running Services

```bash
# Backend
cd backend && python manage.py runserver

# Celery worker
celery -A echo worker -l info

# Celery beat
celery -A echo beat -l info

# Bot (polling mode)
python manage.py run_telegram_bot
```

---

**Tech Stack**: Django 5.1.4, PostgreSQL 16+, Redis 7+, Celery, Next.js 16, python-telegram-bot 21.10