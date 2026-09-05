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

    # Phase 3 — entity/relation extraction. Cheap/free-tier model since this
    # runs once per chunk across the whole corpus, unlike Phase 2/6's one-shot
    # answer generation. Gemini's free tier has both per-minute and per-day
    # quotas — worth checking aistudio.google.com for current limits on
    # whichever model is set here before assuming a number.
    gemini_api_key: str = ""
    gemini_extraction_model: str = "gemini-3.1-flash-lite"
    # Phase 6 Part 2: answer generation moved off Grok (xAI) onto Gemini too —
    # the xAI account's zero-credits billing block had made every "live" test
    # since Phase 2 mock this one call, which meant streaming could never be
    # verified for real. Kept as its own setting (not reusing
    # gemini_extraction_model) since the final answer is a different quality
    # bar than per-chunk extraction and may warrant a heavier model later.
    gemini_answer_model: str = "gemini-3.1-flash-lite"
    # Compliance scanner Phase 6 (Agentic RAG): FindingValidationAgent's own
    # setting, not reused from gemini_extraction_model — judging retrieved
    # standard text against a finding's evidence is closer to answer
    # generation's reasoning bar than the classifier's four-way routing.
    gemini_validation_model: str = "gemini-3.1-flash-lite"
    # Compliance scanner Phase 9 (Auto Remediation): RemediationAgent's own
    # setting, not reused from gemini_validation_model — a code-fix
    # suggestion is a different task shape (structured diff-relevant
    # output) even though today's default model is the same.
    gemini_remediation_model: str = "gemini-3.1-flash-lite"
    # Platform Phase 7 (Evaluation Harness): the LLM-judge's own setting —
    # scoring faithfulness/relevance/precision/recall is yet another
    # distinct task shape from every model above, even sharing today's
    # default.
    gemini_eval_model: str = "gemini-3.1-flash-lite"


@lru_cache
def get_settings() -> Settings:
    """Cached so Settings() — which reads and validates .env — runs once per
    process, not on every request. FastAPI dependencies re-run per request by
    default, so without this every request would re-parse the env file.
    """
    return Settings()
