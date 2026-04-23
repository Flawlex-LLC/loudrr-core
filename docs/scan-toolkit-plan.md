# Scan Toolkit Plan

**Status:** Plan — not yet implemented
**Last Updated:** 2026-04-23
**Target:** Reusable, portable scan toolkit for Django + Next.js projects (loudrr-style)

---

## 1. The Honest Starting Point

**Scanners will not give you "zero bugs" or "zero security issues."** Anyone who tells you otherwise is selling something. Before we build anything, you need to internalize what this toolkit can and cannot do, because the plan only makes sense with clear expectations.

### What the research says (2024–2026 data)

- A single SAST tool catches **~35–50% of real production vulnerabilities** in academic benchmarks. ([Endor Labs: False Negatives in SAST](https://www.endorlabs.com/learn/false-negatives-in-sast-hidden-risks-behind-the-noise), [arXiv 2407.16235](https://arxiv.org/abs/2407.16235))
- Stacking 2–3 scanners gets you to **~55–65%** due to overlap — diminishing returns kick in fast.
- Of alerts that *do* fire, **~70–80% are false positives or irrelevant** to the actual vulnerability class.
- Entire bug classes are **effectively 0% covered** by scanners: IDOR, broken object-level auth, business logic flaws, race conditions, missing rate limits, unsafe defaults.
- One 2024 study of 815 real vulnerable commits found **22% triggered zero SAST warnings at all**.

### What this means for Loudrr specifically

The bugs you're most worried about — *"deleting DB stuffs, sending unwanted messages to users, going out of control, business logic errors"* — fall heavily in the **scanner blind spot**.

Concrete examples from your codebase:

| Concern | Covered by scanners? |
|---------|---------------------|
| `Model.objects.all().delete()` slipping in | Yes — custom Semgrep rule (Group 4) |
| Raw SQL with f-strings | Yes — Semgrep `p/django` |
| Sending Telegram messages in a loop over `User.objects.all()` | **Partially** — only with custom AST rules |
| A signal firing `WAITLIST_APPROVED` twice because of a race in `update_or_create` | **No** — needs integration tests |
| User A reading User B's `WaitlistEntry` because a viewset forgot `.filter(user=request.user)` | **No** — needs auth integration tests |
| `CreditService.earn()` double-crediting on webhook retry | **No** — needs idempotency tests + DB constraints |
| Referral self-credit bypass via edge-case code | **No** — needs business logic tests |
| TweetScout score manipulation allowing tier upgrade | **No** — needs domain-specific tests |

**Roughly: scanners will catch ~40% of the bugs that ship. The remaining ~60% — the ones that actually bring down small startups — need tests, code review, observability, and eventually a real pentest.**

This plan builds the 40%-coverage layer, and names explicitly what you must do beyond it.

---

## 2. Design Goals

1. **Portable** — lives outside any single project (`~/projects/scan-toolkit/`), used across all your Django + Next.js repos.
2. **Auto-detecting** — detects `backend/` (Django via `manage.py`) and `frontend/` (Next.js via `next.config.*`) automatically; scans the whole repo without missing folders.
3. **Grouped** — 4 Python scripts, one per group; each group runs independently or all together via `run.py`.
4. **Scanners only** — no paid services (Sentry, Snyk, Jit, etc.) in scope. Pure local tooling.
5. **Reproducible** — pinned tool versions in `install.py`; same scan gives same result.
6. **Single report** — consolidated `summary.md` per run, sorted by severity, with clickable `file:line` references.
7. **Exit codes wired for CI** — `0` clean, `1` issues, `2` critical — so this can move from manual to automated later.

---

## 3. Folder Structure

```
~/projects/scan-toolkit/
├── README.md
├── run.py                          # Entry point: python run.py --project <path> --groups all
├── install.py                      # One-time install, pinned versions
├── requirements.txt                # Python tool versions
├── package.json                    # Node tool versions
├── detect.py                       # Auto-detects Django/Next.js in target project
├── report.py                       # Aggregates per-group JSON into summary.md
├── groups/
│   ├── __init__.py
│   ├── g1_secrets_and_deps.py      # Group 1
│   ├── g2_security_sast.py         # Group 2
│   ├── g3_logic_and_quality.py     # Group 3
│   ├── g4_django_safety.py         # Group 4 (includes custom AST checks)
│   └── g5_defensive_libraries.py   # Group 5 (library presence + actual usage)
├── rules/
│   ├── semgrep/
│   │   ├── django-dangerous.yml    # Custom rules (delete without filter, etc.)
│   │   ├── django-signals.yml      # Signal handler anti-patterns
│   │   ├── django-credits.yml      # Money/credit mutation rules
│   │   └── nextjs-dangerous.yml    # Next.js App Router patterns
│   └── ast/
│       ├── __init__.py
│       └── django_checks.py        # Custom AST walker for things Semgrep can't express
├── config/
│   ├── pyright.json
│   ├── mypy.ini
│   ├── ruff.toml
│   ├── bandit.yaml
│   ├── vulture_whitelist.py        # Pre-seeded Django whitelist (admin actions, signals, etc.)
│   └── jscpd.json
└── reports/
    └── <project-name>-<YYYYMMDD-HHMMSS>/
        ├── summary.md              # Human-readable, severity-sorted
        ├── summary.json            # Machine-readable for CI
        ├── g1_secrets.json
        ├── g2_sast.json
        ├── g3_quality.json
        ├── g4_django.json
        └── g5_defensive_libs.json
```

### Why a separate repo, not in-project

- You said *"mostly Django and Next.js anyway"* — one toolkit, many projects.
- Update tools in one place, every project benefits.
- No coupling to any project's CI. Copy-paste templates always drift.

---

## 4. The 5 Groups

### Group 1 — `g1_secrets_and_deps.py`
**Purpose:** Nothing leaked, nothing poisoned.

| Tool | What it catches | Gotchas |
|------|----------------|---------|
| `gitleaks detect` | Secrets in git history | Entropy rules false-positive on base64 fixtures; use `.gitleaksignore` with path scoping |
| `trufflehog filesystem --only-verified` | Secrets verified live against provider APIs | **Must** use `--only-verified` or you drown in noise |
| `pip-audit` | Python CVEs (OSV-backed, ~98% recall) | Misses zero-days and typo-squatted packages |
| `npm audit --audit-level=high` | Node CVEs | Set threshold to `high` — default noise is unusable |
| `osv-scanner` | Cross-ecosystem CVEs, lockfiles, Dockerfiles | Call-graph reachability is experimental |

**Auto-detect logic:** runs `pip-audit` only if `requirements*.txt` or `pyproject.toml` exists; `npm audit` only if `package.json` exists.

### Group 2 — `g2_security_sast.py`
**Purpose:** Code-level vulnerabilities (injections, XSS, deserialization, weak crypto).

| Tool | What it catches | Gotchas |
|------|----------------|---------|
| `semgrep` with `p/django p/python p/owasp-top-ten p/security-audit p/nextjs p/react p/jwt minusworld.django-xss minusworld.django-sqli` | OWASP Top 10 patterns | `p/django` is thin (~6 rules) — must layer rulesets and add custom ones |
| `bandit -r -ll` | Python-specific SAST | Skip `B101` in test dirs (pytest assert noise) |
| `njsscan` | Node/JS SAST | Hasn't fully kept up with Next.js App Router patterns |
| ESLint with `eslint-plugin-security`, `@next/eslint-plugin-next` | Frontend security lints, Next-specific (CVE-2025-29927 middleware bypass, etc.) | Needs Next.js project's own config extended |

**Key note:** Semgrep OSS has no interprocedural taint tracking. It finds patterns, not dataflow across files. This is why Group 4's custom rules matter.

### Group 3 — `g3_logic_and_quality.py`
**Purpose:** Code correctness. Catches the class of "wrong variable / wrong function / dead branch / duplicate logic" bugs that become prod incidents when two copies of the same logic drift.

| Tool | What it catches | Gotchas |
|------|----------------|---------|
| `ruff check --select=E,F,W,I,N,S,B,C4,UP,DJ,PL,RUF` | Lint + bug-prone patterns (`B` = bugbear); `DJ` = Django-specific | Cherry-pick rule groups, don't enable all |
| `pyright --strict` | Python types (catches wrong attribute, wrong argument, None mishandling) | 2-week tuning period before signal beats noise; django-stubs is mypy-only — needs `django_stubs_ext.monkeypatch()` |
| `mypy --strict` with `django-stubs` + `djangorestframework-stubs` | Django ORM type checking (e.g. `.filter(wrogn_field=)`) | DRF, django-q2, django-filter stubs are incomplete |
| `vulture --min-confidence 80` | Dead code | **Catastrophic FP rate on Django** — ship a whitelist for admin actions, signal receivers, management commands, viewset methods |
| `tsc --noEmit` | TypeScript types | Requires project's own `tsconfig` |
| `jscpd --min-tokens 50` | Duplicate code cross-language | Aggressive ignore patterns for test fixtures/serializers |
| `pylint --load-plugins=pylint_django --errors-only` | Django anti-patterns | Errors-only to avoid style overlap with ruff |

### Group 4 — `g4_django_safety.py`
**Purpose:** Prevent the exact disasters you named — accidental mass deletes, unwanted message spam, missing atomicity, broken idempotency, unsafe migrations.

**This is the group most teams skip because the off-the-shelf tools don't exist. It's also where the highest-value findings live.**

#### 4a. Built-in Django checks (shell-outs)

| Check | Command |
|-------|---------|
| Production config | `python manage.py check --deploy --settings=<prod>` |
| Unapplied model changes | `python manage.py makemigrations --check --dry-run` |
| Unsafe migrations (column drops, non-nullable adds on large tables) | `django-migration-linter` |
| Template linting if used | `djlint --check` |

#### 4b. Custom Semgrep rules in `rules/semgrep/`

| Rule | Why |
|------|-----|
| `.delete()` on unfiltered QuerySet (`Model.objects.delete()`, `.all().delete()`) | **The #1 "deleted DB stuffs" footgun** |
| `.update()` on unfiltered QuerySet | Mass-update disasters |
| Raw SQL with f-string / `.format()` / `%` | SQL injection (`cursor.execute(f"...")`, `.raw(f"...")`, `.extra(where=[f"..."])`) |
| `select_for_update()` outside `transaction.atomic()` | Silently no-ops — the silent race condition trap |
| `@csrf_exempt`, `AllowAny`, `authentication_classes = []` | Unless explicitly whitelisted |
| `mark_safe` / `|safe` on user input | XSS |
| `HttpResponseRedirect(request.GET.get(...))` | Open redirect |
| `post_save` signal without `if created:` guard calling notify/send_mail/bot.send_* | **Prevents duplicate waitlist notifications on every save** |
| `for ... in Model.objects.all(): send_*(...)` | Mass notification spam, rate-limit hell |
| `get_or_create` / `update_or_create` for uniqueness-critical flows | Race window unless backed by DB unique constraint |
| Credit/money mutations without `@transaction.atomic` or `idempotency_key` kwarg | Matches your `CreditService` API |
| `ForeignKey(..., on_delete=CASCADE)` on models named `*AuditLog`, `*History`, `*Transaction` | Prevents losing audit trail |

#### 4c. Custom AST checks in `rules/ast/django_checks.py`

Things Semgrep can't express cleanly (cross-file reasoning, model-level analysis):

- Every model with a `UniqueConstraint` described in docstring actually has it in `Meta.constraints`.
- Every `CreditService.earn/spend/refund` call site passes `idempotency_key`.
- Every view inheriting `MiniAppAuthMixin` actually reaches an authenticated code path.
- Every `WaitlistEntry` FSM transition is inside `@transaction.atomic`.
- Management commands define `--dry-run` flag handling.
- Signals that send external notifications check both `created` AND `raw` (fixtures).

This is where the toolkit becomes specifically useful for *your* architecture. These are ~200 lines of Python walking the AST of the target project.

### Group 5 — `g5_defensive_libraries.py` (Django only)
**Purpose:** Verify every defensive library is **both installed AND actually used in code**, not just sitting in `requirements.txt`.

**Why this group exists:** "Library present but bypassed" is how defensive layers silently disappear. Someone adds a new viewset without `permission_classes`, a new model `status` field that's a plain `CharField` instead of `FSMField`, a new external API call that skips the circuit breaker. The library is still installed — but the new code does not use it. Standard scanners won't catch this because the code is syntactically fine.

This group enforces **architectural invariants**: "all credit mutations go through `CreditService`", "all external HTTP calls are wrapped in a circuit breaker", "all state fields are FSM-managed".

#### 5a. Presence checks (fast, deterministic)

Verify each library is declared and pinned in `requirements.txt` and importable from the project's venv:

| Library | Purpose |
|---------|---------|
| `django-rules` | Declarative object permissions |
| `django-fsm` (or `viewflow.fsm`) | State machines |
| `django-constance` | Dynamic settings |
| `django-safedelete` | Soft delete |
| `django-stubs` + `djangorestframework-stubs` | Type stubs |
| `django-structlog` | Structured logging |
| `pydantic` | Validation |
| `pybreaker` | Circuit breakers |
| `django-waffle` | Feature flags |
| `django-log-request-id` | Request ID tracing |
| `django-auditlog` | Model change audit |
| `django-q2` | Async tasks |
| `pre-commit` | Pre-commit hooks |

#### 5b. Configuration checks

Verify each library is wired up in `settings.py`:

| Check | Rule |
|-------|------|
| `CONSTANCE_CONFIG` non-empty | django-constance actually has settings registered |
| `'rules.permissions.ObjectPermissionBackend'` in `AUTHENTICATION_BACKENDS` | django-rules enforcement path active |
| `'auditlog.middleware.AuditlogMiddleware'` in `MIDDLEWARE` | django-auditlog captures actor |
| `'log_request_id.middleware.RequestIDMiddleware'` in `MIDDLEWARE` | Request IDs propagated |
| `'waffle.middleware.WaffleMiddleware'` in `MIDDLEWARE` | Feature flags resolvable in requests |
| `LOGGING` uses `structlog` processor chain | django-structlog active |
| `Q_CLUSTER` configured | django-q2 tasks can run |
| `mypy.ini` / `pyproject.toml` has `plugins = mypy_django_plugin.main` + `DJANGO_SETTINGS_MODULE` | django-stubs wired up |
| `.pre-commit-config.yaml` exists AND includes `ruff`, `bandit`, `gitleaks` hooks | Pre-commit enforced |
| `SECURE_HSTS_SECONDS`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `SECURE_SSL_REDIRECT` set in prod settings | Security headers on |
| `CORS_ALLOW_ALL_ORIGINS` is `False` (or absent) | No wildcard CORS |
| `CSRF_TRUSTED_ORIGINS` populated | CSRF defenses not bypassed |

#### 5c. Usage checks (AST-based — the real value)

These walk the target project's AST and flag new code that bypasses defensive layers. This is where the bugs actually live.

| Check | Catches |
|-------|---------|
| Every DRF `ViewSet` / `APIView` / generic view declares `permission_classes` | New view added with default `AllowAny` |
| Every `permission_classes` references a rules predicate OR a DRF permission derived from one | Permission present but bypassed with `AllowAny` |
| Every model with a field named `status`, `state`, or `phase` (CharField with `choices`) uses `FSMField` | New stateful model added without FSM |
| Every `@transition` uses `source=`/`target=` explicitly (no wildcards) | Silent state transitions |
| Every external HTTP call (`requests.*`, `httpx.*`, `urllib3.*`) inside `services/` is inside a `@circuit_breaker` or `with breaker:` block | Raw outbound calls that can't be broken |
| Every `send_message` / `bot.send_*` / `send_mail` happens through `OutboxService.queue_*` OR is inside a documented exception list | Direct notification calls that bypass the outbox |
| Every credit mutation (`user.credits +=`, `user.credits -=`, `.save(update_fields=['credits'])`) goes through `CreditService` | Raw balance writes that skip idempotency/audit |
| Every `CreditService.earn/spend/refund` call site passes `idempotency_key=` | Missing idempotency on a new credit flow |
| Every `@receiver(post_save/post_delete)` that sends notifications uses `transaction.on_commit(lambda: ...)` | Signal fires before commit — sends notification for a rollback |
| Every model touching credits/waitlist/user/post is registered with `auditlog.register(Model)` | New sensitive model added without audit |
| Every view that reads query/body params uses a Pydantic model OR a DRF serializer with `.is_valid(raise_exception=True)` | Unvalidated input |
| Every waffle flag referenced in code (`waffle.flag_is_active('name')`) is defined in a migration or fixture | Typo'd flag names silently return `False` |
| Every django-q2 task that mutates state takes `idempotency_key` as a parameter (or is decorated with an idempotency wrapper) | Retried task double-mutates |
| Every `SafeDeleteModel` subclass uses `.all()` / `.filter()` (not `.all_with_deleted()`) in user-facing code paths | Accidental exposure of soft-deleted rows |
| Every DRF viewset declares `throttle_classes` OR is in a whitelist | New endpoint without rate limit |

#### 5d. Project-level expected-library manifest

Each project gets an optional `.scan-toolkit/expected.yml`:

```yaml
# ~/projects/loudrr/.scan-toolkit/expected.yml
defensive_libraries:
  required:
    - django-rules
    - django-fsm
    - django-constance
    - django-safedelete
    - django-stubs
    - django-structlog
    - pydantic
    - pybreaker
    - django-waffle
    - django-log-request-id
    - django-auditlog
    - django-q2
  usage_rules:
    credit_service_only:
      pattern: "user.credits [+-]="
      allowed_in: ["core/services/credits.py"]
    external_http_needs_breaker:
      pattern: "requests\\.(get|post|put|delete)"
      required_context: "@circuit_breaker|with .*breaker"
    notifications_through_outbox:
      pattern: "bot\\.send_message|send_mail"
      allowed_in: ["core/services/outbox.py", "bots/telegram/"]
  waived:
    # Document any intentional bypasses with a reason
    - rule: credit_service_only
      location: "core/management/commands/seed_posts.py:42"
      reason: "Test fixture seeding; runs outside production"
      reviewed_by: "ak"
      reviewed_on: "2026-04-23"
```

The `waived` section is important — it forces bypasses to be **documented and reviewed**, not silently present. Unknown bypasses fail the scan; waived ones don't.

---

## 5. Auto-Detection (`detect.py`)

```
Enter project root
├── Is there a manage.py at ./ or ./backend/?
│   └── Yes → Enable Django scans (Groups 4 + 5, Django pieces of 2/3)
├── Is there a next.config.{js,ts,mjs} at ./ or ./frontend/?
│   └── Yes → Enable Next.js scans (frontend pieces of 2/3)
├── Is there a package.json?
│   └── Yes → Enable npm audit, eslint, njsscan, tsc, jscpd JS mode
├── Is there a requirements.txt / pyproject.toml?
│   └── Yes → Enable pip-audit, bandit, ruff, pyright, mypy, vulture
└── Always-on → gitleaks, trufflehog, osv-scanner, jscpd
```

**Critical requirement from you:** *"I don't want it to miss any folders."*

Implementation: `detect.py` walks the entire project tree (respecting `.gitignore`), lists every Python and JS/TS file, and logs the count per group. `summary.md` always shows **"Scanned N Python files across M directories"** so you can visually confirm nothing was skipped.

---

## 6. Running It

```bash
# One-time setup
cd ~/projects/scan-toolkit
python install.py                                      # Installs pinned versions in isolated venv

# Against any project
python run.py --project ~/projects/loudrr              # All groups, all auto-detected
python run.py --project ~/projects/loudrr --groups 4   # Django safety only
python run.py --project ~/projects/loudrr --groups 5   # Defensive library check only
python run.py --project ~/projects/loudrr --groups 1,2 # Secrets + SAST
python run.py --project ~/projects/loudrr --fail-on high   # Exit non-zero if high/critical findings
python run.py --project ~/projects/loudrr --format md,json # Both output formats
```

Exit codes:
- `0` — no findings above configured threshold
- `1` — findings at or above threshold
- `2` — critical findings or tool crashes

---

## 7. What This Toolkit Does NOT Do

Stated explicitly so you are not surprised later:

| Missing | Why | How to cover it |
|---------|-----|-----------------|
| **Authorization / IDOR detection** | Scanners have no concept of "who owns this object" | Integration tests: "User A cannot read User B's WaitlistEntry" — one test class per viewset |
| **Business logic bugs** (referral self-credit, coupon stacking, FSM bypass) | No pattern signal | Property-based tests with Hypothesis; domain-specific unit tests |
| **Race conditions** (duplicate webhook credits, signal double-fire) | Static analysis can't observe concurrency | Integration tests with `threading` / `concurrent.futures`; DB unique constraints as the real defense |
| **Missing rate limits** | Scanners don't model "this endpoint should have throttle class X" | Audit all viewsets; add a test that asserts throttle presence |
| **Runtime vulnerabilities** (SSRF to internal network, auth bypass in live app) | SAST sees code, not behavior | DAST — OWASP ZAP baseline against staging; one annual pentest |
| **Dependency confusion / typo-squats** | `pip-audit` needs a CVE to exist | Lockfile pinning, `pip install --require-hashes` in prod |
| **LLM/prompt injection surfaces** (if you add AI features) | Nascent tooling | Threat model per feature |

---

## 8. Non-Negotiable Practices Beyond Scanners

These produce more bug reduction per hour spent than adding another scanner. Treat them as tier-0 alongside the toolkit:

1. **Auth-focused PR review checklist** — every PR touching a view answers:
   - Who can call this endpoint?
   - What objects can the caller reference? Is ownership checked?
   - Is there a rate limit?
   - Is it idempotent (safe to retry)?
   - Is it inside `@transaction.atomic` if it writes multiple rows?
2. **Authorization integration tests** — for *every* viewset, assert User A cannot access User B's data. This one pattern catches most IDORs.
3. **Property-based tests with Hypothesis** — 2024 data: PBTs find ~50x more mutations than average unit tests. Apply to `CreditService` (earn + spend + refund should conserve total balance), FSM transitions, `ReferralService.increment_referral_count()`.
4. **DB constraints as the real idempotency guarantee** — `UniqueConstraint` on `(user, type, idempotency_key)` in `transactions`. You have this. Make sure it exists for every credit-affecting operation.
5. **Feature flags + staged rollouts** (django-waffle is already installed) — contain blast radius of the 60% of bugs scanners miss.
6. **Business-metric alerting** — `credits_minted_per_hour`, `waitlist_approval_rate`, `failed_verification_rate`. A sudden 10x spike *is* the bug detector scanners can't be.
7. **Runtime invariants** — you already have [core/invariants.py](../backend/core/invariants.py). Extend coverage.
8. **Threat modeling quarterly** against [OWASP ASVS v5.0](https://owasp.org/www-project-application-security-verification-standard/) Level 2.
9. **One annual external pentest or bug bounty** — the only reliable way to find IDOR + business logic bugs at scale.

---

## 9. Implementation Plan

**Phase 1 — Scaffold (1 day)**
- Create `~/projects/scan-toolkit/` structure above.
- Write `install.py` with pinned tool versions.
- Write `detect.py` + `run.py` + `report.py`.

**Phase 2 — Groups 1, 2, 3 (1 day)**
- Wire in off-the-shelf tools. Each group is ~100 LOC of subprocess + JSON parsing.
- Verify against loudrr — make sure no folders are missed.

**Phase 3 — Group 4 custom rules (1–2 days)**
- Write custom Semgrep rules in `rules/semgrep/`.
- Write custom AST checks in `rules/ast/django_checks.py`.

**Phase 4 — Group 5 defensive library checks (1 day)**
- Presence + config checks (fast, YAML-driven).
- AST usage checks — the ~15 rules in Section 4 (5c).
- Seed `.scan-toolkit/expected.yml` for loudrr based on your existing 14-item checklist.
- First-run across all 5 groups against loudrr; expect 50–200 findings.

**Phase 5 — Baseline triage (1 day)**
- Go through every finding. For each: fix OR suppress-with-documented-reason.
- Commit suppressions to the target project, not the toolkit.
- After this pass, every future run surfaces **only new issues**.

**Phase 6 — Ongoing**
- Run before every release.
- Add a new custom rule every time a bug ships that a rule could have caught.
- Every time you add a new defensive library to a project, add it to `expected.yml` and write a usage rule for it.
- Eventually move to pre-commit hook + CI gate.

---

## 10. Realistic Expected Coverage After Build

| Layer | Coverage |
|-------|----------|
| This toolkit alone | ~40% of all potential bugs/vulns caught |
| Toolkit + authorization integration tests | ~65% |
| Toolkit + integration tests + Hypothesis on core services | ~80% |
| All of the above + annual pentest + observability alerts | ~90–95% |
| **"Zero bugs"** | **Not achievable by any combination of tools**. What you can achieve is fast detection + small blast radius when bugs inevitably ship. |

---

## 11. Sources

- [Endor Labs — False Negatives in SAST](https://www.endorlabs.com/learn/false-negatives-in-sast-hidden-risks-behind-the-noise)
- [arXiv 2407.16235 — Comparison of SAST Tools and LLMs for Vulnerability Detection](https://arxiv.org/abs/2407.16235)
- [Veracode State of Software Security 2025](https://www.veracode.com/wp-content/uploads/2025/02/State-of-Software-Security-2025.pdf)
- [ZeroPath — Authorization Bugs Having Their SQL Injection Moment](https://zeropath.com/blog/idor-crisis-2025)
- [Precursor Security — Business Logic Vulnerabilities: What Scanners Miss](https://www.precursorsecurity.com/blog/business-logic-vulnerabilities-what-scanners-miss)
- [Include Security — Customizing Semgrep Rules for Flask/Django](https://blog.includesecurity.com/2021/07/customizing-semgrep-rules-for-flask-django/)
- [Simon Crowe — Django and Semgrep: Enforcing a Service Layer](https://simoncrowe.hashnode.dev/django-and-semgrep-enforcing-a-service-layer-using-static-analysis)
- [minusworld Semgrep rulesets](https://semgrep.dev/p/minusworld.django-trimmed)
- [Django ticket #29499 — update_or_create race condition](https://code.djangoproject.com/ticket/29499)
- [django-migration-linter incompatibilities](https://github.com/3YOURMIND/django-migration-linter/blob/main/docs/incompatibilities.md)
- [OWASP ASVS v5.0](https://owasp.org/www-project-application-security-verification-standard/)
- [Next.js Security Update 2025-12-11 (CVE-2025-29927, CVE-2025-55182)](https://nextjs.org/blog/security-update-2025-12-11)
- [OOPSLA 2025 — Empirical Evaluation of Property-Based Testing in Python](https://cseweb.ucsd.edu/~mcoblenz/assets/pdf/OOPSLA_2025_PBT.pdf)
- [Edgescan Vulnerability Statistics Report 2024](https://www.edgescan.com/stats-report/)
