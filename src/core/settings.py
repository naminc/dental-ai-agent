"""Validated, side-effect-free application settings."""

from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parents[2]


class Engine(str, Enum):
    OPENAI = "openai"
    LOCAL = "local"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: Literal["development", "test", "production"] = "development"
    log_level: Literal["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"] = "INFO"
    log_file: Path = BASE_DIR / "logs" / "chat.log"
    cors_origins: list[str] = Field(default_factory=list)

    database_url: str = Field(min_length=1)
    secret_key: SecretStr = Field(min_length=1)
    algorithm: str = "HS256"
    access_token_expire_minutes: int = Field(default=60 * 24 * 7, gt=0)

    embedding_engine: Engine = Engine.LOCAL
    llm_engine: Engine = Engine.OPENAI

    openai_api_key: SecretStr | None = None
    openai_base_url: str | None = None
    openai_chat_model: str = "gpt-4.1-mini"
    openai_embedding_model: str = "text-embedding-3-small"
    openai_embedding_dim: int = Field(default=1536, gt=0)

    ollama_base_url: str = "http://localhost:11434/v1"
    ollama_chat_model: str = "qwen2.5:1.5b"

    provider_timeout_seconds: float = Field(default=60.0, gt=0)
    provider_max_retries: int = Field(default=2, ge=0)

    local_embedding_model: str = "keepitreal/vietnamese-sbert"
    local_embedding_dim: int = Field(default=768, gt=0)

    multi_query_expansion: bool = True
    top_k: int = Field(default=10, gt=0)
    vector_db_dir: Path = BASE_DIR / "data" / "vector_db"

    raw_data_path: Path = BASE_DIR / "data" / "raw" / "dental_dataset.json"
    raw_data_v2_path: Path = BASE_DIR / "data" / "raw" / "dental_dataset_v2.json"
    processed_data_path: Path = BASE_DIR / "data" / "processed" / "chunks.json"

    upgrade_dataset_model: str = "gpt-4o-mini"
    auto_pipeline_model: str = "gpt-4.1-mini"

    @field_validator("log_level", mode="before")
    @classmethod
    def normalize_log_level(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value

    @field_validator("openai_base_url", mode="before")
    @classmethod
    def normalize_optional_base_url(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip() or None
        return value

    @field_validator("cors_origins")
    @classmethod
    def validate_cors_origins(cls, origins: list[str]) -> list[str]:
        normalized: list[str] = []
        for origin in origins:
            origin = origin.strip().rstrip("/")
            if origin == "*":
                raise ValueError("CORS_ORIGINS must not contain wildcard '*'")
            parsed = urlsplit(origin)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ValueError(
                    f"CORS origin must be an absolute http(s) origin: {origin!r}"
                )
            if parsed.path or parsed.query or parsed.fragment:
                raise ValueError(
                    f"CORS origin must not contain a path, query, or fragment: {origin!r}"
                )
            if origin not in normalized:
                normalized.append(origin)
        return normalized

    @model_validator(mode="after")
    def validate_engine_credentials(self) -> "Settings":
        uses_openai = (
            self.embedding_engine is Engine.OPENAI
            or self.llm_engine is Engine.OPENAI
        )
        api_key = (
            self.openai_api_key.get_secret_value().strip()
            if self.openai_api_key is not None
            else ""
        )
        if uses_openai and not api_key:
            raise ValueError(
                "OPENAI_API_KEY is required when EMBEDDING_ENGINE or LLM_ENGINE is 'openai'"
            )
        if self.app_env == "production":
            if len(self.secret_key_value) < 32:
                raise ValueError(
                    "SECRET_KEY must contain at least 32 characters in production"
                )
            if not self.cors_origins:
                raise ValueError("CORS_ORIGINS is required in production")
        return self

    @property
    def openai_api_key_value(self) -> str | None:
        if self.openai_api_key is None:
            return None
        value = self.openai_api_key.get_secret_value().strip()
        return value or None

    @property
    def secret_key_value(self) -> str:
        return self.secret_key.get_secret_value()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the single validated settings instance for this process."""
    return Settings()
