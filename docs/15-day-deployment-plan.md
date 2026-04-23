# Loudrr — 15-Day Pre-Deployment Plan

**Start:** 2026-04-21 · **Target launch:** 2026-05-12 (~3 weeks of weekdays)
**Capacity assumption:** ~5-6 hours focused work per day
**Definition of Done per day:** code committed + pushed + smoke-tested locally

Categories: **DEV** = code features · **BOT** = bot/notification safety · **DATA** = DB integrity · **SEC** = security · **TEST** = testing · **RESP** = responsive UI · **INFRA** = deployment infra · **OBS** = observability · **OPS** = runbook/process · **LEGAL** = compliance · **LAUNCH** = final pre-launch

Priority: **P0** = blocks launch · **P1** = needed before users · **P2** = post-launch acceptable

---

## Tooling additions for responsive UI testing

Install once (Day 1) and use throughout the plan:

```bash
# Frontend lints + responsive checks
cd frontend
npm install -D eslint-plugin-tailwindcss          # validates Tailwind classes, flags missing responsive prefixes
npm install -D stylelint stylelint-config-standard # raw CSS quality + rule ordering
npm install -D @lhci/cli                          # Lighthouse CI: mobile + desktop perf/a11y/best-practices
npm install -D @playwright/test                   # cross-viewport tests + visual regression
npm install -D pa11y-ci                           # accessibility linter (a11y is half of "responsive")
```

What these catch:
- **eslint-plugin-tailwindcss** → flags `w-[400px]` without responsive variants, invalid classes, conflicting utilities
- **Lighthouse CI mobile preset** → fails build if mobile score drops, layout shift, tap-targets too small
- **Playwright viewport matrix** → screenshots at 320 / 375 / 414 / 768 / 1024 / 1280 px, fails if horizontal scrollbar appears or critical elements get clipped
- **pa11y-ci** → WCAG AA violations (color contrast, missing alt, etc.)

---

# WEEK 1 — Bot safety + critical code (P0)

## Day 1 — Bot safety foundations
| Task | Cat | Pri | Est |
|------|-----|-----|-----|
| A1: Add unique constraint on OutboxEvent (event_type, reference_type, reference_id) for active events | BOT | P0 | 30 min |
| A1: Update OutboxService.queue_*() to catch IntegrityError → return existing event | BOT | P0 | 30 min |
| A4: Add `NOTIFICATIONS_PAUSED` Constance flag → check in OutboxService.process_event() | BOT | P0 | 20 min |
| A6: Add Telegram webhook update_id dedup via Redis (24h TTL) in `bots/telegram/views.py` | BOT | P0 | 45 min |
| Install responsive lint stack (npm install lines above) | RESP | P1 | 15 min |
| Configure eslint-plugin-tailwindcss in `frontend/eslint.config.mjs` and run once | RESP | P1 | 30 min |
| Commit + push | OPS | P0 | 10 min |

## Day 2 — Notification audit + ENCRYPTION_KEY
| Task | Cat | Pri | Est |
|------|-----|-----|-----|
| A2: Create `NotificationSent` model (recipient_telegram_id, message_hash, outbox_event FK, sent_at) + migration | BOT | P0 | 45 min |
| A2: Update bot send helpers to record + check 24h dedup before sending | BOT | P0 | 1 hr |
| A2: Auditlog register the new model | BOT | P0 | 5 min |
| A5: Add `NOTIFICATION_RECIPIENT_WHITELIST` env var; in non-prod skip non-whitelisted recipients | BOT | P1 | 30 min |
| ENCRYPTION_KEY: add to `.env.example` with `secrets.token_urlsafe(32)` instructions | SEC | P0 | 10 min |
| ENCRYPTION_KEY: add startup assertion in `apps.py` (fail fast if unset in prod) | SEC | P0 | 15 min |
| Commit + push | OPS | P0 | 10 min |

## Day 3 — Permission decorators + IntegrityError handlers
| Task | Cat | Pri | Est |
|------|-----|-----|-----|
| Add `@has_perm` decorators to all mutation endpoints in `core/api/views.py` | DEV | P0 | 1.5 hr |
| Audit and add to `miniapp/views.py` (post submit, link X, link x_oauth start, etc.) | DEV | P0 | 1 hr |
| Add `IntegrityError → 400` wrapper for `WaitlistRegisterView`, `LinkXAccountView`, `SubmitPostView` | DEV | P0 | 1 hr |
| Map constraint names to friendly messages (e.g., `user_no_self_referral` → "You can't refer yourself") | DEV | P0 | 30 min |
| Commit + push | OPS | P0 | 10 min |

