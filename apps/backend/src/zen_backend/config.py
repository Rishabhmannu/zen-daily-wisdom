from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: str = Field(default="development", alias="ENVIRONMENT")
    backend_port: int = Field(default=8000, alias="BACKEND_PORT")

    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")
    gemini_daily_call_cap: int = Field(default=20, alias="GEMINI_DAILY_CALL_CAP")

    supabase_url: str = Field(default="", alias="SUPABASE_URL")
    supabase_service_role_key: str = Field(default="", alias="SUPABASE_SERVICE_ROLE_KEY")
    supabase_anon_key: str = Field(default="", alias="SUPABASE_ANON_KEY")
    owner_uid: str = Field(default="", alias="OWNER_UID")

    internal_hmac_secret: str = Field(default="", alias="INTERNAL_HMAC_SECRET")
    feedback_link_secret: str = Field(default="", alias="FEEDBACK_LINK_SECRET")

    telegram_bot_token: str = Field(default="", alias="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: str = Field(default="", alias="TELEGRAM_CHAT_ID")
    telegram_webhook_secret: str = Field(default="", alias="TELEGRAM_WEBHOOK_SECRET")

    gmail_client_id: str = Field(default="", alias="GMAIL_CLIENT_ID")
    gmail_client_secret: str = Field(default="", alias="GMAIL_CLIENT_SECRET")
    gmail_refresh_token: str = Field(default="", alias="GMAIL_REFRESH_TOKEN")
    gmail_from_address: str = Field(default="", alias="GMAIL_FROM_ADDRESS")

    gcal_client_id: str = Field(default="", alias="GCAL_CLIENT_ID")
    gcal_client_secret: str = Field(default="", alias="GCAL_CLIENT_SECRET")
    gcal_refresh_token: str = Field(default="", alias="GCAL_REFRESH_TOKEN")
    gcal_calendar_id: str = Field(default="", alias="GCAL_CALENDAR_ID")

    supabase_db_dsn: str = Field(default="", alias="SUPABASE_DB_DSN")
    supabase_db_dsn_pooler: str = Field(default="", alias="SUPABASE_DB_DSN_POOLER")
    public_base_url: str = Field(default="http://localhost:8000", alias="NEXT_PUBLIC_BACKEND_URL")
    frontend_base_url: str = Field(default="http://localhost:3000", alias="NEXT_PUBLIC_FRONTEND_URL")
    allowed_emails_raw: str = Field(default="", alias="ALLOWED_EMAILS")

    @property
    def allowed_emails(self) -> set[str]:
        raw = self.allowed_emails_raw.strip()
        if not raw:
            return set()
        return {entry.strip().lower() for entry in raw.split(",") if entry.strip()}


settings = Settings()

