from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8")
# app wireup
    app_name: str = "QuestKit"
# debug default to false, can be overridden by .env
    debug: bool = False
# db url
    database_url: str # no default — required; Pydantic errors at startup if .env lacks it
    items_per_page: int = 20

# business logic settings
settings = Settings()

print(f'{settings.app_name}\n{settings.debug}\n{settings.items_per_page}')