## Day 4 — Circuit breakers wired up
| Task | Cat | Pri | Est |
|------|-----|-----|-----|
| Wrap Twitter API calls in `core/services/twitter_verification.py` with `twitter_breaker.call(...)` | DEV | P0 | 45 min |
| Wrap TweetScout API in `core/services/tweetscout.py` with `tweetscout_breaker` | DEV | P0 | 30 min |
| Wrap Telegram Bot API calls (in notifications.py + outbox.py `_process_telegram_notify`) | DEV | P0 | 30 min |
| Add `/admin/breakers/` page or management command to inspect breaker states | DEV | P1 | 45 min |
| Verify referral_count increment fires correctly: write quick test, approve a fake user, check count | DEV | P0 verify | 30 min |
| Commit + push | OPS | P0 | 10 min |

## Day 5 — Per-user rate limit + schema docs + Redis cache
| Task | Cat | Pri | Est |
|------|-----|-----|-----|
| A3: Per-user Telegram notification rate limit (5/hr/user) via Redis INCR + TTL | BOT | P1 | 45 min |
| Switch `CACHES` from `LocMemCache` to `django-redis` | INFRA | P1 | 30 min |
| Install `django-redis`, configure with existing REDIS_URL | INFRA | P1 | 20 min |
| Add `@extend_schema` decorators to all `core/api/views.py` endpoints | DEV | P1 | 1 hr |
| Add `@extend_schema` decorators to remaining `miniapp/views.py` endpoints | DEV | P1 | 1.5 hr |
| Verify schema validates: `python manage.py spectacular --validate` | DEV | P1 | 10 min |
| Commit + push | OPS | P0 | 10 min |

---

# WEEK 2 — Data safety + tests + responsive UI

## Day 6 — Backups + disk monitoring
| Task | Cat | Pri | Est |
|------|-----|-----|-----|
| Create Backblaze B2 account + bucket `loudrr-backups-prod` | INFRA | P0 | 20 min |
| Configure Coolify scheduled backup task: daily `pg_dump` → B2 (rotate after 30 days) | DATA | P0 | 1 hr |
| Set Hetzner disk alert at 75% via cloud console | INFRA | P0 | 15 min |
| Set Hetzner memory + CPU alerts | INFRA | P1 | 15 min |
| First manual backup + verify file appeared in B2 | DATA | P0 | 15 min |
| First restore drill: download backup, restore to local Postgres, run smoke queries | DATA | P0 | 1 hr |
| Document restore procedure in `docs/runbook.md` | OPS | P0 | 30 min |
| Commit + push | OPS | P0 | 10 min |

## Day 7 — Soft delete + migration safety
| Task | Cat | Pri | Est |
|------|-----|-----|-----|
| B3: Convert User model to `SafeDeleteModel(SOFT_DELETE_CASCADE)` + migration | DATA | P0 | 1 hr |
| B3: Same for WaitlistEntry, Post, Engagement | DATA | P0 | 1 hr |
| B3: Update admin to show deleted_at + add restore action | DATA | P0 | 45 min |
| B4: Write `docs/migration-checklist.md` (preflight + rollback template) | OPS | P0 | 30 min |
| Add `DATABASES['default']['ATOMIC_REQUESTS'] = True` to settings | DATA | P1 | 5 min |
| Audit `.save()` calls outside `transaction.atomic()` blocks; wrap any risky ones | DATA | P1 | 1.5 hr |
| Commit + push | OPS | P0 | 10 min |

## Day 8 — Set up test infra + X OAuth tests
| Task | Cat | Pri | Est |
|------|-----|-----|-----|
| Add pytest fixtures for: approved User, mock Telegram bot, mock X OAuth response | TEST | P0 | 1 hr |
| Test: X OAuth callback success (username matches → x_verified=True) | TEST | P0 | 45 min |
| Test: X OAuth callback mismatch (different username → pending_claimed_x_username set) | TEST | P0 | 45 min |
| Test: ConfirmMismatchView creates XVerificationRequest | TEST | P0 | 30 min |
| Test: Admin approve action updates user.x_username + sets verified | TEST | P0 | 30 min |
| Test: Admin reject action demotes user back to waitlist with x_verified_previously=True | TEST | P0 | 45 min |
| Run full test suite: `pytest backend/ -x` | TEST | P0 | 15 min |
| Commit + push | OPS | P0 | 10 min |

## Day 9 — Outbox + FSM + Campaign tests
| Task | Cat | Pri | Est |
|------|-----|-----|-----|
| Test: OutboxEvent retry (mark as failed → retry_failed_outbox_events resets to pending) | TEST | P0 | 45 min |
| Test: OutboxEvent dedup (try queueing duplicate → IntegrityError caught, returns existing) | TEST | P0 | 30 min |
| Test: WaitlistEntry FSM rollback (approve then reject → state correct) | TEST | P0 | 30 min |
| Test: Post FSM auto-complete on escrow=0 + auto-cancel on expiry | TEST | P0 | 45 min |
| Test: Campaign winner selection (random + weighted_xp + weighted_score) | TEST | P1 | 1 hr |
| Test: Concurrent engagement claim by same user (race condition) | TEST | P1 | 45 min |
| Commit + push | OPS | P0 | 10 min |

