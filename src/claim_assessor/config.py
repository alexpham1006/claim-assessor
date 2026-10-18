from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    gemini_api_key: SecretStr
    gemini_model: str
    gemini_timeout_seconds: float = Field(default=60.0, gt=0)
    gemini_max_attempts: int = Field(default=3, ge=1, le=5)
    data_dir: Path = Path("data")


@lru_cache
def get_settings() -> Settings:
    return Settings()
