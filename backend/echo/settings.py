"""
Django settings for ECHO project.
"""
import os
from pathlib import Path

import environ

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Environment variables
env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1"]),
)

# Read .env file if it exists
environ.Env.read_env(os.path.join(BASE_DIR.parent, ".env"))

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env("SECRET_KEY", default="django-insecure-change-me-in-production")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env("DEBUG")

ALLOWED_HOSTS = env("ALLOWED_HOSTS") + [".trycloudflare.com"]

# Load Testing Configuration (NEVER enable in production!)
# Set LOAD_TEST_MODE=true and LOAD_TEST_SECRET to enable load test auth bypass
LOAD_TEST_MODE = env.bool("LOAD_TEST_MODE", default=False)
LOAD_TEST_SECRET = env("LOAD_TEST_SECRET", default="")

# Application definition
INSTALLED_APPS = [
    "jazzmin",  # Must be before django.contrib.admin
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third party
    "rest_framework",
    "drf_spectacular",  # OpenAPI schema generation
    "corsheaders",
    "auditlog",
    # Backend Hardening (Jan 2026)
    "django_fsm",  # State machines (auditlog tracks changes instead of django_fsm_log)
    "rules",
    "constance",
    "safedelete",
    "django_structlog",
    "waffle",
    # Local apps
    "core",
    "posts",
    "redirects",
    "bots",
    "miniapp",
    "loud",
]

# Jazzmin Admin UI Configuration
JAZZMIN_SETTINGS = {
    # Title & Branding
    "site_title": "Loudrr Admin",
    "site_header": "Loudrr",
    "site_brand": "",
    "site_logo": "images/loudrr-logo.png",
    "login_logo": "images/loudrr-logo.png",
    "login_logo_dark": "images/loudrr-logo.png",
    "site_logo_classes": "",
    "site_icon": "images/loudrr-icon.png",
    "welcome_sign": "Welcome to Loudrr Admin",
    "copyright": "Loudrr 2024",

    # Search model for top search bar
    "search_model": ["core.User", "posts.Post"],

    # User menu avatar
    "user_avatar": None,

    # Top Menu Links
    "topmenu_links": [
        {"name": "Home", "url": "admin:index", "permissions": ["auth.view_user"]},
        {"name": "View Site", "url": "/", "new_window": True},
        {"model": "core.User"},
        {"model": "posts.Post"},
    ],

    # User menu links
    "usermenu_links": [
        {"name": "Support", "url": "https://github.com/anthropics/claude-code/issues", "new_window": True},
        {"model": "core.User"},
    ],

    # Side Menu Configuration
    "show_sidebar": True,
    "navigation_expanded": True,
    "hide_apps": [],
    "hide_models": [],

    # Custom ordering for apps/models
    "order_with_respect_to": [
        "core",
        "core.User",
        "core.Transaction",
        "core.SiteSetting",
        "core.AuditLog",
        "core.XProfile",
        "posts",
        "posts.Post",
        "posts.Engagement",
        "posts.SponsoredPost",
        "posts.Campaign",
        "miniapp",
        "loud",
        "loud.LoudProject",
        "loud.LoudSubmission",
        "loud.LoudLeaderboardEntry",
    ],

    # Custom icons for apps/models (FontAwesome 5)
    "icons": {
        "auth": "fas fa-users-cog",
        "auth.user": "fas fa-user",
        "auth.Group": "fas fa-users",
        "admin": "fas fa-history",
        "admin.LogEntry": "fas fa-history",
        "core": "fas fa-cogs",
        "core.User": "fas fa-users",
        "core.Transaction": "fas fa-exchange-alt",
        "core.SiteSetting": "fas fa-sliders-h",
        "core.AuditLog": "fas fa-clipboard-check",
        "core.XProfile": "fab fa-twitter",
        "posts": "fas fa-paper-plane",
        "posts.Post": "fas fa-file-alt",
        "posts.Engagement": "fas fa-heart",
        "posts.SponsoredPost": "fas fa-ad",
        "posts.Campaign": "fas fa-bullhorn",
        "posts.CampaignEntry": "fas fa-ticket-alt",
        "miniapp": "fas fa-mobile-alt",
        "loud": "fas fa-rocket",
        "loud.LoudProject": "fas fa-flag",
        "loud.LoudSubmission": "fas fa-paper-plane",
        "loud.LoudLeaderboardEntry": "fas fa-trophy",
        "auditlog": "fas fa-file-alt",
        "auditlog.LogEntry": "fas fa-clipboard-list",
    },
    "default_icon_parents": "fas fa-folder",
    "default_icon_children": "fas fa-circle",

    # Related Modal
    "related_modal_active": True,

    # Custom CSS/JS
    "custom_css": "admin/css/loudrr-theme.css",
    "custom_js": None,

    # Show UI Builder
    "show_ui_builder": False,

    # Change view settings
    "changeform_format": "horizontal_tabs",
    "changeform_format_overrides": {
        "core.user": "collapsible",
        "posts.post": "horizontal_tabs",
    },
}