## Day 10 — Responsive UI lints + Playwright viewport tests
| Task | Cat | Pri | Est |
|------|-----|-----|-----|
| Run `npx eslint frontend/app --ext .tsx --max-warnings 0` and fix all responsive class issues | RESP | P0 | 1.5 hr |
| Set up Playwright config with viewport matrix (320, 375, 414, 768, 1024, 1280) | RESP | P0 | 30 min |
| Write Playwright test: landing page loads at all viewports, no horizontal scroll | RESP | P0 | 45 min |
| Write Playwright test: mini-app `/app` loads at all viewports | RESP | P0 | 45 min |
| Write Playwright test: waitlist registration wizard flows on 320px (smallest mobile) | RESP | P0 | 45 min |
| Write Playwright test: ConnectXScreen + MismatchPromptScreen + PendingReviewScreen on mobile | RESP | P0 | 45 min |
| Set up Lighthouse CI: target ≥ 90 perf, ≥ 95 a11y on mobile | RESP | P1 | 30 min |
| Run `npx pa11y-ci http://localhost:3000/ http://localhost:3000/app` and fix top issues | RESP | P1 | 1 hr |
| Commit + push | OPS | P0 | 10 min |

---

# WEEK 3 — Observability + infra + pre-launch

## Day 11 — Sentry + uptime
| Task | Cat | Pri | Est |
|------|-----|-----|-----|
| Sentry account + create projects (loudrr-backend, loudrr-frontend) | OBS | P0 | 15 min |
| Install `sentry-sdk[django]`, add config in `echo/settings.py` (DSN from env) | OBS | P0 | 30 min |
| Send test error from `/admin/` to verify ingest | OBS | P0 | 15 min |
| Install `@sentry/nextjs` in frontend, run `npx @sentry/wizard` | OBS | P0 | 30 min |
| Upload source maps for readable stack traces | OBS | P1 | 30 min |
| UptimeRobot account, add monitor for `https://loudrr.com/health/` every 5 min | OBS | P0 | 15 min |
| Configure UptimeRobot Telegram alerts to your TG ID | OBS | P0 | 15 min |
| Sentry alerts: 5xx rate > 5/min, qcluster failed task count > 10/hr, OutboxEvent FAILED > 5/hr | OBS | P1 | 45 min |
| Frontend ErrorBoundary in `frontend/app/layout.tsx` (logs to Sentry) | DEV | P1 | 30 min |
| Commit + push | OPS | P0 | 10 min |

