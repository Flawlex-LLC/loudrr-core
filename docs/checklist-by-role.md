# Loudrr — Launch Checklist (spreadsheet-ready)

15-day plan as one table. Paste into Google Sheets / Excel.

**Columns:** Day · Role · Category · Priority · Task · Tool · Tool note · Why it matters · Status

> **Grouping philosophy** — adapted from [scan-toolkit-plan.md](./scan-toolkit-plan.md). Instead of running tools one at a time on different days, we **batch similar tools into "scan groups"** so a single sitting catches everything. One run = one report = one triage. Saves days, reduces context-switching.
>
> **Scan groups (run together, not separately):**
> - **Group 1 — Secrets + Deps:** gitleaks + pip-audit + npm audit + osv-scanner
> - **Group 2 — SAST:** semgrep + bandit + njsscan + ESLint security
> - **Group 3 — Code Quality:** ruff + pyright + vulture + django-doctor + jscpd
> - **Group 4 — Django Safety:** `manage.py check --deploy` + django-migration-linter + custom Semgrep rules (mass delete, signal spam, missing idempotency)
> - **Group 5 — Defensive Library Audit:** AST check that every defensive lib is actually used (rules permissions, circuit breakers, FSM, idempotency keys)
> - **Group 6 — Dynamic Scans:** sqlmap + OWASP ZAP + Trivy (on staging only)

---

## Tool inventory (one table, sortable/filterable)

**Columns:** Tool · Type · Stack · Category · Status · Install / Access · What it does · Used in scan group / day

| Tool | Type | Stack | Category | Status | Install / Access | What it does | Used in |
|------|------|-------|----------|:-----:|------------------|--------------|---------|
| ruff | Lint / formatter (CLI) | Python / Django | Code Quality | Installed | already in `backend/requirements.txt` | Python lint + format | Group 3 (Day 7) |
| bandit | SAST (CLI) | Python / Django | Security | Installed | already in `backend/requirements.txt` | Python security lint | Group 2 (Day 12) |
| pytest | Test runner (CLI) | Python / Django | Tests | Installed | already in `backend/requirements.txt` | Test runner | Days 7-9, 14, 15 |
| hypothesis | Test library (in-code) | Python / Django | Tests | Installed | already in `backend/requirements.txt` | Property-based tests | Days 7, 9 |
| django-rules | App library (in-code) | Python / Django | API Hardening | Installed | `pip install rules` (already in reqs) | Permission predicates → use `@has_perm` on endpoints | Day 3 |
| django-fsm | App library (in-code) | Python / Django | Data Integrity | Installed | already in reqs | State machine for waitlist + post status | Day 9 tests |
| django-constance | App library (in-code) | Python / Django | Settings | Installed | already in reqs | Runtime settings via admin (kill switches, lock, modes) | Days 1, 12, 15 |
| django-safedelete | App library (in-code) | Python / Django | Data Integrity | Installed | already in reqs | Soft delete | Day 7 |
| django-auditlog | App library (in-code) | Python / Django | Audit Trails | Installed | already in reqs | Auto-audit model changes | Days 2, 12 |
| pybreaker | App library (in-code) | Python / Django | External APIs | Installed | already in reqs | Circuit breakers around external API calls | Day 4 |
| drf-spectacular | App library (in-code) | Python / Django | API Hardening | Installed | already in reqs | OpenAPI schema → Swagger UI at `/api/docs/` | Day 5 |
| django-structlog | App library (in-code) | Python / Django | Observability | Installed | already in reqs | Structured JSON logging | always on |
| django-q2 | App library (in-code) | Python / Django | Async Tasks | Installed | already in reqs | Async tasks + scheduler (replaces Celery) | Days 12, 14 |
| pre-commit | Git hook (CLI) | Python / Django | Code Quality | Installed | `pre-commit install` | Run hooks (ruff, bandit, gitleaks) before commit | always on |
| ESLint + Next config | Lint (CLI) | Next.js / TS | Code Quality | Installed | already in `frontend/package.json` | JS/TS linting | Days 1, 10 |
| TypeScript | Compiler (CLI) | Next.js / TS | Code Quality | Installed | already in package.json | Static types | always on |
| django-redis | App library (in-code) | Python / Django | Performance | To install | `pip install django-redis` | Redis cache backend (replaces LocMemCache) | Day 5 |
| django-csp | App library (middleware) | Python / Django | Security Headers | To install | `pip install django-csp` | Content Security Policy header | Day 12 |
| sentry-sdk[django] | App library + service | Python / Django | Observability | To install | `pip install "sentry-sdk[django]"` + Sentry account | Backend error tracking | Day 11 |
| pip-audit | CVE scanner (CLI) | Python / Django | Scan Group 1 | To install | `pip install pip-audit` | Python dependency CVE scanner | Group 1 (Day 5) |
| eslint-plugin-tailwindcss | Lint plugin | Next.js / TS | Responsive & A11y | To install | `npm i -D eslint-plugin-tailwindcss` | Lints Tailwind classes incl. responsive prefixes | Days 1, 10 |
| stylelint + config-standard | Lint (CLI) | Next.js / TS | Code Quality | To install | `npm i -D stylelint stylelint-config-standard` | Raw CSS quality | Day 10 |
| @lhci/cli | Perf scanner (CLI) | Next.js / TS | Responsive & A11y | To install | `npm i -D @lhci/cli` | Lighthouse CI for perf + a11y scoring on mobile | Day 10 |
| @playwright/test | Test runner (CLI) | Next.js / TS | Tests | To install | `npm i -D @playwright/test` + `npx playwright install` | Cross-browser viewport + visual tests | Day 10 |
| pa11y-ci | A11y scanner (CLI) | Next.js / TS | Responsive & A11y | To install | `npm i -D pa11y-ci` | WCAG accessibility scanner | Day 10 |
| @sentry/nextjs | App library + service | Next.js / TS | Observability | To install | `npx @sentry/wizard@latest -i nextjs` + Sentry account | Frontend error tracking | Day 11 |
| react-error-boundary | App library (in-code) | Next.js / TS | Frontend UX | To install | `npm i react-error-boundary` | Stops one crashed component from killing the whole app | Day 11 |
| Cypress | Test runner (CLI) | Next.js / TS | Tests | To install | `npm i -D cypress` | E2E browser test runner | Day 14 |
| openapi-typescript | Codegen (CLI) | Next.js / TS | Code Quality | To install | `npm i -D openapi-typescript` | Auto-generate TS types from OpenAPI schema | Day 7 |
| semgrep | SAST (CLI) | Polyglot | Scan Group 2 | To install | `pip install semgrep` | Static analysis (deeper than bandit; custom rules possible) | Group 2 (Day 12) |
| njsscan | SAST (CLI) | Next.js / TS | Scan Group 2 | To install | `pip install njsscan` | Node/JS SAST | Group 2 (Day 12) |
| vulture | Dead-code scanner (CLI) | Python / Django | Scan Group 3 | To install | `pip install vulture` | Finds unused Python code | Group 3 (Day 7) |
| pyright | Type checker (CLI) | Python / Django | Scan Group 3 | To install | `npm i -g pyright` (yes, pyright ships via npm) | Strict Python type checker (catches wrong attr / arg / None) | Group 3 (Day 7) |
| jscpd | Dup detector (CLI) | Polyglot | Scan Group 3 | To install | `npm i -g jscpd` | Cross-language duplicate code finder | Group 3 (Day 7) |
| django-doctor | Lint (CLI) | Python / Django | Scan Group 3 | To install | `pip install django-doctor` | Catches Django anti-patterns + slow query patterns | Group 3 (Day 7) |
| django-migration-linter | Lint (CLI) | Python / Django | Scan Group 4 | To install | `pip install django-migration-linter` | Flags unsafe migrations (column drops, non-null adds) | Group 4 (Day 12) |
| gitleaks | Secret scanner (CLI) | Polyglot | Scan Group 1 | To install | https://github.com/gitleaks/gitleaks (download binary) | Scans git history for leaked secrets | Group 1 (Day 5) |
| trufflehog | Secret scanner (CLI) | Polyglot | Scan Group 1 | To install | `brew install trufflehog` or download | Verified secret detection (live API check) | Group 1 (Day 5) |
| osv-scanner | CVE scanner (CLI) | Polyglot | Scan Group 1 | To install | https://google.github.io/osv-scanner/ | Cross-ecosystem CVE scanner (Dockerfiles, lockfiles) | Group 1 (Day 5) |
| Trivy | Container scanner (CLI) | Docker | Scan Group 6 | To install | https://trivy.dev/ | Docker image CVE scanner | Group 6 (Day 14) |
| sqlmap | DAST (CLI) | Polyglot | Scan Group 6 | To install | `pip install sqlmap` | SQL injection scanner | Group 6 (Day 14) |
| OWASP ZAP | DAST (GUI/CLI) | Polyglot | Scan Group 6 | To install | https://www.zaproxy.org/download/ | Dynamic web app security scanner | Group 6 (Day 14) |
| Locust | Load test (CLI) | Python | Performance | To install | `pip install locust` | Load testing | Day 14 |
| pg_dump / pg_restore | DB CLI | Postgres | Backups | Comes with Postgres | bundled with `postgresql-client` | Backup + restore | Days 6, 15 |
| openssl | Crypto CLI | Polyglot | Security | Pre-installed | preinstalled on most systems | Generate webhook secrets etc. | Day 13 |
| Sentry.io | External service | Polyglot | Observability | Sign up | sentry.io (free 5k events/mo) | Error tracking + native Telegram Alerts Bot | Day 11 |
| UptimeRobot.com | External service | Polyglot | Observability | Sign up | uptimerobot.com (free 50 monitors @ 5 min) | Health-check pings + Telegram alerts | Day 11 |
| Backblaze B2 | External service | Polyglot | Backups | Sign up | backblaze.com/b2 (free 10 GB, then $0.005/GB) | S3-compatible off-site backup storage | Day 6 |
| Cloudflare | External service | Polyglot | Cloudflare & Edge | Sign up | cloudflare.com (free) | DNS + DDoS + SSL + edge cache | Day 12 |
| Hetzner Cloud Console | External service | Polyglot | Infrastructure | Sign up | console.hetzner.cloud | VPS + monitoring + alerts | pre-week-1 |
| Coolify | Self-hosted service | Polyglot | Coolify & Deploy | Already running | install on Hetzner VPS | App orchestration + scheduled backups + rollback | Days 6, 13, 15 |
| PgBouncer | Self-hosted service | Postgres | DB Pooling | One-click in Coolify | Coolify > Add Service > PgBouncer | Connection pooler for Postgres | Day 13 |
| termly.io (optional) | External service / generator | Polyglot | Legal Pages | Sign up (free starter) | termly.io | Free Privacy Policy + ToS templates to customize | Day 6 |
| Twitter Developer Portal | External service | — | Security | Sign up | developer.twitter.com | OAuth credentials + secret rotation | Day 5 |
| Telegram (bot + groups) | External service | — | Observability | Already have | telegram + your bot token | Ops alert channels (Errors, Uptime, App Events) | Day 11 |