# Jazzmin UI Tweaks (Clean Black & White Theme)
JAZZMIN_UI_TWEAKS = {
    "navbar_small_text": False,
    "footer_small_text": False,
    "body_small_text": False,
    "brand_small_text": False,
    "brand_colour": "navbar-dark",
    "accent": "accent-primary",
    "navbar": "navbar-dark navbar-primary",
    "no_navbar_border": True,
    "navbar_fixed": True,
    "layout_boxed": False,
    "footer_fixed": False,
    "sidebar_fixed": True,
    "sidebar": "sidebar-dark-primary",
    "sidebar_nav_small_text": False,
    "sidebar_disable_expand": False,
    "sidebar_nav_child_indent": True,
    "sidebar_nav_compact_style": False,
    "sidebar_nav_legacy_style": False,
    "sidebar_nav_flat_style": False,
    "theme": "darkly",
    "dark_mode_theme": "darkly",
    "button_classes": {
        "primary": "btn-primary",
        "secondary": "btn-secondary",
        "info": "btn-info",
        "warning": "btn-warning",
        "danger": "btn-danger",
        "success": "btn-success",
    },
}

MIDDLEWARE = [
    "log_request_id.middleware.RequestIDMiddleware",  # Request tracing (must be first)
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # Serve static files in production
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "auditlog.middleware.AuditlogMiddleware",  # Track who made changes
    "django_structlog.middlewares.RequestMiddleware",  # Structured logging
    "waffle.middleware.WaffleMiddleware",  # Feature flags
]

ROOT_URLCONF = "echo.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "echo.wsgi.application"

# Database - uses DATABASE_URL
DATABASES = {
    "default": env.db("DATABASE_URL", default="postgresql://echo:echo@localhost:5432/echo")
}
# Add connection health checks and shorter timeouts for Supabase
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True
DATABASES["default"]["CONN_MAX_AGE"] = 60  # Reuse connections for 60 seconds
DATABASES["default"]["OPTIONS"] = {
    "connect_timeout": 30,  # Increased for Supabase cold starts
    "keepalives": 1,
    "keepalives_idle": 30,
    "keepalives_interval": 10,
    "keepalives_count": 5,
}

# Redis
REDIS_URL = env("REDIS_URL", default="redis://localhost:6379/0")

# Celery
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "UTC"

# Cache
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "echo-cache",
    }
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Custom user model
AUTH_USER_MODEL = "core.User"

# Authentication backends (allow login via telegram_id)
AUTHENTICATION_BACKENDS = [
    'rules.permissions.ObjectPermissionBackend',  # django-rules object permissions
    'core.backends.TelegramIDBackend',  # Login with telegram ID
    'django.contrib.auth.backends.ModelBackend',  # Default (UUID)
]

# Internationalization
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [
    BASE_DIR / "static",
]
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    },
}

# Default primary key field type
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# REST Framework
REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    # OpenAPI schema generation
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

