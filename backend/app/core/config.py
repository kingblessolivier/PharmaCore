"""Application configuration (12-factor via environment variables).

Business rules (statutory rates, insurance schemes, tax classes) live in the
database, not here — see docs/development/environments-and-config.md.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings, read from environment / .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "PharmaCore API"
    version: str = "0.0.0"
    # dev | staging | production
    medlink_env: str = "dev"

    # SQLite default keeps the app bootable with no external services;
    # production/staging override with a PostgreSQL URL.
    database_url: str = "sqlite+pysqlite:///./pharmacore_dev.db"

    # Auth
    secret_key: str = "change-me-in-production"
    jwt_access_ttl_minutes: int = 30

    log_level: str = "info"


settings = Settings()
