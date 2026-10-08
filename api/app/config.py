from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = (
        "postgresql+psycopg://deploywatch:deploywatch@localhost:5433/deploywatch"
    )

    checker_concurrency: int = 50
    incident_open_after: int = 3
    incident_close_after: int = 2

    # Auth (Supabase). Leave SUPABASE_URL empty to run with auth off locally.
    supabase_url: str = ""
    supabase_jwt_secret: str = ""  # only for legacy HS256 projects
    owner_user_id: str = ""
    # Allow monitors/webhooks to target localhost and private networks.
    allow_private_targets: bool = False

    cors_origins: str = "http://localhost:5173"

    smtp_host: str = "localhost"
    smtp_port: int = 1025
    # Mailpit needs none of these. A real provider (Resend, Brevo, Gmail...)
    # needs username/password and usually STARTTLS on port 587.
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_starttls: bool = False
    alert_from: str = "alerts@deploywatch.local"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