# =============================================================================
# API DOCUMENTATION (drf-spectacular)
# =============================================================================
SPECTACULAR_SETTINGS = {
    "TITLE": "Loudrr API",
    "DESCRIPTION": """
## Loudrr - X/Twitter Engagement Rewards Platform

Loudrr is a Telegram-based mini-app platform for X/Twitter engagement rewards.
Users earn "karma" by engaging with posts, then spend karma to promote their own content.

### Authentication

Most endpoints require Telegram Web App authentication via the `X-Telegram-Init-Data` header.
This header contains HMAC-signed data from the Telegram Web App SDK.

### Core Features

- **Engagement System**: Start sessions, engage with posts, earn karma
- **Post Promotion**: Spend karma to promote your posts
- **LOUD UGC**: Submit content to contests for rewards
- **Waitlist**: Onboarding flow with admin approval
- **Referrals**: Share referral links to earn bonuses

### Rate Limits

- Waitlist endpoints: 5 requests/hour per IP
- Session endpoints: Standard DRF throttling
    """,
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    # Organize endpoints by tags
    "TAGS": [
        {"name": "Health", "description": "Health check endpoints"},
        {"name": "Settings", "description": "App configuration"},
        {"name": "Waitlist", "description": "Waitlist signup and status"},
        {"name": "User", "description": "User profile and stats"},
        {"name": "Engagement", "description": "Session-based engagement flow"},
        {"name": "Posts", "description": "Post submission and management"},
        {"name": "LOUD", "description": "UGC contest submissions"},
        {"name": "Referral", "description": "Referral system"},
    ],
    # Schema customization
    "COMPONENT_SPLIT_REQUEST": True,
    "SCHEMA_PATH_PREFIX": r"/api/",
    # Security
    "SECURITY": [{"TelegramWebAppAuth": []}],
    "APPEND_COMPONENTS": {
        "securitySchemes": {
            "TelegramWebAppAuth": {
                "type": "apiKey",
                "in": "header",
                "name": "X-Telegram-Init-Data",
                "description": "Telegram Web App init data (HMAC-signed)",
            }
        }
    },
    # Swagger UI settings
    "SWAGGER_UI_SETTINGS": {
        "deepLinking": True,
        "persistAuthorization": True,
        "displayOperationId": False,
        "filter": True,
    },
    # ReDoc settings
    "REDOC_UI_SETTINGS": {
        "hideDownloadButton": False,
        "expandResponses": "200,201",
    },
}

# =============================================================================
# EMAIL CONFIGURATION
# =============================================================================
# For production, use an SMTP service like AWS SES, SendGrid, Mailgun, etc.
# Set these environment variables:
#   EMAIL_HOST=smtp.sendgrid.net
#   EMAIL_PORT=587
#   EMAIL_HOST_USER=apikey
#   EMAIL_HOST_PASSWORD=your-api-key
#   EMAIL_USE_TLS=True
#   DEFAULT_FROM_EMAIL=noreply@loudrr.com

EMAIL_BACKEND = env(
    "EMAIL_BACKEND",
    default="django.core.mail.backends.console.EmailBackend" if DEBUG else "django.core.mail.backends.smtp.EmailBackend"
)
EMAIL_HOST = env("EMAIL_HOST", default="smtp.gmail.com")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
EMAIL_USE_SSL = env.bool("EMAIL_USE_SSL", default=False)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="Loudrr <noreply@loudrr.com>")
EMAIL_SUBJECT_PREFIX = "[Loudrr] "

# =============================================================================
# CORS
# =============================================================================
# In production, set CORS_ALLOW_ALL_ORIGINS=False (defaults to DEBUG value)
CORS_ALLOW_ALL_ORIGINS = env.bool("CORS_ALLOW_ALL_ORIGINS", default=DEBUG)
CORS_ALLOWED_ORIGINS = env.list(
    "CORS_ALLOWED_ORIGINS",
    default=[
        # Development
        "http://localhost:3000",  # Main frontend
        "http://localhost:3001",  # Landing page
        # Production (set via environment variables)
        # Example: CORS_ALLOWED_ORIGINS=https://loudrr.com,https://www.loudrr.com,https://app.loudrr.com
    ]
)
CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^https://.*\.trycloudflare\.com$",  # Allow all Cloudflare tunnel URLs (dev/staging)
]
CORS_ALLOW_HEADERS = [
    "accept",
    "accept-encoding",
    "authorization",
    "content-type",
    "dnt",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
    "x-telegram-init-data",  # Custom header for Telegram Web App
]

