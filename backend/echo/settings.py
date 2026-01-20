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
    "corsheaders",
    "auditlog",
    # Local apps
    "core",
    "posts",
    "redirects",
    "bots",
    "miniapp",
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
    "accent": "accent-light",  # White accent on dark
    "navbar": "navbar-dark",
    "no_navbar_border": True,
    "navbar_fixed": True,
    "layout_boxed": False,
    "footer_fixed": False,
    "sidebar_fixed": True,
    "sidebar": "sidebar-dark-light",  # Dark sidebar with white highlight
    "sidebar_nav_small_text": False,
    "sidebar_disable_expand": False,
    "sidebar_nav_child_indent": True,
    "sidebar_nav_compact_style": False,
    "sidebar_nav_legacy_style": False,
    "sidebar_nav_flat_style": False,
    "theme": "darkly",
    "dark_mode_theme": "darkly",
    "button_classes": {
        "primary": "btn-dark",
        "secondary": "btn-outline-light",
        "info": "btn-outline-light",
        "warning": "btn-light",
        "danger": "btn-outline-light",
        "success": "btn-light",
    },
}

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "auditlog.middleware.AuditlogMiddleware",  # Track who made changes
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
}

# CORS
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=["http://localhost:3000"])
CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^https://.*\.trycloudflare\.com$",  # Allow all Cloudflare tunnel URLs
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

# Mini App URL (for bot to open)
MINIAPP_URL = env("MINIAPP_URL", default="http://localhost:3000")

# Bot tokens
TELEGRAM_BOT_TOKEN = env("TELEGRAM_BOT_TOKEN", default="")
DISCORD_BOT_TOKEN = env("DISCORD_BOT_TOKEN", default="")

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

# Logging configuration - outputs errors to console for gunicorn to capture
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
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
    },
}
