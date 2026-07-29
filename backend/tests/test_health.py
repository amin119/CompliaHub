from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_liveness():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_deep_reports_all_services():
    """Doesn't require the docker containers to be up — just that each
    dependency is checked and reported, healthy or not.
    """
    response = client.get("/health/deep")
    assert response.status_code == 200
    body = response.json()
    assert set(body["services"].keys()) == {
        "postgres",
        "redis",
        "neo4j",
        "qdrant",
        "minio",
    }