# CSRF Trusted Origins (required for Django 4.0+ with HTTPS)
# Without this, admin login and other POST forms will fail with 403 CSRF error
CSRF_TRUSTED_ORIGINS = env.list(
    "CSRF_TRUSTED_ORIGINS",
    default=[
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        # Production domains (set via env var or add here)
        "https://api.loudrr.com",
        "https://loudrr.com",
        "https://app.loudrr.com",
    ]
)

# Public site URL (serves landing at /, mini app at /app, card APIs at /api/cards/*)
SITE_URL = env("SITE_URL", default="http://localhost:3000")

# Mini App URL (the URL Telegram opens as the Web App)
MINIAPP_URL = env("MINIAPP_URL", default=f"{SITE_URL}/app")

# Landing Page URL (used for card image generation and share links)
LANDING_URL = env("LANDING_URL", default=SITE_URL)

# Bot tokens
TELEGRAM_BOT_TOKEN = env("TELEGRAM_BOT_TOKEN", default="")
TELEGRAM_BOT_USERNAME = env("TELEGRAM_BOT_USERNAME", default="Loudrrbot")

# Telegram webhook config (for production). If both are set, run the bot as
# a webhook target via /api/telegram/webhook/. If unset, run `python manage.py
# run_telegram_bot` (polling mode) for local dev.
TELEGRAM_WEBHOOK_URL = env("TELEGRAM_WEBHOOK_URL", default="")
TELEGRAM_WEBHOOK_SECRET = env("TELEGRAM_WEBHOOK_SECRET", default="")

# Twitter API (twitterapi.io) for verification (v1)
TWITTER_API_KEY = env("TWITTER_API_KEY", default="")

# TweetScout API for user score
TWEETSCOUT_API_KEY = env("TWEETSCOUT_API_KEY", default="")

# Admin Telegram IDs (can give credits to users)
# Add your Telegram user ID here
ADMIN_TELEGRAM_IDS = env.list("ADMIN_TELEGRAM_IDS", default=["6451704338"])

# ECHO Configuration - Reference Defaults
# NOTE: These values are seeded into SiteSettings table via migrations.
# Runtime values come from DB only - this dict is for reference/documentation.
# To change values, use Django admin: /loudrr-admin/core/sitesetting/
ECHO_CONFIG = {
    # Core costs & caps
    "POST_COST": 80,
    "CREDIT_PER_ENGAGEMENT": 1,
    "DAILY_EARN_CAP": 160,
    "ENGAGEMENT_COOLDOWN": 0,
    "AUDIT_PROBABILITY": 0.05,
    # Verification settings
    "VERIFICATION_BATCH_SIZE": 10,
    "VERIFICATION_SAMPLE_SIZE": 3,
    "MAX_VERIFICATION_RETRIES": 2,
    # Sponsored XP
    "SPONSORED_XP_PER_ENGAGEMENT": 5,
    # Streak multipliers
    "STREAK_7_DAY_MULTIPLIER": 1.0,
    "STREAK_14_DAY_MULTIPLIER": 1.0,
    "STREAK_30_DAY_MULTIPLIER": 1.0,
    # Streak bonuses
    "STREAK_7_DAY_BONUS": 5,
    "STREAK_14_DAY_BONUS": 6,
    "STREAK_30_DAY_BONUS": 10,
    # Karma decay
    "KARMA_DECAY_THRESHOLD_DAYS": 14,
    "KARMA_DECAY_RATE": 0.015,
    # Tier thresholds (TweetScout score)
    "TIER_NORMIE_THRESHOLD": 100,
    "TIER_DEGEN_THRESHOLD": 200,
    "TIER_BASED_THRESHOLD": 400,
    "TIER_LEGEND_THRESHOLD": 600,
    "TIER_OG_THRESHOLD": 800,
    "TIER_GOAT_THRESHOLD": 1000,
    # Tier multipliers
    "TIER_ANON_MULTIPLIER": 1.0,
    "TIER_NORMIE_MULTIPLIER": 1.10,
    "TIER_DEGEN_MULTIPLIER": 1.15,
    "TIER_BASED_MULTIPLIER": 1.20,
    "TIER_LEGEND_MULTIPLIER": 1.25,
    "TIER_OG_MULTIPLIER": 1.30,
    "TIER_GOAT_MULTIPLIER": 1.35,
}

