"""Environment-based application configuration.

Settings are loaded from environment variables (and a local .env file in
development). Nothing here should ever contain a real secret value -
defaults are safe placeholders for local development only.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Fraud Intelligence Platform API"
    environment: str = "local"
    api_v1_prefix: str = "/api/v1"

    database_url: str = "postgresql+psycopg://fraud_app:fraud_app@localhost:5432/fraud_intelligence"

    cors_allow_origins: list[str] = ["http://localhost:5173"]

    jwt_secret: str = ""
    aws_region: str = ""
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    bedrock_model_id: str = ""


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance so env vars are parsed once."""
    return Settings()
