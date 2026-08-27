from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Single source of truth for all configuration. Values are read from
    environment variables / a local .env file (never committed).
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Gemini ---
    gemini_api_key: str
    gemini_model: str = "gemini-2.5-flash"

    # --- Itinerary knowledge base ---
    itinerary_pdf_path: str = "data/kerala_itinerary.pdf"

    # --- Session store ---
    redis_url: Optional[str] = None  # if unset, falls back to in-memory store
    session_ttl_seconds: int = 60 * 60 * 24 * 3  # 3 days

    # --- WhatsApp / Meta ---
    whatsapp_token: Optional[str] = None
    whatsapp_phone_id: Optional[str] = None
    whatsapp_verify_token: Optional[str] = None
    whatsapp_app_secret: Optional[str] = None  # required to verify webhook signatures

    # --- Web widget ---
    allowed_origins: str = ""  # comma-separated list, e.g. "https://yoursite.com"

    # --- Leads ---
    leads_db_path: str = "data/leads.db"
    company_notify_webhook_url: Optional[str] = None  # e.g. Slack/CRM webhook on lead completion

    # --- App ---
    environment: str = "development"  # development | staging | production
    log_level: str = "INFO"

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