# Encryption key for user IDs in redirect URLs
ENCRYPTION_KEY = env("ENCRYPTION_KEY", default="change-me-32-byte-key-in-prod!!")

# Allow async operations with Django ORM (required for python-telegram-bot)
# See: https://docs.djangoproject.com/en/5.0/topics/async/#async-safety
os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"

# Logging configuration with structlog for structured JSON logging
# In production, logs are JSON for easy parsing by log aggregators
import structlog

# Configure structlog processors
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.filter_by_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
    ],
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        # Human-readable format for development
        "verbose": {
            "format": "{levelname} {asctime} {module} {message}",
            "style": "{",
        },
        # Structlog JSON format for production
        "json": {
            "()": structlog.stdlib.ProcessorFormatter,
            "processor": structlog.processors.JSONRenderer(),
        },
        # Structlog console format for development
        "console_structlog": {
            "()": structlog.stdlib.ProcessorFormatter,
            "processor": structlog.dev.ConsoleRenderer(),
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "console_structlog" if DEBUG else "json",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "django.request": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": False,
        },
        # App loggers
        "core": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "posts": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "loud": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "django_structlog": {
            "handlers": ["console"],
            "level": "INFO",
        },
        # Silence httpx/telegram logging to prevent token exposure
        "httpx": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
        "httpcore": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
        "telegram": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
    },
}

# =============================================================================
# BACKEND HARDENING CONFIGURATION (Jan 2026)
# =============================================================================
# Note: Using django-auditlog for state change tracking (not django_fsm_log)
# auditlog captures all field changes including FSM status transitions

# Django-Constance settings (dynamic settings from admin)
CONSTANCE_BACKEND = "constance.backends.database.DatabaseBackend"
# Note: Empty string disables caching for constance (acceptable for low-traffic admin settings)
# For production with Redis, use: CONSTANCE_DATABASE_CACHE_BACKEND = "redis"
CONSTANCE_DATABASE_CACHE_BACKEND = ""

# Django-Constance configuration - replaces SiteSetting model
# These settings can be changed via Django admin at /loudrr-admin/constance/config/
CONSTANCE_CONFIG = {
    # Credits & Posting
    "POST_COST": (80, "Karma cost to create a post", int),
    "CREDIT_PER_ENGAGEMENT": (1, "Base credit per engagement", int),
    "DAILY_EARN_CAP": (160, "Maximum karma earnable per day", int),

    # Engagement
    "ENGAGEMENT_COOLDOWN": (0, "Cooldown between engagements (seconds)", int),
    "MIN_SESSION_DURATION_SECONDS": (30, "Minimum time before claiming", int),

    # Verification
    "VERIFICATION_BATCH_SIZE": (10, "Engagements per verification batch", int),
    "VERIFICATION_SAMPLE_SIZE": (3, "Sample size for verification", int),
    "MAX_VERIFICATION_RETRIES": (2, "Max retries for verification", int),
    "AUDIT_PROBABILITY": (0.05, "Probability of audit", float),

    # TweetScout Tier Thresholds
    "TIER_NORMIE_THRESHOLD": (100, "Minimum score for Normie tier", int),
    "TIER_DEGEN_THRESHOLD": (200, "Minimum score for Degen tier", int),
    "TIER_BASED_THRESHOLD": (400, "Minimum score for Based tier", int),
    "TIER_LEGEND_THRESHOLD": (600, "Minimum score for Legend tier", int),
    "TIER_OG_THRESHOLD": (800, "Minimum score for OG tier", int),
    "TIER_GOAT_THRESHOLD": (1000, "Minimum score for GOAT tier", int),

    # Tier Multipliers
    "TIER_ANON_MULTIPLIER": (1.0, "Karma multiplier for Anon tier", float),
    "TIER_NORMIE_MULTIPLIER": (1.10, "Karma multiplier for Normie tier", float),
    "TIER_DEGEN_MULTIPLIER": (1.15, "Karma multiplier for Degen tier", float),
    "TIER_BASED_MULTIPLIER": (1.20, "Karma multiplier for Based tier", float),
    "TIER_LEGEND_MULTIPLIER": (1.25, "Karma multiplier for Legend tier", float),
    "TIER_OG_MULTIPLIER": (1.30, "Karma multiplier for OG tier", float),
    "TIER_GOAT_MULTIPLIER": (1.35, "Karma multiplier for GOAT tier", float),

    # Streak Settings
    "STREAK_7_DAY_BONUS": (5, "Bonus karma for 7-day streak", int),
    "STREAK_14_DAY_BONUS": (6, "Bonus karma for 14-day streak", int),
    "STREAK_30_DAY_BONUS": (10, "Bonus karma for 30-day streak", int),

    # LOUD Settings
    "LOUD_DAILY_SUBMISSION_LIMIT": (6, "Max LOUD submissions per day", int),
    "LOUD_POINTS_DIVISOR": (10, "TweetScout score divisor for points", int),

    # Feature Flags (can also use django-waffle for more complex flags)
    "MAINTENANCE_MODE": (False, "Enable maintenance mode", bool),
    "REGISTRATION_OPEN": (True, "Allow new registrations", bool),

    # Production Safety
    "PRODUCTION_LOCK": (False, "Block dangerous actions (campaigns, payouts, destructive ops)", bool),
}

