"""Application settings using Pydantic BaseSettings."""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "TM Transportadora API"
    app_env: Literal["development", "staging", "production"] = "development"
    app_debug: bool = False
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_workers: int = 1
    app_version: str = "0.1.0"

    # Security
    secret_key: str = "change-me-in-production-min-32-characters-long!!"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    password_reset_token_expire_hours: int = 1

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/tm_transportadora"
    database_url_sync: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/tm_transportadora"

    # Supabase
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_key: str = ""

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    redis_password: str = ""

    # Celery
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    # CORS
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    # Rate Limiting
    rate_limit_per_minute: int = 60
    rate_limit_auth_per_minute: int = 10

    # Registro público de tenant (desligar em produção)
    allow_tenant_registration: bool = True

    # Logging
    log_level: str = "INFO"
    log_format: Literal["json", "console"] = "json"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            raw = v.strip()
            if raw.startswith("["):
                import json

                return json.loads(raw)
            return [origin.strip() for origin in raw.split(",") if origin.strip()]
        return v

    @model_validator(mode="after")
    def _enforce_production_constraints(self) -> Settings:
        if self.app_env == "production":
            _default = (
                "change-me-in-production-min-32-characters-long!!"
            )
            if self.secret_key == _default or len(self.secret_key) < 32:
                raise ValueError(
                    "SECRET_KEY must be changed from default "
                    "and be >= 32 chars in production"
                )
            if self.app_debug:
                raise ValueError(
                    "APP_DEBUG must be false in production"
                )
            if self.allow_tenant_registration:
                raise ValueError(
                    "ALLOW_TENANT_REGISTRATION must be "
                    "false in production"
                )
        return self

    @property
    def database_url_async(self) -> str:
        return self.database_url

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()
