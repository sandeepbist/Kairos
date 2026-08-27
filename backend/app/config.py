"""Configuration and environment settings for Kairos backend."""
from typing import Literal
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
import base64
import os
from cryptography.fernet import Fernet


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
    SANDBOX_MODE: bool = True  # Allows full offline demo with zero OAuth friction

    # Postgres Database
    POSTGRES_USER: str = "kairos_user"
    POSTGRES_PASSWORD: str = "kairos_password"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5435
    POSTGRES_DB: str = "kairos_db"

    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    @property
    def SYNC_DATABASE_URL(self) -> str:
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6381
    REDIS_URL: str = "redis://localhost:6381/0"

    # Temporal
    TEMPORAL_HOST: str = "localhost:7234"
    TEMPORAL_NAMESPACE: str = "default"
    TEMPORAL_TASK_QUEUE: str = "kairos-batch-queue"

    # Security & OAuth Vault (AES-256 / Fernet key)
    # Default generated fallback key for development if not in .env
    ENCRYPTION_KEY: str = Field(
        default="eWF5c29tZXJhbmRvbWtleWZvcmRldmVsb3BtZW50MTIzNDU="
    )

    # LLM Settings
    LLM_PROVIDER: Literal["google", "openai", "anthropic", "mock"] = "google"
    GOOGLE_API_KEY: str | None = None
    OPENAI_API_KEY: str | None = None
    ANTHROPIC_API_KEY: str | None = None
    DEFAULT_MODEL_NAME: str = "gemini-2.0-flash"

    # Ingestion & Guardrail Thresholds
    MAX_INPUT_TOKENS: int = 3000
    MAX_INPUT_CHARS: int = 15000

    # Mem0 Memory
    MEM0_ENABLED: bool = True

    # Langfuse Observability
    LANGFUSE_PUBLIC_KEY: str | None = None
    LANGFUSE_SECRET_KEY: str | None = None
    LANGFUSE_HOST: str = "https://cloud.langfuse.com"


settings = Settings()
