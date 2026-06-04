from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")
    # app wireup
    app_name: str = "Loudrr"
    # debug default to false, can be overridden by .env
    debug: bool = False
    # db url
    database_url: (
        str  # no default — required; Pydantic errors at startup if .env lacks it
    )
    items_per_page: int = 20

    # --- DB connection pool (scale; see backend/tests/SCALING.md) ---
    # Per-process pool. Across N web + M worker processes, keep
    # N+M × (db_pool_size + db_max_overflow) under Postgres max_connections,
    # or front it with PgBouncer (transaction pooling).
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_timeout: int = 30      # seconds to wait for a free connection before erroring
    db_pool_recycle: int = 1800    # recycle a connection after 30 min (avoid stale handles)

    # --- Telegram ---
    # the bot's secret token (a string like "123456:ABC-…"), read from .env
    telegram_bot_token: str = ""
    telegram_bot_username: str = ""

    # --- Redis / task queue (Ch16) ---
    redis_url: str = ""
    # when True, on-demand jobs enqueue to arq (needs Redis + a running worker);
    # when False (dev/test), they run via FastAPI BackgroundTasks in-process
    use_task_queue: bool = False

    # --- External services (Ch10/11/13/15) ---
    # TweetScout: clout score + X profile (Ch10). Twitter: reply verification (Ch13).
    tweetscout_api_key: str = ""
    twitter_api_key: str = ""

    # --- X OAuth 2.0 (Ch11) ---
    x_oauth_client_id: str = ""
    x_oauth_client_secret: str = ""
    x_oauth_callback_url: str = ""

    # --- URLs / misc ---
    site_url: str = ""
    landing_url: str = ""
    encryption_key: str = ""           # 32-byte key for redirect-URL encryption
    # comma-separated; default is the canonical dev admin (Oxblest,
    # telegram_id=6451704338) — matches the Django reference's default.
    # In prod set ADMIN_TELEGRAM_IDS in .env to your real admin IDs.
    admin_telegram_ids: str = "6451704338"
    cors_allowed_origins: str = ""     # comma-separated

    # --- admin panel (Ch17) ---
    secret_key: str = "dev-insecure-secret-change-me"  # session signing for SQLAdmin
    admin_username: str = "admin"
    admin_password: str = ""           # set in prod; blank disables admin login


# business logic settings
settings = Settings()  # type: ignore[call-arg]  # pydantic-settings reads required fields from .env at runtime

print(f"{settings.app_name}\n{settings.debug}\n{settings.items_per_page}")
