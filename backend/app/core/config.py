from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed application config, loaded from environment variables / backend/.env.

    Using pydantic-settings instead of raw os.environ gives us three things:
    validation (the app fails fast at startup if a var is missing or malformed,
    not mid-request), typed values (REDIS_URL is a str, MINIO_SECURE is a bool,
    no manual parsing), and a single object we can inject via FastAPI's Depends
    instead of importing os.environ everywhere.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"

    database_url: str
    redis_url: str

    neo4j_uri: str
    neo4j_user: str
    neo4j_password: str

    qdrant_url: str

    minio_endpoint: str
    minio_access_key: str
    minio_secret_key: str
    minio_secure: bool = False

    cors_origins: list[str] = ["http://localhost:3000"]


@lru_cache
def get_settings() -> Settings:
    """Cached so Settings() — which reads and validates .env — runs once per
    process, not on every request. FastAPI dependencies re-run per request by
    default, so without this every request would re-parse the env file.
    """
    return Settings()
