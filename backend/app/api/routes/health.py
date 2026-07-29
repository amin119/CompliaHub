import psycopg2
import redis
from fastapi import APIRouter, Depends
from minio import Minio
from neo4j import GraphDatabase
from qdrant_client import QdrantClient

from app.core.config import Settings, get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    """Liveness check: is the process up and able to respond at all."""
    return {"status": "ok"}


@router.get("/health/deep")
def health_deep(settings: Settings = Depends(get_settings)):
    """Readiness check: can we actually reach every infra dependency.

    Each service is checked independently and failures are caught individually
    so that one down container reports as "degraded" instead of crashing the
    whole endpoint with a 500 — useful while you're bringing the stack up
    piece by piece.
    """
    results = {}

    try:
        conn = psycopg2.connect(settings.database_url, connect_timeout=2)
        conn.close()
        results["postgres"] = "ok"
    except Exception as exc:
        results["postgres"] = f"error: {exc}"

    try:
        client = redis.from_url(settings.redis_url, socket_connect_timeout=2)
        client.ping()
        results["redis"] = "ok"
    except Exception as exc:
        results["redis"] = f"error: {exc}"

    try:
        driver = GraphDatabase.driver(
            settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password)
        )
        driver.verify_connectivity()
        driver.close()
        results["neo4j"] = "ok"
    except Exception as exc:
        results["neo4j"] = f"error: {exc}"

    try:
        client = QdrantClient(url=settings.qdrant_url, timeout=2)
        client.get_collections()
        results["qdrant"] = "ok"
    except Exception as exc:
        results["qdrant"] = f"error: {exc}"

    try:
        client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
        client.list_buckets()
        results["minio"] = "ok"
    except Exception as exc:
        results["minio"] = f"error: {exc}"

    overall = "ok" if all(v == "ok" for v in results.values()) else "degraded"
    return {"status": overall, "services": results}
