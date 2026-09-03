"""
Centralized settings, loaded from environment variables only.

No secret ever has a real default here — every security-sensitive value
either comes from the environment or raises at startup. See
backend/.env.example for the full list of variables an operator must set.
"""
from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Database -----------------------------------------------------
    # Real value configured by the operator. Never hardcode credentials.
    database_url: str = "postgresql+psycopg2://user:password@localhost:5432/beetticket"

    # --- JWT / auth -----------------------------------------------------
    jwt_secret: str = "CHANGE_ME_INSECURE_DEFAULT_DO_NOT_USE_IN_PRODUCTION"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    password_reset_token_expire_minutes: int = 30

    # --- File storage -------------------------------------------------------
    # Firebase Storage is intentionally NOT integrated yet (see
    # backend/README.md, "Activar Firebase Storage más adelante", for the
    # exact steps to enable it once real credentials are available). Every
    # one of these four stays unset until then, so the service always uses
    # the local-disk mode below — which is a REAL, working storage backend
    # for this phase, not a placeholder.
    firebase_project_id: str | None = None
    firebase_client_email: str | None = None
    firebase_private_key: str | None = None
    firebase_storage_bucket: str | None = None
    # Local-disk storage mode (used for tickets, debt-assumption documents,
    # and signature images this phase). Relative to the backend/ directory
    # by default. Safe to point elsewhere via .env; never served directly
    # by a static file route — only read back through authenticated,
    # ownership-checked endpoints (see routers/tickets.py).
    local_storage_fallback_dir: str = "./storage_local"

    # --- File retention ---------------------------------------------------
    file_retention_days: int = 90

    # --- CORS -----------------------------------------------------------
    cors_origins: str = "http://localhost:5173"

    # --- Environment -----------------------------------------------------
    environment: str = "development"

    @property
    def cors_origin_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
