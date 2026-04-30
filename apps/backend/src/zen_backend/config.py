import re

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_EMAIL_REGEX = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")


def _clean_email_entry(raw: str) -> str | None:
    """Defensive cleaner for env-var values that occasionally include the literal
    `KEY=value` prefix or surrounding whitespace/quotes. Returns None if the
    cleaned value is not a syntactically valid email address.
    """
    candidate = raw.strip().strip('"').strip("'")
    if not candidate:
        return None
    if "=" in candidate:
        # Drop any leading "GMAIL_TO_ADDRESSES=" (or similar) prefix that may
        # have been accidentally pasted into the value field of the env var.
        candidate = candidate.split("=", 1)[1].strip()
    if not _EMAIL_REGEX.match(candidate):
        return None
    return candidate


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: str = Field(default="development", alias="ENVIRONMENT")
    backend_port: int = Field(default=8000, alias="BACKEND_PORT")

    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")
    gemini_daily_call_cap: int = Field(default=20, alias="GEMINI_DAILY_CALL_CAP")
    checkin_gemini_timeout_s: float = Field(default=12.0, alias="CHECKIN_GEMINI_TIMEOUT_S")
    enable_checkin_gemini_response: bool = Field(default=True, alias="ENABLE_CHECKIN_GEMINI_RESPONSE")
    dashboard_narrative_ttl_minutes: int = Field(
        default=360, alias="DASHBOARD_NARRATIVE_TTL_MINUTES"
    )
    dashboard_narrative_timeout_s: float = Field(
        default=15.0, alias="DASHBOARD_NARRATIVE_TIMEOUT_S"
    )
    enable_dashboard_narrative: bool = Field(
        default=True, alias="ENABLE_DASHBOARD_NARRATIVE"
    )

    supabase_url: str = Field(default="", alias="SUPABASE_URL")
    supabase_service_role_key: str = Field(default="", alias="SUPABASE_SERVICE_ROLE_KEY")
    supabase_anon_key: str = Field(default="", alias="SUPABASE_ANON_KEY")
    owner_uid: str = Field(default="", alias="OWNER_UID")

    internal_hmac_secret: str = Field(default="", alias="INTERNAL_HMAC_SECRET")
    feedback_link_secret: str = Field(default="", alias="FEEDBACK_LINK_SECRET")
    checkin_link_secret: str = Field(default="", alias="CHECKIN_LINK_SECRET")

    telegram_bot_token: str = Field(default="", alias="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: str = Field(default="", alias="TELEGRAM_CHAT_ID")
    telegram_webhook_secret: str = Field(default="", alias="TELEGRAM_WEBHOOK_SECRET")

    gmail_client_id: str = Field(default="", alias="GMAIL_CLIENT_ID")
    gmail_client_secret: str = Field(default="", alias="GMAIL_CLIENT_SECRET")
    gmail_refresh_token: str = Field(default="", alias="GMAIL_REFRESH_TOKEN")
    gmail_from_address: str = Field(default="", alias="GMAIL_FROM_ADDRESS")
    gmail_to_addresses_raw: str = Field(default="", alias="GMAIL_TO_ADDRESSES")

    gcal_client_id: str = Field(default="", alias="GCAL_CLIENT_ID")
    gcal_client_secret: str = Field(default="", alias="GCAL_CLIENT_SECRET")
    gcal_refresh_token: str = Field(default="", alias="GCAL_REFRESH_TOKEN")
    gcal_calendar_id: str = Field(default="", alias="GCAL_CALENDAR_ID")

    supabase_db_dsn: str = Field(default="", alias="SUPABASE_DB_DSN")
    supabase_db_dsn_pooler: str = Field(default="", alias="SUPABASE_DB_DSN_POOLER")
    public_base_url: str = Field(default="http://localhost:8000", alias="NEXT_PUBLIC_BACKEND_URL")
    frontend_base_url: str = Field(default="http://localhost:3000", alias="NEXT_PUBLIC_FRONTEND_URL")
    cors_allowed_origins_raw: str = Field(default="", alias="CORS_ALLOWED_ORIGINS")
    allowed_emails_raw: str = Field(default="", alias="ALLOWED_EMAILS")

    @property
    def allowed_emails(self) -> set[str]:
        raw = self.allowed_emails_raw.strip()
        if not raw:
            return set()
        return {entry.strip().lower() for entry in raw.split(",") if entry.strip()}

    @property
    def cors_allowed_origins(self) -> list[str]:
        raw = self.cors_allowed_origins_raw.strip()
        if raw:
            return [entry.strip().rstrip("/") for entry in raw.split(",") if entry.strip()]
        return [self.frontend_base_url.rstrip("/"), "http://localhost:3000"]

    @property
    def gmail_to_addresses(self) -> list[str]:
        raw = self.gmail_to_addresses_raw.strip()
        if not raw:
            return []
        cleaned: list[str] = []
        seen: set[str] = set()
        for entry in raw.split(","):
            normalized = _clean_email_entry(entry)
            if not normalized:
                continue
            lowered = normalized.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            cleaned.append(normalized)
        return cleaned

    @property
    def effective_checkin_link_secret(self) -> str:
        # Prefer a dedicated secret, but fall back to the feedback-link secret
        # so an existing deployment doesn't need a new env var to start working.
        if self.checkin_link_secret:
            return self.checkin_link_secret
        return self.feedback_link_secret

    @property
    def is_localhost_frontend(self) -> bool:
        host = self.frontend_base_url.lower()
        return host.startswith("http://localhost") or host.startswith("http://127.")


settings = Settings()

