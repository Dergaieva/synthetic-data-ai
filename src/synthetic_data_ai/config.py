"""Typed application configuration."""

from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration loaded from environment variables and an optional `.env` file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="SYNTH_",
        extra="ignore",
    )

    app_name: str = "Synthetic Data Studio"
    environment: Literal["development", "test", "production"] = "development"
    database_url: str = "sqlite+pysqlite:///./synthetic_data.db"
    google_cloud_project: str = Field(
        default="gd-gcp-gridu-genai",
        validation_alias=AliasChoices("GOOGLE_CLOUD_PROJECT", "SYNTH_GOOGLE_CLOUD_PROJECT"),
    )
    google_cloud_location: str = Field(
        default="global",
        validation_alias=AliasChoices("GOOGLE_CLOUD_LOCATION", "SYNTH_GOOGLE_CLOUD_LOCATION"),
    )
    use_vertex_ai: bool = Field(
        default=True,
        validation_alias=AliasChoices("GOOGLE_GENAI_USE_VERTEXAI", "SYNTH_USE_VERTEX_AI"),
    )
    gemini_model: str = "gemini-2.5-flash"
    langfuse_public_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("LANGFUSE_PUBLIC_KEY", "SYNTH_LANGFUSE_PUBLIC_KEY"),
    )
    langfuse_secret_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("LANGFUSE_SECRET_KEY", "SYNTH_LANGFUSE_SECRET_KEY"),
    )
    langfuse_host: str = Field(
        default="https://cloud.langfuse.com",
        validation_alias=AliasChoices("LANGFUSE_HOST", "SYNTH_LANGFUSE_HOST"),
    )

    @property
    def langfuse_enabled(self) -> bool:
        """Return whether both credentials required for tracing are configured."""

        return bool(self.langfuse_public_key and self.langfuse_secret_key)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached settings instance for dependency injection."""

    return Settings()
