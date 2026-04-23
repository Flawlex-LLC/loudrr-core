# Loudrr Pre-Deployment Checklist

**Audit date:** 2026-04-21
**Target deployment:** Hetzner VPS via Coolify
**Stack:** Django 5.2 + django-q2 + PostgreSQL + Redis + Next.js 16 + python-telegram-bot

Priorities: **P0** = blocks launch, **P1** = before users, **P2** = post-launch acceptable

---

## A. CODE-LEVEL ISSUES (from audit)

### A.1 — django-rules permissions [P0]

**Finding:** 45 predicates defined in [core/rules.py](../backend/core/rules.py) but ZERO `@has_perm` decorators on mutation endpoints.

**Vulnerable endpoints in [core/api/views.py](../backend/core/api/views.py):**
- `CurrentUserView.patch()` line 27 — no permission check
- `LinkAccountView.post()` line 104 — no permission check
- `CreateUserView.post()` line 134 — should validate not banned

**Action:** wrap mutation endpoints with `@has_perm('core.can_update_profile')` etc.

### A.2 — Circuit breakers not applied [P0]

**Finding:** [circuit_breakers.py](../backend/core/circuit_breakers.py) defines 3 breakers (twitter, tweetscout, telegram) but they're never decorated onto actual API calls.

**Action:** wrap external HTTP calls in:
- `core/services/twitter_verification.py` → `twitter_breaker.call(...)`
- `core/services/tweetscout.py` → `tweetscout_breaker.call(...)`
- `bots/telegram/notifications.py` → `telegram_breaker.call(...)`

### A.3 — Telegram webhook idempotency [P0]

**Finding:** [bots/telegram/views.py](../backend/bots/telegram/views.py) doesn't dedupe by `update.update_id`. Telegram retries deliver same update multiple times.

**Action:** Cache `update_id` in Redis with 24h TTL; reject duplicates with 200 OK.

### A.4 — DB constraints return 500, not 400 [P0]

**Finding:** All 33 CheckConstraints/UniqueConstraints raise IntegrityError → 500 to client.

**Action:** Wrap model `.save()` in try/except IntegrityError in views, return 400 with friendly message based on constraint name.

### A.5 — ENCRYPTION_KEY missing default [P0]

