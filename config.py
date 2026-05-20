from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )
    bot_token: str = Field(..., alias="BOT_TOKEN")
    webapp_url: str = Field("", alias="WEBAPP_URL")
    superadmin_ids: list[int] = Field(default_factory=list, alias="SUPERADMIN_IDS")

    database_url: str = Field(..., alias="DATABASE_URL")
    redis_url: str = Field("redis://localhost:6379/0", alias="REDIS_URL")

    ai_provider: Literal["openai", "claude", "gemini"] = Field("gemini", alias="AI_PROVIDER")
    ai_model: str = Field("gemini-flash-latest", alias="AI_MODEL")
    openai_api_key: str = Field("", alias="OPENAI_API_KEY")
    anthropic_api_key: str = Field("", alias="ANTHROPIC_API_KEY")
    gemini_api_key: str = Field("", alias="GEMINI_API_KEY")
    log_level: str = Field("INFO", alias="LOG_LEVEL")
    tz: str = Field("UTC", alias="TZ")
    webapp_host: str = Field("0.0.0.0", alias="WEBAPP_HOST")
    webapp_port: int = Field(8080, alias="WEBAPP_PORT")

    @field_validator("superadmin_ids", mode="before")
    @classmethod
    def _split_ids(cls, v):
        if v is None or v == "":
            return []
        if isinstance(v, int):
            return [v]
        if isinstance(v, str):
            return [int(x) for x in v.split(",") if x.strip()]
        return v


settings = Settings()  # type: ignore[call-arg]