## Day 12 — Cloudflare + security headers
| Task | Cat | Pri | Est |
|------|-----|-----|-----|
| Add `loudrr.com` to Cloudflare zone (already done) — verify orange-cloud proxy ON | INFRA | P1 | 15 min |
| Cloudflare → SSL/TLS → Full (strict) | INFRA | P0 | 5 min |
| Cloudflare → Security → "Bot Fight Mode" ON for /admin paths | INFRA | P1 | 10 min |
| Cloudflare → Caching → bypass /api/* (don't cache API responses) | INFRA | P0 | 10 min |
| Add Django security middleware settings: SECURE_SSL_REDIRECT, SESSION_COOKIE_SECURE, CSRF_COOKIE_SECURE, SECURE_HSTS_SECONDS=31536000, SECURE_CONTENT_TYPE_NOSNIFF | SEC | P0 | 30 min |
| Add CSP header via `django-csp` (or middleware) | SEC | P1 | 1 hr |
| Add X-Frame-Options=SAMEORIGIN (Telegram WebApp needs to embed) | SEC | P0 | 10 min |
| Run `python manage.py check --deploy` → fix every warning | SEC | P0 | 30 min |
| Trivy scan on built backend Docker image | SEC | P1 | 30 min |
| Commit + push | OPS | P0 | 10 min |

## Day 13 — Coolify config for prod
| Task | Cat | Pri | Est |
|------|-----|-----|-----|
| Update Coolify backend service: use `Dockerfile` (not `Dockerfile.celery`) | INFRA | P0 | 15 min |
| Add Coolify worker service: use `Dockerfile.qcluster` (replaces celery worker + beat) | INFRA | P0 | 30 min |
| Set all prod env vars in Coolify (compare against `.env.example` line-by-line) | INFRA | P0 | 1 hr |
| Generate fresh prod `TELEGRAM_WEBHOOK_SECRET`: `openssl rand -hex 32` | INFRA | P0 | 5 min |
| Set `SITE_URL=https://loudrr.com`, `MINIAPP_URL=https://loudrr.com/app`, `LANDING_URL=https://loudrr.com`, `X_OAUTH_CALLBACK_URL=https://loudrr.com/api/auth/x/callback/`, `TELEGRAM_WEBHOOK_URL=https://loudrr.com/api/telegram/webhook/` | INFRA | P0 | 15 min |
| Update X Developer Portal callback URI to prod URL | INFRA | P0 | 5 min |
| PgBouncer one-click in Coolify, point Django at it (port 6432) | INFRA | P0 | 30 min |
| Deploy to staging environment first (separate Coolify stack on staging.loudrr.com) | INFRA | P0 | 1 hr |
| Run migrations on staging: `python manage.py migrate` | INFRA | P0 | 10 min |
| Run `python manage.py set_telegram_webhook` on staging | INFRA | P0 | 5 min |
| Verify staging /health/ returns 200 and admin login works | INFRA | P0 | 15 min |
| Commit + push | OPS | P0 | 10 min |

## Day 14 — Load test, E2E, legal pages
| Task | Cat | Pri | Est |
|------|-----|-----|-----|
| Locust: write scenario simulating 100 users hitting `/session/start/` + `/session/click/` + `/session/queue-claim/` | TEST | P1 | 1 hr |
| Run Locust against staging for 5 min, watch Sentry + qcluster logs for issues | TEST | P1 | 30 min |
| Cypress: write happy-path E2E (waitlist register → admin approve → mini-app → connect X → engage → claim) | TEST | P1 | 2 hr |
| Run Cypress against staging | TEST | P1 | 15 min |
| Privacy Policy page at `/privacy/` (Next.js static page) | LEGAL | P0 | 1 hr |
| Terms of Service page at `/terms/` | LEGAL | P0 | 45 min |
| GDPR data export endpoint (`POST /api/miniapp/account/export/` returns JSON dump) | LEGAL | P1 | 45 min |
| GDPR delete endpoint (`POST /api/miniapp/account/delete/` soft-deletes with 30-day grace) | LEGAL | P1 | 45 min |
| Commit + push | OPS | P0 | 10 min |

## Day 15 — Final pre-launch pass + deploy
| Task | Cat | Pri | Est |
|------|-----|-----|-----|
| Final `python manage.py check --deploy` → must show zero warnings | LAUNCH | P0 | 15 min |
| Final `python manage.py migrate --plan` on prod DB → must show nothing pending | LAUNCH | P0 | 10 min |
| Run all tests: `pytest backend/` + `npm test` + Playwright + Cypress | LAUNCH | P0 | 30 min |
| Backup taken AND restore-tested same morning | LAUNCH | P0 | 45 min |
| Sentry: send test error from prod, verify it arrives | LAUNCH | P0 | 10 min |
| UptimeRobot: green | LAUNCH | P0 | 5 min |
| All env vars in Coolify match `.env.example` (audit one more time) | LAUNCH | P0 | 30 min |
| Set `LOAD_TEST_MODE=false`, `LOAD_TEST_SECRET=` (empty), `PRODUCTION_LOCK=True` in Constance | LAUNCH | P0 | 10 min |
| DNS for `loudrr.com` pointed at Cloudflare → Hetzner | LAUNCH | P0 | 15 min |
| Deploy to prod via Coolify | LAUNCH | P0 | 30 min |
| Run `python manage.py set_telegram_webhook` on prod | LAUNCH | P0 | 5 min |
| Smoke test on prod: register → approve → connect X → engage → claim → verify Telegram cards arrived | LAUNCH | P0 | 1 hr |
| Pin a "report bugs" Telegram thread for early users | OPS | P0 | 15 min |
| Watch Sentry, qcluster logs, OutboxEvent table for the first hour | OPS | P0 | 1 hr |

---

## Daily rituals (every day)

- Start: pull latest, `.\dev.ps1`, run `pytest -x` to confirm clean baseline
- End: commit + push, update todo list, write 2-line note in `docs/dev-log.md` about what shipped + what blocked

## Buffer / slip plan

If a day goes long → push lower-priority items to the next day. Day 15 is the hard launch deadline; everything in Days 1-12 must be done before Day 13 (deploy day). If you slip more than 2 days total, push launch by a week — don't compress Day 15.

## What gets cut if you only have 10 days instead of 15

- P2 items: skip
- Cypress E2E: replace with manual smoke test on staging
- Lighthouse CI: skip (run manually before launch)
- Source maps for Sentry frontend: skip (do post-launch)
- GDPR export/delete endpoints: skip (add post-launch with a "contact us" fallback)
- Trivy scan: skip
- Migration checklist doc: skip writing, just be careful

## What stays even if you have only 7 days

Everything marked P0. Total P0 effort is roughly 5 working days if you're focused. Add the 2 days of legal pages + final pre-launch pass = 7 day minimum.