**File:** [core/services/engagements.py:80](../backend/core/services/engagements.py#L80) — crashes if env var missing.

**Action:** Add to `.env.example` with `python -c "import secrets; print(secrets.token_urlsafe(32))"` instructions.

### A.6 — Referral count increment [P0 verify]

**Finding:** Audit says referral increment logic in approval handler is unclear. The signal exists in [core/signals.py](../backend/core/signals.py) but needs end-to-end verification with a real test approval.

### A.7 — Cache backend [P1]

**Finding:** `CACHES` in [echo/settings.py](../backend/echo/settings.py) uses `LocMemCache` — broken across multiple Django workers.

**Action:** Switch to `django-redis` cache backend in prod.

### A.8 — FSM `protected=True` [P1]

**Finding:** WaitlistEntry and Post use `FSMField(protected=False)` allowing raw `.status = X` assignment.

**Action:** Set `protected=True` after verifying no raw assignments remain.

### A.9 — drf-spectacular schema gaps [P1]

**Finding:** Only ~6 endpoints have `@extend_schema`. Most are undocumented in `/api/docs/`.

**Action:** Add `@extend_schema_view` to every public endpoint. Run `python manage.py spectacular --validate` in CI.

### A.10 — Mixed logging (structlog + stdlib) [P1]

**Finding:** Some files use `import structlog`, others use `import logging`. Inconsistent log format makes prod debugging painful.

**Action:** Replace all `import logging` with `structlog.get_logger()`.

### A.11 — Frontend Error Boundary [P1]

**Finding:** No `ErrorBoundary` in [frontend/app/layout.tsx](../frontend/app/layout.tsx). Component crash = white screen of death.

**Action:** Add error boundary at root layout.

### A.12 — ECHO_CONFIG hardcoded [P1]

**Finding:** Some constants in `settings.ECHO_CONFIG` should be runtime-tunable via Constance.

**Action:** Migrate POST_COST, tier multiplier ranges, etc. to Constance entries.

### A.13 — django-waffle unused [P2]

**Finding:** Installed but no `flag_is_active`/`switch_is_active` calls anywhere.

**Action:** Either start using for safe rollouts (X verification, LOUD, campaigns) or remove from deps.

### A.14 — django-fsm-log unused [P2]

**Finding:** Installed but not registered with FSMField models, so transitions aren't logged.

**Action:** Register or remove.

---

## B. FEATURE COMPLETENESS

Legend: ✓ implemented + tested · ⚠️ implemented but untested · ❌ stub/missing

### B.1 — Auth & Onboarding
| Feature | Status |
|---------|--------|
| Waitlist 3-step registration | ✓ |
| Waitlist admin approval | ✓ |
| Waitlist admin rejection | ✓ |
| Referral code submission | ✓ |
| Referral count increment on approval | ⚠️ — needs E2E verify |
| **X OAuth verification (post-approval)** | ⚠️ — just built |
| **X mismatch admin approve/reject** | ⚠️ — just built |
| Re-bounced waitlist with `x_verified_previously` | ⚠️ — needs verify |
| TweetScout fetch on approval | ⚠️ — verify event triggers |

### B.2 — Engagement Loop
| Feature | Status |
|---------|--------|
| Session start (feed) | ✓ |
| Click recording | ✓ |
| Queue-claim (verification batch) | ✓ |
| Async verification (qcluster) | ⚠️ — needs end-to-end verify |
| Settlement with tier multiplier | ⚠️ — needs concurrency test |
| Daily cap enforcement | ✓ |
| Honesty score on failure | ✓ |
| Streak tracking | ✓ |

### B.3 — Posts
| Feature | Status |
|---------|--------|
| Post submission with escrow | ✓ |
| Post auto-completion when escrow=0 | ✓ |
| **Post auto-expiry + refund** | ⚠️ — `expire_old_posts` task exists, needs scheduler verify |
| Sponsored post XP rewards | ⚠️ — code exists, untested |
| Tweet ownership validation | ✓ |

### B.4 — LOUD UGC
| Feature | Status |
|---------|--------|
| Project listing | ✓ |
| Submission with daily limit | ✓ |
| Leaderboard | ⚠️ — update logic untested under concurrency |
| Point adjustments (admin) | ⚠️ — model exists, admin action unclear |

### B.5 — Campaigns
| Feature | Status |
|---------|--------|
| Campaign creation (admin) | ✓ |
| Eligibility checking | ⚠️ |
| Winner selection (random/weighted) | ⚠️ — untested |

### B.6 — Telegram Bot
| Feature | Status |
|---------|--------|
| `/start` command | ✓ |
| `/launch` command | ✓ |
| `/help` command | ✓ |
| Deep link `ref_<CODE>` | ✓ |
| **Webhook mode (prod)** | ⚠️ — just built, untested in prod |
| Polling mode (dev) | ✓ |

### B.7 — Notifications (OutboxEvent)
| Feature | Status |
|---------|--------|
| Waitlist submitted card | ✓ |
| Waitlist approved card | ✓ |
| TweetScout fetch trigger | ⚠️ |
| Failed event retry | ✓ |
| Old event cleanup (scheduler) | ⚠️ |

---

## C. TEST COVERAGE

### C.1 — Existing tests (9 files)
- [test_decimal_karma.py](../backend/core/tests/test_decimal_karma.py) — unit
- [test_e2e_gaming.py](../backend/core/tests/test_e2e_gaming.py) — E2E
- [test_engagement_hypothesis.py](../backend/core/tests/test_engagement_hypothesis.py) — property-based
- [test_integration_e2e.py](../backend/core/tests/test_integration_e2e.py) — integration
- [test_race_conditions.py](../backend/core/tests/test_race_conditions.py) — concurrency
- [test_settlement_verification.py](../backend/core/tests/test_settlement_verification.py) — settlement
- [test_loud_hypothesis.py](../backend/loud/tests/test_loud_hypothesis.py) — LOUD property-based

### C.2 — Critical untested paths [P0]
- X OAuth callback (match + mismatch + admin actions)
- Outbox event retry under failure
- FSM rollback (reject after approve)
- Concurrent engagement claim by same user
- Webhook duplicate `update_id`

### C.3 — Important untested paths [P1]
- Campaign winner selection (random + weighted_xp + weighted_score)
- Post auto-expiry + refund
- Sponsored post XP distribution
- LOUD leaderboard update under concurrent submits
- Tier boundary cases (exactly at threshold)

### C.4 — External/manual tests
- **Locust** load test (~100 concurrent users on `/session/queue-claim/`)
- **Cypress** full happy path (register → approve → connect X → engage → claim)
- Manual smoke test on staging

---

## D. SECURITY

### D.1 — Already done ✓
- bandit · semgrep · gitleaks · sqlmap · OWASP ZAP · pip-audit · npm audit · custom OWASP Top 10 · pyright · jscpd

### D.2 — Pending [P0]
- **Rotate X Client Secret** (was pasted in chat earlier)
- `python manage.py check --deploy` shows zero warnings
- `DEBUG=False`, `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE` in prod env
- `LOAD_TEST_MODE=false` in prod
- `PRODUCTION_LOCK=True` in Constance

### D.3 — Pending [P1]
- Trivy scan on built Docker images
- Add CSP, HSTS, X-Frame-Options, X-Content-Type-Options headers
- Re-run pip-audit + npm audit pre-launch
- Verify Telegram init_data HMAC validation works on edge cases (missing fields, bad signature, expired auth_date)

---

## E. INFRASTRUCTURE (Hetzner + Coolify)

### E.1 — VPS [P0]
- Hetzner CPX21 minimum (4GB RAM, 2 vCPU) for ~500 users
- UFW firewall: only 22, 80, 443 open
- SSH key-only auth, password disabled
- fail2ban enabled
- Postgres NOT exposed publicly
- Redis NOT exposed publicly

### E.2 — Coolify config updates [P0]
- Replace `Dockerfile.celery` references with `Dockerfile.qcluster`
- Verify env vars match `.env.example` (no missing keys)
- Set: `SITE_URL`, `MINIAPP_URL`, `LANDING_URL`, `X_OAUTH_CALLBACK_URL`, `TELEGRAM_WEBHOOK_URL`, `TELEGRAM_WEBHOOK_SECRET`
- Run `python manage.py set_telegram_webhook` once after deploy
- Run `python manage.py migrate` (includes 0046 X verification migration)

### E.3 — Database [P0]
- PgBouncer for connection pooling (Coolify one-click)
- Daily Postgres backups
- Off-site backup copy (S3 / Backblaze B2)
- **Restore-test the backup** — actually restore to a temp DB and verify queries work

### E.4 — DNS / SSL [P1]
- Cloudflare in front of `loudrr.com` (DNS + DDoS + cache)
- Let's Encrypt via Coolify for HTTPS
- Disk monitoring (alert at 80%)
- Memory monitoring

### E.5 — Staging env [P1]
- Mirror of prod on a 2nd Coolify stack (subdomain like `staging.loudrr.com`)
- Test all deploys here first

---

## F. OBSERVABILITY

### F.1 — Error tracking [P0]
- **Sentry** backend SDK
- Sentry frontend SDK
- Source maps uploaded for React stack traces

### F.2 — Uptime [P0]
- UptimeRobot (free tier) ping `https://loudrr.com/health/` every 5 min
- Notify via email + Telegram

### F.3 — Alerts [P1]
- 5xx rate spike → Sentry → Telegram alert channel
- qcluster failed task count > N/min → alert
- OutboxEvent failed count > N → alert
- Disk > 80% → Hetzner alert

### F.4 — Logs [P1]
- Structured JSON logs (django-structlog already installed)
- Log rotation
- Optional: Better Stack / Logtail for aggregation

---

## G. OPERATIONAL READINESS

### G.1 — Documentation [P0]
- Runbook: "what to do when X is down" — at least 1 page
- Rollback plan: how to revert a bad deploy in <5 min (Coolify has built-in)
- Migration risk review for each deploy

### G.2 — Drills [P0]
- Manual rollback test on staging
- Manual smoke test: register → approve → Connect X → engage → claim
- Backup restore drill

---

## H. LEGAL & COMPLIANCE

### H.1 — Required pages [P0]
- Privacy Policy (data collected, retention, contact, your rights)
- Terms of Service
- Contact email + DPO email if EU users

### H.2 — GDPR / DPDPA endpoints [P1]
- `/account/export-data/` — JSON dump of user data
- `/account/delete/` — soft-delete + 30-day window then hard-delete
- Cookie banner only if non-essential cookies (you don't have many)

### H.3 — X / Twitter compliance [P0]
- Privacy policy must match what you told X Developer Portal about data usage
- "We use OAuth only for verification, no posting on behalf of users" — true and documented

---

## I. PRE-LAUNCH FINAL PASS (the day before)

- [ ] `python manage.py check --deploy` zero warnings
- [ ] `python manage.py migrate --plan` shows zero pending
- [ ] All Docker images rebuilt with latest commit
- [ ] Smoke test: full happy path completes on staging
- [ ] Backup taken AND restore-tested same day
- [ ] Sentry receives a test error from prod
- [ ] Uptime monitor green
- [ ] All env vars in Coolify match `.env.example`
- [ ] `LOAD_TEST_MODE=false`, `LOAD_TEST_SECRET=` (empty)
- [ ] `PRODUCTION_LOCK=True` in Constance
- [ ] DNS pointed at Hetzner / proxied via Cloudflare
- [ ] X Developer Portal callback URL points to prod, not dev tunnel
- [ ] Telegram bot webhook registered at prod URL (run `python manage.py set_telegram_webhook`)
- [ ] Privacy policy + ToS pages live and linked

---

## J. POST-LAUNCH DAY 1

- Monitor Sentry every hour
- Watch qcluster log for failed tasks
- Watch OutboxEvent FAILED count
- Have rollback plan ready
- Pin a "report bugs" Telegram thread for early users

---

**Honest assessment:** The codebase architecture is strong (FSM, constraints, locking, auditlog all in place). The biggest gaps are operational (backups, monitoring, alerts) and the "implemented but untested" features (X OAuth flow, post expiry, campaign winner selection). Audit-list completeness is already above what most early-stage startups ship with.

**Suggested execution order:**
1. **Today:** Finish X OAuth E2E test, push commits, rotate X secret
2. **This week:** Address all P0 code issues (rules perms, circuit breakers, webhook idempotency, ENCRYPTION_KEY, IntegrityError handling)
3. **Next week:** P1 code + infra (Cache→Redis, Sentry, Cloudflare, backups, security headers)
4. **Pre-launch week:** Tests for untested paths, staging smoke test, runbook, legal pages
5. **Launch day:** Final pass, deploy, monitor