---

## Main task table

| Day | Role | Category | Pri | Task | Tool | Tool note | Why it matters | Status |
|----:|------|----------|:---:|------|------|-----------|----------------|:------:|
| 1 | Frontend | Frontend UX | P0 | Fix the waitlist card design and the approval card design | @vercel/og + browser | Edit `frontend/app/api/cards/*/route.tsx`, preview in browser | First impression on every new user; lazy design = lazy product |  |
| 1 | Backend | Onboarding | P0 | Fix the onboarding flow (waitlist application → approval → OAuth verification on the onboarding page) | Manual | — | Broken first-mile = user drops off before ever using the app |  |
| 1 | Backend | Bot Safety | P0 | Make sure the bot can never send duplicate notifications | Django UniqueConstraint | Add to OutboxEvent model + migration; catch IntegrityError in OutboxService | Prevents the #1 reputation risk: spamming users |  |
| 1 | Backend | Bot Safety | P0 | Add an emergency kill switch to pause all notifications | django-constance | Add `NOTIFICATIONS_PAUSED` flag, check in OutboxService.process_event() | Lets you stop a bug in 5 seconds without a redeploy |  |
| 1 | Backend | Bot Safety | P0 | Make sure duplicate Telegram updates aren't processed twice | django-redis | Use Redis SET with 24h TTL keyed by update_id in webhook view | Telegram retries the same update; without dedup, /start runs 3x |  |
| 1 | Frontend | Responsive & A11y | P1 | Install responsive lint stack | eslint-plugin-tailwindcss, stylelint, Playwright, @lhci/cli, pa11y-ci | All npm dev-deps; see Tool Inventory above | Catches mobile bugs at write-time, not after user complaints |  |
| 1 | Frontend | Responsive & A11y | P1 | Run the lint and fix any responsive class issues | eslint-plugin-tailwindcss | `npx eslint app --max-warnings 0` | Cheap win; eliminates entire bug class |  |
| 1 | Frontend | Frontend UX | P1 | Audit design consistency across pages and note inconsistencies (don't migrate to shadcn yet — just list) | Manual + browser | Take screenshots, list mismatches in a doc | Inventory before refactor; full migration is a separate sprint |  |
| 2 | Backend | Bot Safety | P0 | Build a "notification sent" audit log (who got what, when) | Django model | New `NotificationSent` model + auditlog.register() | Last line of defense + permanent record for support |  |
| 2 | Backend | Bot Safety | P1 | Add a recipient whitelist so dev tests never accidentally ping real users | django-environ | Read `NOTIFICATION_RECIPIENT_WHITELIST` env var; check before send | Prevents the "oops sent test card to all approved users" disaster |  |
| 2 | Security | Security | P0 | Make ENCRYPTION_KEY mandatory and document how to generate one | Python `secrets` | `python -c "import secrets; print(secrets.token_urlsafe(32))"` | Prevents prod from crashing on first request |  |
| 3 | Backend | API Hardening | P0 | Add permission checks to every endpoint that changes data | django-rules | Use `@has_perm('app.permission_name')` on view methods | Currently anyone hitting your API can mutate data |  |
| 3 | Backend | API Hardening | P0 | Make API errors return friendly messages instead of raw 500s | DRF exception handler | Custom `EXCEPTION_HANDLER` in REST_FRAMEWORK settings + try/except IntegrityError | 500s leak stack traces and look amateur |  |
| 4 | Backend | External APIs | P0 | Protect external API calls (Twitter, TweetScout, Telegram) with circuit breakers | pybreaker | Wrap calls in `twitter_breaker.call(...)` etc. (already defined in `core/circuit_breakers.py`) | One flaky upstream API won't cascade and tank your whole app |  |
| 4 | Backend | Referrals | P0 | Test referral via Telegram deep link (ref_CODE) captures the code | pytest + pytest-django | `pytest backend/core/tests/test_referrals.py -k deep_link` | Referral system is your growth engine; can't silently break |  |
| 4 | Backend | Referrals | P0 | Test self-referral is blocked | pytest | Test the DB constraint + signal | Otherwise users farm themselves for referral karma |  |
| 4 | Backend | Referrals | P1 | Test referral codes are unique (no collisions across many users) | hypothesis | Property-based: generate 10k codes, assert all unique | Collision = wrong user gets credit |  |
| 4 | Backend | Referrals | P0 | Verify referral counts actually increment when admin approves a user | pytest-django Client | Use admin Client to approve, assert count == prev+1 | Otherwise referrals silently don't pay out |  |
| 5 | Backend | Bot Safety | P1 | Rate-limit Telegram notifications to 5 per hour per user | django-redis | `r.incr(f"notif:{tg_id}:{hour}")` with TTL=3600; reject if > 5 | Worst-case bug spam is bounded, not infinite |  |
| 5 | Backend | API Hardening | P1 | Document remaining API endpoints in the OpenAPI schema | drf-spectacular | `@extend_schema(...)` decorators; browse at `/api/docs/` | Future devs / yourself in 6 months will thank you |  |
| 5 | Frontend | Frontend UX | P1 | Fix any UI bugs that came out of the audit | Manual | — | Polish the rough edges before users see them |  |
| 5 | Security | Security | P0 | Rotate the X Client Secret (was pasted in chat earlier) | X Developer Portal | developer.twitter.com → your app → Keys → Regenerate Client Secret | Pasted secrets are compromised secrets |  |
| 5 | Security | Scan Group 1 | P0 | **Run Group 1 scan: Secrets + Deps** (find any other leaked secrets + outdated deps with CVEs) | gitleaks + pip-audit + npm audit + osv-scanner | `gitleaks detect --source .` then `pip-audit` then `cd frontend && npm audit --audit-level=high` | One scan covers all secret + dependency risks; do the triage once |  |
| 5 | Infra | Performance | P1 | Switch the cache from in-memory to Redis | django-redis | `CACHES = {'default': {'BACKEND': 'django_redis.cache.RedisCache', ...}}` | LocMem cache breaks across multiple workers in prod |  |
| 6 | Infra | Backups & Recovery | P0 | Set up daily Postgres backups to off-site storage | Coolify scheduled task + Backblaze B2 | Coolify > Service > Schedule: `pg_dump | gzip | b2 upload` | Server dies = company dies without off-site backups |  |
| 6 | Infra | Observability | P0 | Set Hetzner disk alert at 75% | Hetzner Cloud Console | Project > Alerts > Add → Disk usage > 75% | Disk full = Postgres stops writes = corruption risk |  |
| 6 | Infra | Observability | P1 | Set Hetzner memory and CPU alerts | Hetzner Cloud Console | Same as above; CPU > 90% sustained 10min, RAM > 85% | Catches degradation before users notice |  |
| 6 | Infra | Backups & Recovery | P0 | Take a manual backup and verify it landed in B2 | pg_dump + b2 CLI | `pg_dump <db> | gzip | b2 upload-file ...` then check B2 console | Backups you've never seen succeed are not backups |  |
| 6 | Infra | Backups & Recovery | P0 | Do a restore drill — actually restore the backup somewhere and check it works | pg_restore | `b2 download-file ... | gunzip | psql <test_db>` then run smoke queries | Backups you've never restored are not backups |  |
| 6 | Frontend | Legal Pages | P0 | Build the Privacy Policy page | Manual / termly.io generator | Free template at termly.io as starting point, customize | Legal requirement; X Dev Portal will revoke without one |  |
| 6 | Frontend | Legal Pages | P0 | Build the Terms of Service page | Manual / termly.io generator | Same generator, ToS variant | Legal cover; required by many platforms |  |
| 6 | Ops | Operations | P0 | Write a one-page runbook (what to do when something breaks) | Markdown | `docs/runbook.md` — sections: "site down", "backup restore", "rollback" | At 3am, you won't remember; future-you needs this |  |
| 7 | Backend | Data Integrity | P0 | Make user / post / engagement deletes recoverable (soft delete) | django-safedelete | Inherit `SafeDeleteModel(SOFT_DELETE_CASCADE)`; existing migration pattern | One bad query = data gone forever without this |  |
| 7 | Backend | Data Integrity | P1 | Wrap every API request in a database transaction by default | Django setting | `DATABASES['default']['ATOMIC_REQUESTS'] = True` | Half-applied changes = corrupt state; this prevents it |  |
| 7 | Backend | Karma System | P0 | Test earning karma respects the daily cap (boundary cases at exactly the limit) | pytest + pytest-django | Test at cap-1, cap, cap+1 | Karma is money-equivalent; cap bug = exploit |  |
| 7 | Backend | Karma System | P0 | Test spending karma fails when balance is insufficient | pytest | Test that spend > balance raises and doesn't deduct | Negative balance = users spending free karma |  |
| 7 | Backend | Audit Trails | P0 | Test admin grant / revoke karma is audited | pytest + auditlog API | Trigger admin action, assert auditlog.LogEntry exists | If an admin acts maliciously, you need a paper trail |  |
| 7 | Backend | Karma System | P0 | Test that two users earning + spending at the same moment doesn't break balances (race condition) | pytest + threading or pytest-asyncio | Spawn N parallel earn() calls, verify final balance is correct | The bug nobody can reproduce on their laptop |  |
| 7 | Backend | Karma System | P1 | Test karma decimal precision — no rounding leaks across many small earns | hypothesis | Property-based: 10k random small earns; sum should equal balance | Tiny rounding errors compound into real money |  |
| 7 | Backend | Karma System | P1 | Verify the "earned ≥ spent" rule holds even under stress | hypothesis | Generate random sequences of earn/spend, assert constraint never violated | DB constraint exists; this confirms code respects it under load |  |
| 7 | Backend | Data Integrity | P1 | Audit and fix any save() calls that aren't safely wrapped | ripgrep + manual | `rg "\.save\(" backend/` and review each context | Plugs the holes in your transaction guarantees |  |
| 7 | Backend | Scan Group 3 | P1 | **Run Group 3 scan: Code Quality** (dead code, types, lint, dup) + triage | ruff + pyright + vulture + django-doctor + jscpd | `ruff check && pyright && vulture backend/ --min-confidence 80 && python manage.py doctor && jscpd backend/` | Single batch finds all "code smells"; triage once, not 5 times |  |
| 7 | Frontend | Frontend UX | P1 | Update API types if backend changes break frontend types | openapi-typescript | `npx openapi-typescript http://localhost:8000/api/schema/ -o lib/api-types.ts` | Type errors at compile time vs runtime crashes |  |
| 7 | Ops | Operations | P0 | Write a migration checklist (preflight + rollback) | Markdown | `docs/migration-checklist.md` | Bad migration = data loss; checklist prevents the rush mistakes |  |
| 8 | Backend | Tests | P0 | Write tests for the X OAuth flow (success + mismatch + admin actions) | pytest + pytest-django + responses | Mock X OAuth callbacks with `responses` library | Verification is your trust layer; can't silently break |  |
| 8 | Backend | Engagement Anti-Fraud | P0 | Test that verification fails when user didn't actually reply | pytest + responses | Mock Twitter API replies; assert verified=False | Without this, users earn karma for nothing |  |
| 8 | Backend | Engagement Anti-Fraud | P0 | Test honesty score drops correctly on failed verification | pytest | Assert score change matches `ceil(failures/2)` | Fraud penalty must actually apply |  |
| 8 | Backend | Engagement Anti-Fraud | P0 | Test minimum session duration is enforced (no instant claims) | pytest + freezegun | `freeze_time` to control clock during test | Stops bots from spam-clicking for free karma |  |
| 8 | Backend | Engagement Anti-Fraud | P0 | Test cannot engage with own post | pytest | Assert IntegrityError or 400 response | Otherwise users self-engage to drain their own escrow back to themselves |  |
| 8 | Backend | Engagement Anti-Fraud | P0 | Test cannot engage the same post twice | pytest | Hit endpoint twice, assert second is rejected | Double-claim = double karma exploit |  |
| 8 | Backend | Engagement Anti-Fraud | P1 | Test random audit spot-checks fire at the configured probability | pytest + mocked random | Patch random.random() to test boundaries | Defends against systemic gaming |  |
| 8 | Backend | Engagement Anti-Fraud | P1 | Test verification batch handles partial failures (some pass, some fail) | pytest + responses | Mix mock responses to fail some, succeed others | One failure shouldn't sink the whole batch |  |
| 8 | Backend | Bot Behavior | P0 | Test /start without referral shows correct welcome | pytest + python-telegram-bot test fixtures | Use Application's test mode | The first thing every user sees |  |
| 8 | Backend | Bot Behavior | P0 | Test /start with ref_CODE captures and stores referral | pytest | Same; verify referral_code_used set | If this breaks, your growth loop dies silently |  |
| 8 | Backend | Bot Behavior | P0 | Test webhook rejects requests with wrong/missing secret | pytest-django Client | POST to /api/telegram/webhook/ without/with bad secret header | Otherwise anyone on the internet can post fake updates to your bot |  |
| 8 | Backend | Bot Behavior | P1 | Test /launch produces a pinnable message with correct mini-app button | pytest + bot fixtures | Assert message has WebAppInfo button with correct URL | Used in groups for promotion |  |
| 8 | Backend | Admin Panel | P0 | Test "approve selected waitlist entries" creates User + queues notification + queues TweetScout fetch | pytest-django Client (admin login) | `client.post('/admin/.../changelist/', {'action': 'approve_entries', '_selected_action': [...]})` | Approval is your most-used admin action |  |
| 8 | Backend | Admin Panel | P0 | Test "reject selected waitlist entries" sets correct status (no User created) | pytest-django Client | Same pattern | Otherwise rejected users still get accounts |  |
| 8 | Backend | Admin Panel | P0 | Test "approve XVerificationRequest" updates user's X handle + marks verified + clears pending | pytest-django Client | Trigger approval action; assert User fields updated | Half-applied verification = stuck user |  |
| 8 | Backend | Admin Panel | P0 | Test "reject XVerificationRequest" deletes User + creates new waitlist entry with carry-forward flag | pytest-django Client | Trigger reject; assert User gone, new WaitlistEntry exists | Complex flow, easy to break, must work |  |
| 8 | Backend | Admin Panel | P0 | Test "ban users" sets is_banned=True AND clears is_whitelisted (so DB constraint passes) | pytest-django Client | Trigger ban; assert both flags set correctly | Existing bug source — constraint blocks naive ban |  |
| 8 | Backend | Admin Panel | P0 | Test "whitelist users" action | pytest-django Client | Same | Counterpart to ban; same risk profile |  |
| 8 | Backend | Admin Panel | P1 | Test grant-karma admin action creates a Transaction with idempotency_key | pytest-django Client | Trigger twice; assert only one transaction exists | Otherwise admin double-clicks = double karma |  |
| 8 | Backend | Admin Panel | P1 | Test revoke-karma admin action handles negative-balance edge case | pytest-django Client | Try to revoke > balance; assert it caps or rejects | Don't let admin push user below zero |  |
| 8 | Backend | Admin Panel | P1 | Test PRODUCTION_LOCK blocks dangerous admin actions when ON | django-constance + pytest | Set lock=True via Constance; assert action returns warning | Safety brake against accidental clicks in prod |  |
| 8 | Ops | Tests | P0 | Run the full backend test suite | pytest | `pytest backend/ -x --tb=short` | Confirm nothing regressed during the test-writing day |  |
| 9 | Backend | Tests | P0 | Write tests for outbox events (retry + dedup + state changes) | pytest | Test mark_failed → retry_failed_outbox_events resets to PENDING | Outbox is your notification reliability layer |  |
| 9 | Backend | Tests | P0 | Write tests for waitlist approve→reject rollback | pytest + django-fsm transitions | Trigger approve, then reject, assert state correct | Edge case that bites in prod, never in dev |  |
| 9 | Backend | Posts & Escrow | P0 | Write tests for post auto-completion + auto-expiry | pytest + freezegun | Freeze time, age post past expiry, run task, assert refund | Money flow into and out of escrow must be exact |  |
| 9 | Backend | Tier & Streak | P0 | Test tier calculation at boundary scores (just-below and just-above each tier) | pytest | Parametrize with each boundary value | Off-by-one at tier boundary = wrong multiplier |  |
| 9 | Backend | Tier & Streak | P0 | Test tier multiplier is correctly applied to earned karma | pytest | Mock TweetScout score per tier, earn karma, verify amount | Tier system is the core game mechanic |  |
| 9 | Backend | Tier & Streak | P1 | Test streak increments on first engagement of day, resets after missing a day | pytest + freezegun | Travel time forward by 1, 2, 3 days; assert streak | Streaks drive retention; bug = users stop caring |  |
| 9 | Backend | Tier & Streak | P1 | Test honesty score is bounded 0–50, never escapes | hypothesis | Random sequences of penalties + recoveries; assert always in range | DB constraint check; confirms code respects it |  |
| 9 | Backend | Posts & Escrow | P0 | Test post submission locks karma in escrow exactly equal to cost | pytest | Submit post, assert user.credits dropped by exactly POST_COST | Mismatch = either creator pays nothing or loses extra |  |
| 9 | Backend | Posts & Escrow | P0 | Test escrow deducts atomically on each verified engagement | pytest + threading | Concurrent verifications, assert escrow stays non-negative | Race condition here = double-payment or under-payment |  |
| 9 | Backend | Posts & Escrow | P0 | Test post auto-completes when escrow hits zero | pytest | Drain escrow to 0, assert FSM transition fires | Otherwise active posts with zero escrow waste user attention |  |
| 9 | Backend | Posts & Escrow | P0 | Test expired post is cancelled and exact remaining escrow refunded | pytest + freezegun | Age post past POST_EXPIRY_HOURS, run task, assert refund == remaining | Refund bugs cost real money or make users lose trust |  |
| 9 | Backend | Posts & Escrow | P0 | Test cannot submit a post without sufficient karma | pytest | Set user.credits = 0, attempt submit, assert 400 | Free posts = bypass entire economy |  |
| 9 | Backend | Posts & Escrow | P1 | Test that user cannot submit someone else's tweet (tweet ownership check) | pytest + responses | Mock Twitter API to return different author_id, assert 400 | Stops impersonation / hijacking other people's content |  |
| 9 | Backend | LOUD UGC | P0 | Test daily LOUD submission limit per user + per project | pytest + freezegun | Submit limit+1 in a day, assert last is rejected | Spam prevention |  |
| 9 | Backend | LOUD UGC | P0 | Test cannot submit duplicate LOUD tweet IDs | pytest | Submit same tweet_id twice, assert IntegrityError caught | Same tweet rewarded twice = exploit |  |
| 9 | Backend | LOUD UGC | P0 | Test LOUD points calculation matches TweetScout score / configured divisor | pytest | Set divisor via Constance, mock score, assert points | Wrong points = wrong leaderboard |  |
| 9 | Backend | LOUD UGC | P1 | Test LOUD leaderboard updates atomically when many submissions land at once | pytest + threading | Concurrent submissions, assert leaderboard total correct | Concurrent updates can lose points without locking |  |
| 9 | Backend | LOUD UGC | P1 | Test soft-deleted LOUD submissions don't count in leaderboard | pytest | Soft-delete a submission, assert leaderboard excludes it | Soft delete must respect leaderboard semantics |  |
| 9 | Backend | Tests | P1 | Write tests for campaign winner selection | pytest | Test random / weighted_xp / weighted_score paths | Winners are public; bug = embarrassing public-facing error |  |
| 9 | Backend | Tests | P1 | Write tests for concurrent engagement claims (race conditions) | pytest + threading | Same user, multiple parallel claims; assert exactly-once credit | The class of bugs that only show up at scale |  |
| 10 | Frontend | Frontend UX | P0 | Test all main tabs (feed, engage, post, profile, LOUD) load and switch cleanly | Playwright | `npx playwright test app-tabs.spec.ts` | Core navigation; broken = unusable app |  |
| 10 | Frontend | Frontend UX | P0 | Test karma balance updates after earning | Playwright | Mock API; click engage; assert balance updated | Users not seeing their karma = users think it's broken |  |
| 10 | Frontend | Frontend UX | P0 | Test feed excludes own posts and already-engaged posts | Playwright | Mock feed API; assert excluded items absent | Otherwise feed feels stale and rewards self-engagement |  |
| 10 | Frontend | Frontend UX | P0 | Test pending claim count + verification trigger UI work | Playwright | Trigger 10+ engagements; assert verify button appears | Core earning loop visibility |  |
| 10 | Frontend | Frontend UX | P1 | Test pull-to-refresh on the feed | Playwright (mobile emulation) | `page.touchscreen.swipe()` from top | Standard mobile expectation |  |
| 10 | Frontend | Frontend UX | P1 | Test error states gracefully when backend is down | Playwright | Mock 500 response; assert error UI shown, not crash | Don't show users a white screen during outages |  |
| 10 | Frontend | Frontend UX | P1 | Test Telegram MainButton appears/disappears on the right screens | Playwright | Mock window.Telegram.WebApp; assert MainButton state | Telegram-specific UX detail that breaks easily |  |
| 10 | Frontend | Responsive & A11y | P0 | Run ESLint with strict mode, fix all responsive issues | eslint-plugin-tailwindcss | `npx eslint app --ext .tsx --max-warnings 0` | Catches missing breakpoints automatically |  |
| 10 | Frontend | Responsive & A11y | P0 | Test every page on mobile (320px), tablet, and desktop screen sizes | Playwright viewport matrix | Set `use: { viewport: { width: 320, ... } }` per project | Mini app users are 90% on mobile |  |
| 10 | Frontend | Responsive & A11y | P0 | Test the waitlist wizard works smoothly on the smallest mobile screen | Playwright (320px) | Step through wizard, assert no horizontal scroll | Most punishing viewport; if this works, all sizes work |  |
| 10 | Frontend | Responsive & A11y | P0 | Test the Connect X / Mismatch / Pending Review screens on mobile | Playwright (375px) | Same idea | Critical onboarding flow on critical viewport |  |
| 10 | Frontend | Responsive & A11y | P1 | Run Lighthouse — target 90+ performance, 95+ accessibility on mobile | @lhci/cli | `npx lhci autorun --collect.url=http://localhost:3000` | Slow apps lose users in 3 seconds |  |
| 10 | Frontend | Responsive & A11y | P1 | Run an accessibility scan and fix the top issues | pa11y-ci | `npx pa11y-ci http://localhost:3000/ http://localhost:3000/app` | Required for some user groups; also good SEO signal |  |
| 11 | Frontend | Observability | P0 | Add Sentry to the frontend | @sentry/nextjs | `npx @sentry/wizard@latest -i nextjs` | Without this, you don't know users are seeing errors |  |
| 11 | Frontend | Frontend UX | P1 | Add a React error boundary so a component crash doesn't kill the whole app | react-error-boundary | `npm i react-error-boundary` then wrap layout.tsx | One bad component = white screen for the whole user without this |  |
| 11 | Infra | Observability | P0 | Set up Sentry projects for backend and frontend | sentry.io | Create org → 2 projects: loudrr-backend (Django), loudrr-frontend (Next.js) | The eyes of your prod system |  |
| 11 | Infra | Observability | P0 | Add Sentry SDK to the backend | sentry-sdk[django] | `pip install "sentry-sdk[django]"`, init in settings.py | Backend errors must be captured |  |
| 11 | Infra | Observability | P0 | Send a test error and verify it arrives in Sentry | Manual | `raise Exception("test")` in a view | Confirms the wire actually works |  |
| 11 | Infra | Observability | P0 | Set up UptimeRobot to ping the health endpoint every 5 minutes | UptimeRobot.com | Add HTTP(s) monitor → `https://loudrr.com/health/` → 5-min interval | First line: is the site even up? |  |
| 11 | Infra | Observability | P0 | Wire UptimeRobot alerts to the ops Telegram channel | UptimeRobot Telegram integration | UptimeRobot Settings → Add Alert Contact → Telegram (built-in wizard) | You shouldn't learn from users that prod is down |  |
| 11 | Infra | Observability | P1 | Set Sentry alerts for spike in errors / failed jobs / failed notifications | Sentry alert rules | Sentry → Alerts → Create rule → action: send to Telegram | Active alerting beats reactive checking |  |
| 11 | Ops | Observability | P0 | Create "Loudrr • Errors" Telegram group, wire to Sentry's native Telegram bot | Sentry Telegram Alerts Bot | Sentry → Settings → Integrations → Telegram Alerts Bot | Errors visible in real time during your day |  |
| 11 | Ops | Observability | P0 | Create "Loudrr • Uptime" Telegram group, wire to UptimeRobot | UptimeRobot Telegram | Built-in integration, no custom code | Binary down/up signal, separate channel for clarity |  |
| 11 | Ops | Observability | P1 | Create "Loudrr • App Events" Telegram group, post curated events from your bot | Custom helper (your bot) | Add `core/services/ops_alerts.py` helper that posts via Bot API | Curated business events — your morning-coffee channel |  |
| 12 | Security | Audit Trails | P0 | Spot-check the audit log captures credit changes, admin actions, and status transitions | django-auditlog admin | `/admin/auditlog/logentry/` filter by model | Confirms forensic trail works when you'll need it most |  |
| 12 | Security | Admin Panel | P0 | Test non-staff users get 403 / redirect on /admin/ | pytest-django Client | Login as non-staff, request /admin/, assert redirect | Otherwise anyone with creds = total compromise |  |
| 12 | Security | Admin Panel | P0 | Test staff users without group perms can only see allowed models | pytest-django + django Group | Create staff w/ limited perms, assert filtered sidebar | Defense in depth on admin permissions |  |
| 12 | Security | Admin Panel | P0 | Test admin login enforces strong password | Django auth validators | `AUTH_PASSWORD_VALIDATORS` in settings (built-in) | Weak admin = entire system compromised |  |
| 12 | Security | Admin Panel | P0 | Confirm /admin/ is HTTPS only | Cloudflare + Django middleware | `SECURE_SSL_REDIRECT = True` + Cloudflare Always Use HTTPS | Plain HTTP = sniffable admin sessions |  |
| 12 | Backend | Settings | P1 | Test admin > Constance > change POST_COST → next post submission uses new value | django-constance | Change in admin, submit post, assert new escrow amount | Confirms dynamic config actually applies |  |
| 12 | Backend | Settings | P1 | Test admin > Constance > toggle MAINTENANCE_MODE blocks user actions | django-constance + pytest | Toggle, hit endpoint, assert 503 | Emergency stop must work |  |
| 12 | Backend | Settings | P1 | Test admin > django_q > Schedule: all 5 cron schedules visible | Manual + django-q admin | `/admin/django_q/schedule/` should show 5 rows | Confirms scheduled jobs are registered (not silently missing) |  |
| 12 | Backend | Settings | P1 | Test admin > django_q > Failed Tasks: clicking a failed task shows the stack trace | Manual + django-q admin | `/admin/django_q/failure/` | Debugging visibility for async jobs |  |
| 12 | Security | Rate Limiting | P0 | Verify waitlist registration rate limit (5/hr/IP) actually blocks abuse | curl/httpie loop | Send 6+ requests, assert 6th is 429 | Otherwise spam fills your waitlist with junk |  |
| 12 | Security | Rate Limiting | P0 | Verify LOUD submission rate limit (10/min/user) actually blocks abuse | curl/httpie loop | Same; 11th request = 429 | Spam protection on the user-generated entry point |  |
| 12 | Security | Headers & SSL | P0 | Set Cloudflare to strict SSL | Cloudflare dashboard | SSL/TLS → Overview → "Full (strict)" | Half-encrypted = leaks data |  |
| 12 | Security | Headers & SSL | P1 | Turn on Cloudflare Bot Fight Mode for /admin paths | Cloudflare dashboard | Security → Bots → Bot Fight Mode ON | Admin is the highest-value target; deserves extra defense |  |
| 12 | Security | Headers & SSL | P0 | Add Django security middleware (HTTPS redirect, secure cookies, HSTS, X-Frame-Options) | Django built-in | Set in settings.py: SECURE_SSL_REDIRECT, SESSION_COOKIE_SECURE, CSRF_COOKIE_SECURE, SECURE_HSTS_SECONDS=31536000 | Free wins; covers OWASP basics |  |
| 12 | Security | Headers & SSL | P1 | Add a Content Security Policy header | django-csp | `pip install django-csp`; configure in settings | Defense against injected scripts |  |
| 12 | Security | Scan Group 2 | P0 | **Run Group 2 scan: SAST** (semgrep + bandit + njsscan + ESLint security) + triage | semgrep + bandit + njsscan + ESLint | `semgrep --config=auto backend/ && bandit -r backend/ -ll && njsscan frontend/` | One SAST batch covers OWASP Top 10 patterns; bandit + semgrep + njsscan find different things |  |
| 12 | Security | Scan Group 4 | P0 | **Run Group 4 scan: Django Safety** (deploy check + migration linter + custom rules for mass-delete / signal spam / missing idempotency) | Django check + django-migration-linter + custom Semgrep rules | `python manage.py check --deploy && python -m django_migration_linter --include-name-contains migrations` + run custom rules from scan-toolkit-plan.md §4b | This is where the *actual disasters* are caught (mass deletes, notification spam) |  |
| 12 | Security | Scan Group 5 | P0 | **Run Group 5 scan: Defensive Library Audit** (every defensive lib actually used in code, not just installed) | Custom AST checks (per scan-toolkit-plan.md §5c) | Walks AST and verifies: every viewset has permission_classes, every credit mutation goes through CreditService, every external HTTP wrapped in circuit breaker, etc. | Catches "library installed but bypassed in new code" — the silent decay |  |
| 12 | Infra | Cloudflare | P1 | Put Cloudflare in front of loudrr.com (DDoS + SSL proxied) | Cloudflare dashboard | Add domain → orange-cloud proxy enabled | Free DDoS, free CDN, free SSL |  |
| 12 | Infra | Cloudflare | P0 | Configure Cloudflare to bypass cache on /api/* paths | Cloudflare Page Rules | Pattern: `*loudrr.com/api/*` → Cache Level: Bypass | Cached API responses = users seeing wrong data |  |
| 13 | Security | Security | P0 | Generate a fresh production Telegram webhook secret | openssl | `openssl rand -hex 32` | Don't reuse dev secrets in prod |  |
| 13 | Infra | Coolify & Deploy | P0 | Update Coolify config to use the new django-q2 worker (replaces Celery) | Coolify dashboard | Worker service → Dockerfile.qcluster | Old config won't run; deploy will be broken |  |
| 13 | Infra | Coolify & Deploy | P0 | Set all production environment variables (verify against .env.example) | Coolify env editor | Compare `.env.example` line by line | Missing env var = crash on first request |  |
| 13 | Infra | Coolify & Deploy | P0 | Set production URLs (site, mini app, X OAuth callback, Telegram webhook) | Coolify env editor | SITE_URL, MINIAPP_URL, X_OAUTH_CALLBACK_URL, TELEGRAM_WEBHOOK_URL | Wrong URLs = OAuth/webhook fail silently |  |
| 13 | Infra | Coolify & Deploy | P0 | Update X Developer Portal callback URL to production | X Developer Portal | App → User authentication settings → Callback URI | Otherwise X OAuth redirects nowhere |  |
| 13 | Infra | DB Pooling | P0 | Connect Postgres via PgBouncer for connection pooling | PgBouncer (Coolify one-click) | Add PgBouncer service; transaction mode; pool_size=25, max_client_conn=1000 | Without it, 100 concurrent users exhaust DB connections |  |
| 13 | Infra | Coolify & Deploy | P0 | Deploy to staging environment | Coolify | New stack on `staging.loudrr.com` | Always deploy to staging first; never go directly to prod |  |
| 13 | Infra | Coolify & Deploy | P0 | Run migrations on staging | Django | `python manage.py migrate` (Coolify deploy hook) | Confirm schema changes apply cleanly |  |
| 13 | Infra | Coolify & Deploy | P0 | Register Telegram webhook on staging | Django management command | `python manage.py set_telegram_webhook` | Confirms webhook mode actually works end-to-end |  |
| 13 | Infra | Coolify & Deploy | P0 | Verify staging health check + admin login work | curl + browser | `curl https://staging.loudrr.com/health/` + login at /admin/ | Quick sanity before declaring staging ready |  |
| 13 | Ops | Operations | P0 | Verify Coolify rollback works in under 5 minutes | Coolify built-in | Deployments → previous → "Rollback" button | When prod breaks, rollback speed = downtime length |  |
| 14 | Ops | Smoke Test | P0 | **Admin smoke checklist** (login → sidebar → approve waitlist → reject XVerificationRequest → click 5 FK links → search user by email → filter posts → trigger PRODUCTION_LOCK-blocked action) | Browser + Telegram + Constance | Sit down, do all 7 click-throughs in one focused 30-min session; check off each as you go | Single batched session vs 7 context switches; same coverage |  |
| 14 | Backend | Tests | P1 | Write a load test simulating ~100 concurrent users | Locust | `pip install locust`, write `locustfile.py`, run `locust` | Find the bottleneck before users do |  |
| 14 | Backend | Tests | P1 | Run the load test against staging and watch for issues | Locust + Sentry | `locust --host=https://staging.loudrr.com`; watch Sentry concurrently | Real test, real numbers |  |
| 14 | Frontend | Tests | P1 | Write a Cypress test covering the full happy path | Cypress | `npx cypress open`; one spec for register→approve→connect→engage→claim | Catches frontend regressions automatically |  |
| 14 | Security | Scan Group 6 | P1 | **Run Group 6 scan: Dynamic + Container** (sqlmap + OWASP ZAP + Trivy on the actual staging deploy) + triage | sqlmap + OWASP ZAP + Trivy | `sqlmap -u "https://staging.loudrr.com/api/..." --batch && trivy image loudrr-backend:latest` + ZAP GUI Quick Attack against staging | Dynamic scans catch runtime vulns + container CVEs that static tools miss |  |
| 14 | Security | Scans | P1 | Re-run Groups 1-5 one final time on the latest code (quick sanity) | All static scanners | `cd ~/projects/scan-toolkit && python run.py --project ~/projects/loudrr --groups all` | Last-minute regression check before deploy |  |
| 14 | Ops | Smoke Test | P0 | Run the full smoke test on staging (register → approve → connect X → engage → claim) | Browser + Telegram (manual) | One person, one phone, one hour | The end-to-end happy path; if this works, ship |  |
| 15 | Ops | Launch — Pre-Deploy Gate | P0 | **Pre-deploy checks (1-shot)**: deploy check + migration plan + run all tests + fresh backup + restore-test + audit prod env vars vs .env.example | Django + pytest + pg_dump + Coolify env | `python manage.py check --deploy && python manage.py migrate --plan && pytest backend/ && backup-and-restore script && diff env vars` | Single gate; if any fails, abort — better to delay than ship broken |  |
| 15 | Ops | Launch — Configure | P0 | **Lock down + point DNS**: confirm `LOAD_TEST_MODE=false`, set `PRODUCTION_LOCK=True` in Constance, point Cloudflare DNS at Hetzner | Coolify + Constance admin + Cloudflare | All three are checkbox-style toggles | These are the "no going back" toggles; do them in order |  |
| 15 | Ops | Launch — Deploy | P0 | **Deploy + register webhook + verify telemetry** (deploy via Coolify, run set_telegram_webhook, confirm Sentry receives test error, confirm UptimeRobot green) | Coolify + Django mgmt + Sentry + UptimeRobot | Push deploy button → wait → run webhook command → trigger test error → check dashboards | The actual go-live; verify each layer is alive before moving on |  |
| 15 | Ops | Launch — Smoke + Watch | P0 | **Prod smoke test + first-hour watch**: full happy path on prod (register → approve → connect X → engage → claim) + pin "report bugs" thread + watch Sentry/qcluster/OutboxEvent for 1 hour | Browser + Telegram + Sentry + Coolify logs + admin | Open 4 browser tabs (Sentry, Coolify logs, admin OutboxEvent, mini-app) — eyes on all four | First-hour issues are 80% of launch issues; this is when you earn your launch |  |

---

## One-time setup (do whenever, not tied to a day)

| Day | Role | Category | Pri | Task | Tool | Tool note | Why it matters | Status |
|----:|------|----------|:---:|------|------|-----------|----------------|:------:|
| pre-week-1 | Infra | Infrastructure | P0 | Provision Hetzner VPS (CPX31 or higher for ~1000 concurrent users) | Hetzner Cloud Console | Console > Servers > Add Server | Right-sized hardware = no painful upgrade mid-launch |  |
| pre-week-1 | Infra | Infrastructure | P0 | Configure UFW firewall (only 22, 80, 443 open) | UFW | `ufw allow 22; ufw allow 80; ufw allow 443; ufw enable` | Closed ports = smaller attack surface |  |
| pre-week-1 | Infra | Infrastructure | P0 | Disable password auth, enable SSH keys only | OpenSSH config | Edit `/etc/ssh/sshd_config`: `PasswordAuthentication no` | Stops the constant SSH brute-force from the internet |  |
| pre-week-1 | Infra | Infrastructure | P0 | Install fail2ban | fail2ban | `apt install fail2ban` | Bans IPs that try too many bad logins |  |
| pre-week-1 | Infra | Infrastructure | P0 | Make sure Postgres and Redis aren't exposed publicly | UFW + Coolify network | Only allow from Coolify internal network | DB on the public internet = breached in hours |  |

---

## Daily summary (who's working what day)

| Day | Backend | Frontend | Security | Infra | Ops |
|---:|---------|----------|----------|-------|-----|
| 1 | Bot dedup + kill switch + webhook idempotency + onboarding flow | Card design + lint stack + design audit | — | — | — |
| 2 | Notification audit log + whitelist | — | ENCRYPTION_KEY | — | — |
| 3 | Permissions + friendly errors | — | — | — | — |
| 4 | Circuit breakers + referral tests | — | — | — | — |
| 5 | Rate limit + schema docs | UI bug fixes | Rotate X secret + **Group 1 scan** (secrets + deps) | Cache → Redis | — |
| 6 | — | Privacy + ToS pages | — | Backups + alerts + restore drill | Runbook |
| 7 | Soft delete + karma tests + safe transactions + **Group 3 scan** (code quality batch) | API types | — | — | Migration checklist |
| 8 | X OAuth + engagement + bot + admin action tests | — | — | — | Run test suite |
| 9 | Outbox + tier + escrow + LOUD + campaign + race tests | — | — | — | — |
| 10 | — | **Heavy day**: feature flows + responsive + a11y | — | — | — |
| 11 | — | Sentry FE + ErrorBoundary | — | Sentry BE + UptimeRobot + alerts | TG ops channels |
| 12 | Settings tests | — | **Groups 2+4+5 scan batch** (SAST + Django safety + defensive lib audit) + admin perms + headers + rate limit | Cloudflare proxy | — |
| 13 | — | — | Generate webhook secret | Coolify config + PgBouncer + staging deploy | Rollback test |
| 14 | Load test | Cypress | **Group 6 scan** (sqlmap + ZAP + Trivy on staging) + Groups 1-5 final re-run | — | Admin smoke (1-shot) + full staging smoke |
| 15 | — | — | (covered in Ops launch chunks) | — | **Launch in 4 chunks: pre-deploy gate → configure → deploy → smoke + watch** 🚀 |

---

## How to use in a spreadsheet

1. Copy the main table (headers + rows) and paste into Google Sheets / Excel
2. Freeze the top row, add a dropdown on **Status** (Not started / In progress / Done / Blocked)
3. Color-code by Priority (P0 red, P1 yellow)
4. Filter by **Role** for individual views, by **Day** for today's work, by **Category** to see all tasks of a type, by **Tool** to bulk-tackle everything that uses one tool
5. The **Why it matters** column doubles as your sales pitch when explaining to teammates why this isn't optional
6. The **Tool note** column has the install command or quick how-to so you don't context-switch to the docs every time
</content>
</invoke>