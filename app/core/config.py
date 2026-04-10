from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # App
    APP_ENV: str = "development"
    SECRET_KEY: str = "change-me-in-production-min-32-chars!!"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    # Supabase
    SUPABASE_URL: str
    SUPABASE_SERVICE_ROLE_KEY: str

    # Anthropic
    ANTHROPIC_API_KEY: str
    ANTHROPIC_MODEL: str = "claude-sonnet-4-20250514"

    # Resend
    RESEND_API_KEY: str = ""
    RESEND_FROM_EMAIL: str = "alerts@academiq.app"
    RESEND_FROM_NAME: str = "AcademIQ Alerts"

    # CORS — comma-separated origins
    ALLOWED_ORIGINS: str = "http://localhost:5173"

    # Risk thresholds
    RISK_RED_THRESHOLD: int = 70
    RISK_AMBER_THRESHOLD: int = 45

    @property
    def origins_list(self) -> list[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",")]

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
