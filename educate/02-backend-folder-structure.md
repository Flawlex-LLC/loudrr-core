# Backend Masterclass — Part 1: The Folder Map

> **Goal:** When you finish reading this, you'll know exactly what every folder and file in `backend/` does, why it exists, and where to look when you want to change something.
>
> **Skip if:** you only want to vibe-code frontend. This doc is only useful if you're going deep on backend.
>
> **Time:** ~45 min if you also open each file mentioned and skim it.

---

## How to read this doc

This isn't a tutorial — it's a **map**. Open `backend/` in your editor (VS Code) and follow along. For each folder I describe, click into it and look at the actual files. Reading code beats reading about code.

Use this doc as a "you are here" guide. Whenever you don't know where something lives, come back here and find the section.

---

## Part 1 — The 30,000-foot view (what is a Django backend?)

A **backend** is a program that:
1. Listens for HTTP requests (someone visiting a URL)
2. Reads/writes data in a database
3. Sometimes calls external services (Twitter, Telegram, etc.)
4. Sends back a response (usually JSON for an API, HTML for a website)

**Django** is a Python framework that gives you a structure for doing this. Instead of writing everything from scratch, Django provides:
- A way to define your database tables in Python (called "models")
- A way to map URLs to functions (called "URL routing")
- A way to write functions that handle requests (called "views")
- An admin interface (auto-generated from your models)
- A bunch of patterns and utilities for common tasks (auth, sessions, migrations, etc.)

Loudrr's backend is a Django project. Inside that project, we have multiple **apps** (small modules), each focused on one piece of functionality.

**Key insight**: a Django *project* is the umbrella; *apps* are the modules under it. One project, many apps. Loudrr has these apps: `core`, `posts`, `miniapp`, `loud`, `redirects`, `bots`.

---

## Part 2 — Top-level layout of `backend/`

When you open `backend/` you see this:

```
backend/
├── manage.py                  ← Django's command runner — you'll use this constantly
├── requirements.txt           ← Python packages to install (pip reads this)
├── pyproject.toml             ← Python project metadata + tool config (ruff, etc.)
├── mypy.ini                   ← Type checker config (mypy)
├── Dockerfile                 ← Recipe for building the Django container in production
├── Dockerfile.qcluster        ← Recipe for building the background worker container
├── Dockerfile.bot             ← (legacy) recipe for the polling bot container
├── docker-entrypoint.sh       ← Shell script that runs when a container starts
├── locustfile.py              ← Load testing script (Locust)
├── celerybeat-schedule.dat    ← (legacy from Celery, can be deleted — we use django-q2 now)
├── celerybeat-schedule.dir    ← (same — legacy)
├── static/                    ← CSS, images, etc. served by the web server
│
├── echo/                      ← The Django PROJECT folder (settings, root URLs)
│
├── core/                      ← App: users, credits, waitlist, audit, X verification
├── miniapp/                   ← App: API endpoints for the Telegram mini-app
├── posts/                     ← App: posts, engagements, escrow, campaigns
├── loud/                      ← App: LOUD UGC submissions + leaderboard
├── redirects/                 ← App: short-URL tracking for engagement clicks
└── bots/                      ← App: Telegram bot handlers + notifications
```

Each `*/` folder is either the project (`echo/`) or a Django app (`core/`, `posts/`, etc.).

### Why the project is called `echo/` and not `loudrr/`

Historical — the project started as "Echo" before being renamed to Loudrr. The folder name stuck because renaming a Django project's main folder is annoying (you'd have to update every `from echo.something import ...`). It works fine, just remember `echo/` = "the project itself".

---

## Part 3 — `manage.py` (your command remote)

This file is tiny. You don't edit it. But you USE it every day.

```python
#!/usr/bin/env python
import os
import sys

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "echo.settings")
    from django.core.management import execute_from_command_line
    execute_from_command_line(sys.argv)
```

It tells Django: "Hey, our settings file is at `echo/settings.py`, then run whatever command the user typed."

### Commands you'll use constantly

