"""Configuration and environment settings for Kairos backend."""
import logging
import secrets
from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

# Fernet keys must be 32-byte urlsafe base64 (44 chars, '='-padded)
_FERNET_KEY_LEN = 44


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App Environment
    APP_NAME: str = "Kairos Ambient Action Agent"
    APP_ENV: Literal["development", "production", "test"] = "development"
    DEBUG: bool = True
    SANDBOX_MODE: bool = False  # Production default: live real API calls to MCP tools

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    @field_validator("DEBUG")
    @classmethod
    def _debug_disallowed_in_production(cls, v: bool, info) -> bool:
        if info.data.get("APP_ENV") == "production" and v:
            raise ValueError("DEBUG must be false when APP_ENV=production")
        return v

    # Authentication (single-operator API key; required in production)
    API_KEY: str | None = Field(default=None, min_length=16)

    @field_validator("API_KEY")
    @classmethod
    def _api_key_required_in_production(cls, v: str | None, info) -> str | None:
        if info.data.get("APP_ENV") == "production" and not v:
            raise ValueError("API_KEY is required when APP_ENV=production")
        return v

    # Postgres Database
    POSTGRES_USER: str = "kairos_user"
    POSTGRES_PASSWORD: str = "kairos_password"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5435
    POSTGRES_DB: str = "kairos_db"

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def SYNC_DATABASE_URL(self) -> str:
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6381
    REDIS_URL: str = "redis://localhost:6381/0"

    # Temporal
    TEMPORAL_HOST: str = "localhost:7234"
    TEMPORAL_NAMESPACE: str = "default"
    TEMPORAL_TASK_QUEUE: str = "kairos-batch-queue"

    # Security & OAuth Vault (AES-256 / Fernet key)
    # Must be provided via environment in production; the default below is a
    # deterministic dev-only key so a fresh checkout boots without setup.
    ENCRYPTION_KEY: str = Field(
        default="eWF5c29tZXJhbmRvbWtleWZvcmRldmVsb3BtZW50MTIzNDU="
    )

    @field_validator("ENCRYPTION_KEY")
    @classmethod
    def _warn_dev_encryption_key(cls, v: str, info) -> str:
        if info.data.get("APP_ENV") == "production" and (
            v == "eWF5c29tZXJhbmRvbWtleWZvcmRldmVsb3BtZW50MTIzNDU="
            or len(v) != _FERNET_KEY_LEN
        ):
            raise ValueError(
                "ENCRYPTION_KEY must be a fresh Fernet key (44-char urlsafe base64) "
                "in production. Generate: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
            )
        return v

    # CORS: exact origins only (no wildcard) in production
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    # LLM Settings
    LLM_PROVIDER: Literal["google", "openai", "anthropic", "mock"] = "google"
    GOOGLE_API_KEY: str | None = None
    OPENAI_API_KEY: str | None = None
    ANTHROPIC_API_KEY: str | None = None
    DEFAULT_MODEL_NAME: str = "gemini-2.5-flash"

    # Ingestion & Guardrail Thresholds
    MAX_INPUT_TOKENS: int = 3000
    MAX_INPUT_CHARS: int = 15000

    # Mem0 Memory
    MEM0_ENABLED: bool = True

    # Langfuse Observability
    LANGFUSE_PUBLIC_KEY: str | None = None
    LANGFUSE_SECRET_KEY: str | None = None
    LANGFUSE_HOST: str = "https://cloud.langfuse.com"


def _generate_dev_encryption_key() -> str:
    """Fresh Fernet key for dev/test sessions that provide none."""
    from cryptography.fernet import Fernet

    return Fernet.generate_key().decode()


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor; validates once at first use."""
    try:
        return Settings()
    except Exception as e:
        # dev/test: auto-provision a fresh key so the app still boots, then warn
        import os

        if os.getenv("APP_ENV") in (None, "", "development", "test"):
            os.environ["ENCRYPTION_KEY"] = _generate_dev_encryption_key()
            logger.warning(
                "ENCRYPTION_KEY missing/invalid — generated an ephemeral dev key. "
                "OAuth tokens saved now will be unreadable after restart. "
                "Set a persistent key in .env for real use."
            )
            return Settings()
        raise


settings = get_settings()
