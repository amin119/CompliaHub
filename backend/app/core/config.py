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

    # Defaults match docker-compose.yml's dev credentials — not real secrets,
    # so the app and test suite work out of the box without a .env file (e.g.
    # in CI, or right after a fresh clone). Real deployments override via env
    # vars or a backend/.env.
    database_url: str = (
        "postgresql://compliancegraph:compliancegraph_dev@localhost:5432/compliancegraph"
    )
    redis_url: str = "redis://localhost:6379/0"

    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "compliancegraph_dev"

    qdrant_url: str = "http://localhost:6333"

    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "compliancegraph"
    minio_secret_key: str = "compliancegraph_dev"
    minio_secure: bool = False

    cors_origins: list[str] = ["http://localhost:3000"]

    # Phase 2 — vector layer. Empty-string defaults keep the app booting
    # without a .env, same as every other setting; real embed/rerank/answer
    # calls fail loudly at call time if a key is missing, not at startup.
    voyage_api_key: str = ""
    voyage_model: str = "voyage-law-2"
    cohere_api_key: str = ""
    cohere_rerank_model: str = "rerank-v3.5"
    # Grok (xAI) exposes an OpenAI-compatible Chat Completions API — answer
    # generation uses the `openai` SDK pointed at xAI's base_url instead of a
    # dedicated xAI SDK.
    grok_api_key: str = ""
    grok_base_url: str = "https://api.x.ai/v1"
    answer_model: str = "grok-4.5"

    # Phase 3 — entity/relation extraction. Cheap/fast model since this runs
    # once per chunk across the whole corpus, unlike Phase 2's one-shot
    # answer generation.
    anthropic_api_key: str = ""
    anthropic_extraction_model: str = "claude-haiku-4-5-20251001"


@lru_cache
def get_settings() -> Settings:
    """Cached so Settings() — which reads and validates .env — runs once per
    process, not on every request. FastAPI dependencies re-run per request by
    default, so without this every request would re-parse the env file.
    """
    return Settings()