```bash
python manage.py runserver 8000        # Start the dev server on port 8000
python manage.py migrate               # Apply pending migrations to the DB
python manage.py makemigrations        # Generate a migration after changing models
python manage.py shell                 # Open a Python shell with Django loaded
python manage.py createsuperuser       # Create an admin user
python manage.py qcluster              # Start the background worker (django-q2)
python manage.py run_telegram_bot      # Start the bot in polling mode (dev only)
python manage.py check --deploy        # Check production-readiness
python manage.py test                  # Run tests
```

Anything in `*/management/commands/*.py` becomes a `manage.py` subcommand. We have a bunch of custom ones (`seed_posts`, `run_e2e_test`, etc.) — more on those later.

---

## Part 4 — `echo/` (the Django project core)

This folder contains the project-wide configuration. Only 5 files matter:

```
echo/
├── __init__.py        ← Empty file that says "this folder is a Python module"
├── settings.py        ← THE config file (1000+ lines, controls everything)
├── urls.py            ← Root URL routing (the dispatcher)
├── admin_site.py      ← Custom admin site config (theming, branding)
└── wsgi.py            ← Hook for production web servers (gunicorn reads this)
```

### `__init__.py` — what is this?

In Python, any folder containing an `__init__.py` becomes an importable module. The file can be empty (and ours is). It just signals "this folder is a Python package".

You'll see `__init__.py` in every folder. It's a Python convention.

### `settings.py` — the master config

This file is where everything in your Django project gets configured: database URL, allowed hosts, installed apps, middleware, secret keys, third-party library configs, custom Loudrr config, etc.

Open it. Even if you don't understand every line, scroll through it once. You'll see sections like:
- `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS` — basic Django setup
- `INSTALLED_APPS` — list of every Django app and third-party library that's "turned on"
- `MIDDLEWARE` — code that runs on every request (auth check, CSRF check, etc.)
- `DATABASES` — DB connection
- `REST_FRAMEWORK` — config for Django REST Framework (DRF)
- `CONSTANCE_CONFIG` — config for django-constance (runtime settings)
- `Q_CLUSTER` — config for django-q2 (the worker)
- `JAZZMIN_SETTINGS` — admin theme config
- `LOGGING` — how logs are formatted and where they go
- `CORS_*`, `CSRF_*`, `SESSION_*` — web security settings
- A bunch of Loudrr-specific values at the bottom (TELEGRAM_BOT_TOKEN, MINIAPP_URL, etc.)

**You'll come back to `settings.py` constantly.** It's the source of truth for "is this feature on?".

### `urls.py` — the URL router

When a request comes in, Django needs to know which function should handle it. That's what this file does.

Open it. You'll see something like:

```python
urlpatterns = [
    path("health/", health_check, name="health_check"),
    path("admin/", admin.site.urls),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/", include("core.api.urls")),
    path("api/posts/", include("posts.api.urls")),
    path("api/miniapp/", include("miniapp.urls")),
    path("api/loud/", include("loud.urls")),
    path("api/telegram/webhook/", telegram_webhook, name="telegram_webhook"),
    path("api/auth/x/callback/", x_oauth_callback, name="x_oauth_callback"),
    path("r/", include("redirects.urls")),
]
```

Reading this:
- `path("admin/", admin.site.urls)` means: any URL starting with `/admin/` is handled by Django's built-in admin
- `path("api/miniapp/", include("miniapp.urls"))` means: anything starting with `/api/miniapp/` — go look at `miniapp/urls.py` for the rest of the routing

`include()` lets you delegate to another URLs file. That's why each app has its own `urls.py` — keeps things organized.

### `admin_site.py` — admin customization

We have a custom admin site (instead of using the default `django.contrib.admin.site`). This file defines the branding, login template, etc.

You won't touch it often — it's set-and-forget config.

### `wsgi.py` — production hook

In production, a "WSGI server" (gunicorn, uwsgi) reads this file to know how to start your Django app. In development, you don't care about it. Don't edit it.

---

## Part 5 — Django apps (the meat)

Now we get to the actual functionality. Each Django app is a self-contained module that handles one area. Loudrr has 6 apps.

### What's IN every Django app?

