from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str = "sqlite:///./test.db"
    poll_interval_sec: int = 5
    batch_size: int = 10


@lru_cache
def get_settings() -> Settings:
    return Settings()
