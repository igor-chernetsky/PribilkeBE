from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str = "postgresql://pribilka:pribilka@localhost:5432/pribilka"
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    default_country: str = "PL"
    debug: bool = False
    api_prefix: str = "/api/v1"

    # Admin alerts when collectors fail (Telegram recommended)
    admin_telegram_bot_token: str | None = None
    admin_telegram_chat_id: str | None = None
    admin_webhook_url: str | None = None
    collector_alert_cooldown_hours: int = 12

    # Admin read API (collector status, etc.)
    admin_api_key: str | None = None

    # Firebase Cloud Messaging (push notifications)
    firebase_project_id: str | None = None
    firebase_credentials_json: str | None = None

    # Optional OpenAI enhancement for product insights
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"


@lru_cache
def get_settings() -> Settings:
    return Settings()