Almost every app has these files (we'll go through what each does):

| File | What it does |
|------|--------------|
| `__init__.py` | Marks folder as a Python module |
| `apps.py` | App config (signals registration, app name) |
| `models.py` | Database tables defined as Python classes |
| `views.py` | Functions that handle HTTP requests |
| `urls.py` | URL routing for this app |
| `admin.py` | How the models show up in the Django admin |
| `migrations/` | DB schema change scripts (auto-generated) |
| `tests/` (or `tests.py`) | Test files |
| `services/` (Loudrr-specific) | Business logic (we'll cover this pattern) |

Not every app has every file — only what it needs.

---

## Part 6 — `core/` app (the foundation)

This is the most important app. It contains:
- The User model
- The waitlist system
- The credit/karma system
- Audit logging
- Outbox events (for reliable notifications)
- X OAuth verification
- Most of the business logic services

```
core/
├── __init__.py
├── apps.py                       ← Registers signals when Django starts
├── models.py                     ← User, Transaction, WaitlistEntry, OutboxEvent, etc.
├── admin.py                      ← How those models appear in /admin/
├── signals.py                    ← Event handlers (e.g., when waitlist approved → queue notification)
├── tasks.py                      ← Background tasks (django-q2)
├── rules.py                      ← Permission predicates (django-rules)
├── guards.py                     ← Reusable permission/business-rule checks
├── invariants.py                 ← Runtime checks ("balance can never be negative" etc.)
├── circuit_breakers.py           ← Wrappers for external API calls (so they don't crash everything)
├── backends.py                   ← Custom auth backend (logs users in by Telegram ID)
│
├── api/                          ← REST API views for general users
│   ├── serializers.py            ← Convert models to/from JSON
│   ├── views.py                  ← API endpoints
│   └── urls.py                   ← URL routing for this api/
│
├── services/                     ← BUSINESS LOGIC (the heart of the backend)
│   ├── credits.py                ← CreditService — earn/spend/refund karma
│   ├── settlement.py             ← Awards karma after engagement verification
│   ├── verification.py           ← Verifies engagements via Twitter API
│   ├── twitter_verification.py   ← Wrapper around Twitter API
│   ├── tweetscout.py             ← Wrapper around TweetScout API
│   ├── tweet_score.py            ← Tier calculations from TweetScout score
│   ├── x_oauth.py                ← X OAuth flow (PKCE, state, token exchange)
│   ├── x_url_resolver.py         ← Parse X profile URLs
│   ├── outbox.py                 ← OutboxService — queues + processes events
│   ├── posts.py                  ← Feed query helpers
│   ├── settings.py               ← get_setting() helper (Constance + DB)
│   ├── referral.py               ← Referral code logic
│   ├── xp.py                     ← Sponsored XP (separate from karma)
│   ├── gamification.py           ← Streaks + bonus calculations
│   ├── campaigns.py              ← Campaign eligibility + winner selection
│   └── engagements.py            ← Engagement helpers
│
├── management/commands/          ← Custom CLI commands (run via manage.py)
│   ├── seed_posts.py
│   ├── run_e2e_test.py
│   ├── run_integration_test.py
│   ├── full_system_test.py
│   ├── requeue_stuck_batches.py
│   ├── test_queue_system.py
│   └── create_load_test_users.py
│
├── migrations/                   ← Auto-generated DB schema scripts
│   ├── 0001_initial.py
│   ├── 0002_*.py
│   └── ... (~46 files)
│
└── tests/                        ← Tests for this app
    ├── test_decimal_karma.py
    ├── test_e2e_gaming.py
    ├── test_engagement_hypothesis.py
    ├── test_integration_e2e.py
    ├── test_race_conditions.py
    └── test_settlement_verification.py
```

### `models.py` — your database tables

This file defines the database schema in Python. Each class becomes a table.

Mini example to read:
```python
class Transaction(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=12, decimal_places=4)
    type = models.CharField(max_length=20, choices=Type.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "transactions"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "type", "idempotency_key"],
                name="transaction_idempotency_unique"
            ),
        ]
```

Reading this: "make a database table called `transactions` with these columns. Enforce a unique constraint so we never insert two rows with the same `(user, type, idempotency_key)`."

Django auto-generates the SQL for you. You never write `CREATE TABLE` by hand.

**This file is BIG (~900 lines).** It contains 11+ models. You don't need to understand all of them at once. Open it, scroll through, get the shape.

### `signals.py` — react to model changes

A "signal" is Django's way of saying: "when this thing happens to this model, also do this other thing."

Example:
```python
@receiver(post_save, sender=WaitlistEntry)
def send_approval_notification_on_approve(sender, instance, created, **kwargs):
    # This runs every time a WaitlistEntry is saved
    if instance.status == 'APPROVED':
        # queue a notification
```

We use signals to:
- Queue Telegram notifications when waitlist status changes
- Increment referral counts when someone gets approved

Signals are powerful but can be confusing because the "trigger" is implicit. If you can't find why some side-effect is happening, check signals.py.

### `tasks.py` — background work

Functions that run in the background via django-q2 (the worker). Used for things that are too slow or unreliable to do during the user's request:
- Process pending notifications
- Fetch TweetScout data after approval
- Reset daily karma caps at midnight
- Clean up old outbox events

You don't call these directly. You call `async_task("core.tasks.function_name", arg1, arg2)`, which writes a message to Redis. The qcluster worker picks it up and runs it.

### `rules.py` — permissions

Uses `django-rules` library. Defines small predicate functions:
```python
@rules.predicate
def is_not_banned(user):
    return not user.is_banned

@rules.predicate
def has_x_account(user):
    return bool(user.x_username)
```

Then we combine them and attach to actions:
```python
rules.add_perm('core.can_create_post', is_not_banned & has_x_account)
```

Then in views:
```python
@has_perm('core.can_create_post')
def create_post(request):
    ...
```

This pattern is GOOD because permissions are reusable, testable, and composable.

### `services/` — business logic (THE most important folder)

This is Loudrr's secret sauce. Instead of putting business logic in views (which gets messy), we put it in service classes/functions.

Pattern:
```python
# In services/credits.py
class CreditService:
    def __init__(self, user):
        self.user = user

    @transaction.atomic
    def earn(self, amount, idempotency_key, ...):
        # The actual logic here
        # Locks the row, checks daily cap, creates Transaction, etc.
```

Then views just orchestrate:
```python
def my_view(request):
    user = get_user_from_request(request)
    service = CreditService(user)
    result = service.earn(amount=10, idempotency_key="xyz")
    return JsonResponse(result)
```

**Why this pattern?**
- View stays thin (just request/response handling)
- Service is testable independently (don't need to fake an HTTP request)
- Service can be reused (called from view, signal, management command, task)
- Business invariants live in one place

Every important domain has a service: credits, posts, engagements, outbox, X OAuth, referrals, etc.

**Open `services/credits.py` and read `CreditService.earn()`.** It's the most important method in the entire backend.

### `migrations/` — DB schema versioning

Every time you change `models.py`, you need a "migration" — a script that updates the database to match the new model. Django generates these for you with `python manage.py makemigrations`.

Each migration is a numbered Python file (`0001_initial.py`, `0002_add_xyz.py`...). They're like git commits but for your database schema.

You apply them with `python manage.py migrate`. In production, this runs on every deploy.

**Don't edit migration files after they've been applied.** If you need to undo a change, write a NEW migration that does the undo.

### `management/commands/` — custom CLI tools

Each `*.py` file becomes a `manage.py` subcommand. Useful for one-off scripts:
- `seed_posts.py` — populate test data
- `run_e2e_test.py` — end-to-end smoke test
- `requeue_stuck_batches.py` — manually retry verification batches

Run with `python manage.py seed_posts`, etc.

### `tests/` — test files

pytest finds files starting with `test_` and runs them. Each test is a function starting with `test_`:
```python
def test_user_cannot_earn_above_daily_cap(db):
    user = User.objects.create(...)
    service = CreditService(user)
    service.earn(amount=500, ...)  # at cap
    with pytest.raises(DailyCapReachedError):
        service.earn(amount=1, ...)  # over cap
```

We use `pytest` (the test runner) and `hypothesis` (property-based testing — generates random inputs to find edge cases).

---

## Part 7 — `miniapp/` app (Telegram WebApp APIs)

This app contains all the API endpoints that the Telegram mini-app calls. It's basically just views + URL routing.

```
miniapp/
├── __init__.py
├── apps.py
├── models.py                 ← Mostly empty (no own models)
├── admin.py                  ← Empty
├── views.py                  ← All the API endpoints (waitlist register, user info, post submit, engagement, etc.)
├── views_x_verification.py   ← X OAuth verification endpoints (separate file for clarity)
├── schema.py                 ← Serializer classes for API docs
├── urls.py                   ← URL routing
└── migrations/
```

### `views.py` is BIG (~1700 lines)

It has every API endpoint the mini-app needs:
- `WaitlistRegisterView` — POST /waitlist/register/
- `WaitlistStatusView` — GET /waitlist/status/
- `UserInfoView` — GET /user/
- `LinkXAccountView` — POST /user/link-x/
- `StartSessionView` — POST /session/start/
- `RecordClickView` — POST /session/click/
- `QueueClaimView` — POST /session/queue-claim/
- `ClaimHistoryView` — GET /claims/history/
- `SubmitPostView` — POST /post/submit/
- ... and more

Each view is a class that extends `APIView` (from Django REST Framework). They look like:

```python
class WaitlistRegisterView(APIView):
    permission_classes = [AllowAny]  # no auth needed for waitlist signup

    @transaction.atomic
    def post(self, request):
        # Read data from request
        email = request.data.get("email", "").strip().lower()
        # Validate
        # Save to DB
        # Return JSON response
        return Response({"status": "registered"})
```

### `views_x_verification.py`

Similar but specifically for X OAuth flow. We split it out because views.py was getting too big.

### `urls.py`

Maps URL paths to views:
```python
urlpatterns = [
    path("waitlist/register/", views.WaitlistRegisterView.as_view()),
    path("user/", views.UserInfoView.as_view()),
    path("session/start/", views.StartSessionView.as_view()),
    # etc.
]
```

Combined with the root `urls.py` prefix (`api/miniapp/`), the full URL becomes `/api/miniapp/waitlist/register/`.

---

## Part 8 — `posts/` app (engagement marketplace)

The post submission, engagement tracking, escrow lifecycle, and campaigns.

```
posts/
├── __init__.py
├── apps.py
├── models.py        ← Post, Engagement, SponsoredPost, Campaign, CampaignEntry, VerificationBatch
├── admin.py
├── tasks.py         ← process_verification_batch (async), expire_old_posts (hourly)
├── rules.py         ← Permission predicates for posts
├── api/             ← API endpoints
│   ├── serializers.py
│   ├── views.py
│   └── urls.py
└── migrations/
```

### `tasks.py` — heavy lifting in the background

Two important tasks:

**`process_verification_batch(batch_id)`** — verifies a batch of engagements via Twitter API. Two-phase pattern:
1. Phase 1: API calls (no DB locks held)
2. Phase 2: Atomic DB writes (escrow deduction + credit award)

Splitting these prevents the DB from being locked while waiting on slow Twitter responses.

**`expire_old_posts()`** — runs hourly via the django-q schedule. Finds posts older than `POST_EXPIRY_HOURS` and refunds the remaining escrow to the creator.

### `models.py`

Notable models:
- `Post` — a tweet someone wants engagement on. Has escrow (locked karma), status (active/completed/cancelled), redirect_token.
- `Engagement` — one user engaging with one post. Has unique constraint `(user, post)` so users can't double-engage.
- `SponsoredPost` — extension to Post for paid campaigns.
- `Campaign` — raffles/giveaways with eligibility criteria.
- `VerificationBatch` — async queue for verifying multiple engagements at once.

---

## Part 9 — `loud/` app (UGC submissions)

LOUD is a separate sub-feature: users submit X posts to themed projects and earn points based on TweetScout score.

```
loud/
├── __init__.py
├── apps.py
├── models.py            ← LoudProject, LoudSubmission, LoudLeaderboardEntry, LoudPointAdjustment
├── admin.py
├── views.py             ← Project listing, submission, leaderboard
├── urls.py
├── rules.py
├── services/            ← LoudService for business logic
│   └── loud.py
├── templates/           ← (rarely used; mostly API-only)
├── tests/
└── migrations/
```

Same patterns as before — service-oriented, models for DB, views for HTTP.

---

## Part 10 — `bots/` app (Telegram bot)

The Telegram bot — handlers for commands, notification sending, webhook view.

```
bots/
├── __init__.py
├── apps.py
├── management/commands/
│   ├── run_telegram_bot.py            ← Polling mode (dev)
│   ├── set_telegram_webhook.py        ← Register webhook with Telegram (prod)
│   └── delete_telegram_webhook.py     ← Unregister webhook
└── telegram/
    ├── __init__.py
    ├── bot.py                         ← Bot factory (create_bot())
    ├── app_instance.py                ← Lazy singleton for the bot Application (webhook mode)
    ├── handlers.py                    ← Command handlers (/start, /help, /launch)
    ├── views.py                       ← Django webhook view (receives Telegram updates)
    ├── notifications.py               ← Send approval / waitlist confirmation cards
    └── image_utils.py                 ← Fetch card PNG from Next.js
```

### Two ways the bot runs

- **Polling mode (dev)**: `python manage.py run_telegram_bot`. The bot constantly asks Telegram "any new messages?". Easy for local dev (no public URL needed).
- **Webhook mode (prod)**: Telegram POSTs new updates to our `/api/telegram/webhook/` endpoint. The Django view in `telegram/views.py` handles them. Faster, no separate bot process needed.

Both modes use the same handlers in `handlers.py`.

### `notifications.py` & `image_utils.py`

We covered these in [01-how-the-card-system-works.md](01-how-the-card-system-works.md). Re-read that doc with this folder map in mind — it'll make more sense now.

---

## Part 11 — `redirects/` app (engagement click tracking)

When a user clicks "engage with this post" in the mini app, we don't open X directly. We open `/r/<token>/` first. This lets us:
1. Record the click in our DB (creates an Engagement row)
2. Then redirect to X

That way we know the user actually started the engagement.

```
redirects/
├── __init__.py
├── apps.py
├── models.py     ← (if any redirect-specific data)
├── admin.py
├── views.py      ← The /r/<token>/ redirect view
└── urls.py
```

Tiny app. One main view. Read it in 5 minutes.

---

## Part 12 — Putting it all together: how a request flows

Let's trace what happens when a user submits the waitlist form. Follow along by opening each file mentioned.

### Step 1: HTTP request arrives
User's mini-app POSTs to `https://loudrr.com/api/miniapp/waitlist/register/` with JSON body.

### Step 2: Django routes the URL
- `echo/urls.py` matches `/api/miniapp/...` → delegates to `miniapp/urls.py`
- `miniapp/urls.py` matches `/waitlist/register/` → routes to `WaitlistRegisterView.post()`

### Step 3: View runs
- `miniapp/views.py` → `WaitlistRegisterView.post(request)`
- Reads + validates request data
- Inside `transaction.atomic()`, calls `WaitlistEntry.objects.create(...)`

### Step 4: Model creation triggers signal
- Django saves the row to the `waitlist_entries` table
- `post_save` signal fires
- `core/signals.py` → `send_submission_confirmation_on_submit(sender, instance, ...)` runs
- Calls `OutboxService.queue_waitlist_submitted(...)` which creates an `OutboxEvent` row

### Step 5: After commit, kick the worker
- `transaction.on_commit(trigger_processing)` runs after the transaction commits
- It calls `async_task("core.tasks.process_pending_outbox_events", ...)` which writes a message to Redis

### Step 6: View returns response
- View returns `Response({"status": "registered", "referral_code": "..."}, status=200)`
- User sees success in the mini app
- User's request completed in <100ms even though the notification hasn't been sent yet

### Step 7: Worker processes the queued task
- The qcluster worker (running in another process) sees the new message in Redis
- Calls `core/tasks.py` → `process_pending_outbox_events(batch_size=10)`
- That function reads all PENDING outbox events from the DB
- For each event, calls `OutboxService.process_event(event)`

### Step 8: Outbox handler routes to the right notification
- `core/services/outbox.py` → `process_event(event)` checks `event.event_type`
- For `WAITLIST_SUBMITTED`, calls `_process_waitlist_submitted(event)`
- That spins up an asyncio loop and calls `send_waitlist_confirmation(entry)`

### Step 9: Notification function
- `bots/telegram/notifications.py` → `send_waitlist_confirmation(entry)`
- Calls `create_waitlist_card(x_username=...)` to fetch the PNG
- Calls `bot.send_photo(chat_id, photo, caption)` to deliver via Telegram

### Step 10: Card image bridge
- `bots/telegram/image_utils.py` → `create_waitlist_card(...)`
- Builds URL: `https://loudrr.com/api/cards/waitlist?username=...`
- HTTP GET to Next.js, gets back PNG bytes
- Returns BytesIO wrapping the bytes

### Step 11: Telegram delivers
- python-telegram-bot library makes HTTPS POST to `api.telegram.org`
- Telegram's servers deliver to the user's chat
- User sees the card

### Recap

| File | Role |
|------|------|
| `echo/urls.py` | Top-level URL dispatch |
| `miniapp/urls.py` | App-level URL dispatch |
| `miniapp/views.py` | View receives request, creates entry |
| `core/models.py` | WaitlistEntry definition |
| `core/signals.py` | Signal handler queues OutboxEvent |
| `core/services/outbox.py` | Service to queue + later process events |
| `core/tasks.py` | Background task that processes events |
| `bots/telegram/notifications.py` | Builds Telegram message |
| `bots/telegram/image_utils.py` | Fetches PNG from Next.js |
| `frontend/app/api/cards/waitlist/route.tsx` | Generates the PNG |
| `python-telegram-bot` library | Sends message to Telegram API |

This same end-to-end pattern repeats for every feature. Once you understand this flow, you understand the backend.

---

## Part 13 — What's NEXT to learn

You now have a map. Recommended order to go deeper:

1. **Read `core/models.py`** — get familiar with what models exist. Don't try to understand every line; just see the shape.
2. **Read `core/services/credits.py`** — the most important service. Understand `earn()` and `spend()`.
3. **Read `core/signals.py`** — understand how signals trigger side effects.
4. **Read `miniapp/views.py`** — see how views are written. Pick one (like `UserInfoView`) and follow it end-to-end.
5. **Run the test suite**: `pytest backend/` — see green dots, then look at one test file like `tests/test_decimal_karma.py`.

Future docs in this `educate/` folder will go deeper:
- `03-django-models-and-database.md` — models, migrations, ORM, querysets
- `04-views-and-urls-and-drf.md` — class-based views, DRF, serializers
- `05-the-services-layer.md` — the service pattern in depth
- `06-async-tasks-and-cron.md` — django-q2, schedules, the worker
- `07-authentication-and-permissions.md` — Telegram WebApp auth, X OAuth, django-rules
- `08-external-apis-and-circuit-breakers.md` — Twitter, TweetScout, Telegram
- `09-testing-patterns.md` — pytest, hypothesis, fixtures
- `10-admin-customization.md` — custom admin actions, filters

Tell me which one you want next.

---

## Quick reference card

Pin this somewhere:

| Want to change... | Look in... |
|-------------------|------------|
| What an API endpoint does | `<app>/views.py` |
| What URL maps to what view | `<app>/urls.py` (and `echo/urls.py`) |
| The shape of the database | `core/models.py` (or other apps' models.py) |
| Business logic (credits, posts, etc.) | `core/services/*.py` |
| Settings (env vars, app config) | `echo/settings.py` |
| What runs in the background | `core/tasks.py`, `posts/tasks.py` |
| What runs when X happens (events) | `core/signals.py` |
| Telegram bot commands | `bots/telegram/handlers.py` |
| Telegram notification sending | `bots/telegram/notifications.py` |
| Card image content | `frontend/app/api/cards/<type>/route.tsx` |
| Admin panel customization | `<app>/admin.py` |
| Permission rules | `<app>/rules.py` |
| Tests | `<app>/tests/` |
| Custom CLI commands | `<app>/management/commands/` |
| DB schema history | `<app>/migrations/` |
</content>
</invoke>