CONSTANCE_CONFIG_FIELDSETS = {
    "Credits & Posting": (
        "POST_COST",
        "CREDIT_PER_ENGAGEMENT",
        "DAILY_EARN_CAP",
    ),
    "Engagement Rules": (
        "ENGAGEMENT_COOLDOWN",
        "MIN_SESSION_DURATION_SECONDS",
    ),
    "Verification": (
        "VERIFICATION_BATCH_SIZE",
        "VERIFICATION_SAMPLE_SIZE",
        "MAX_VERIFICATION_RETRIES",
        "AUDIT_PROBABILITY",
    ),
    "TweetScout Tiers": (
        "TIER_NORMIE_THRESHOLD",
        "TIER_DEGEN_THRESHOLD",
        "TIER_BASED_THRESHOLD",
        "TIER_LEGEND_THRESHOLD",
        "TIER_OG_THRESHOLD",
        "TIER_GOAT_THRESHOLD",
    ),
    "Tier Multipliers": (
        "TIER_ANON_MULTIPLIER",
        "TIER_NORMIE_MULTIPLIER",
        "TIER_DEGEN_MULTIPLIER",
        "TIER_BASED_MULTIPLIER",
        "TIER_LEGEND_MULTIPLIER",
        "TIER_OG_MULTIPLIER",
        "TIER_GOAT_MULTIPLIER",
    ),
    "Streak Bonuses": (
        "STREAK_7_DAY_BONUS",
        "STREAK_14_DAY_BONUS",
        "STREAK_30_DAY_BONUS",
    ),
    "LOUD Feature": (
        "LOUD_DAILY_SUBMISSION_LIMIT",
        "LOUD_POINTS_DIVISOR",
    ),
    "Feature Flags": (
        "MAINTENANCE_MODE",
        "REGISTRATION_OPEN",
        "PRODUCTION_LOCK",
    ),
}

# Django-Waffle settings (feature flags)
WAFFLE_CREATE_MISSING_FLAGS = True  # Auto-create flags in dev
WAFFLE_CREATE_MISSING_SWITCHES = True
WAFFLE_CREATE_MISSING_SAMPLES = True

# Django-Log-Request-ID settings
LOG_REQUEST_ID_HEADER = "HTTP_X_REQUEST_ID"
GENERATE_REQUEST_ID_IF_NOT_IN_HEADER = True
REQUEST_ID_RESPONSE_HEADER = "X-Request-ID"
