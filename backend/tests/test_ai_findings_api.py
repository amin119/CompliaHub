"""Live integration tests for Phase 4's AI/ISO 42001 pipeline stage —
structural copy of `test_privacy_findings_api.py`'s pattern (Phase 3's
own live-infra template), extended to a three-framework partition and the
bidirectional delete-scoping regression across all three rule-pass tasks.
"""

import io
import zipfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.db import engine
from app.main import app
from app.services import storage
from app.tasks.celery_app import celery_app


def _infra_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1 FROM findings LIMIT 1"))
        storage.get_minio_client().list_buckets()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _infra_available(),
    reason="requires docker compose up (postgres+redis+minio) with migrations applied",
)


@pytest.fixture(autouse=True, scope="module")
def _eager_celery():
    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True
    yield
    celery_app.conf.task_always_eager = False
    celery_app.conf.task_eager_propagates = False


def _sample_repo_zip(marker: str = "") -> bytes:
    """A repo with content relevant to all three frameworks: Phase 2's
    security rules, Phase 3's GDPR rules, and Phase 4's AI rules (an
    `openai` import, a prompt-shaped string, a `qdrant_client` import
    co-located with `.embed(`, and a `@tool`-decorated function — at
    least two independent AI signal types, clearing the inventory
    threshold).
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as archive:
        archive.writestr(
            "app/auth.py",
            "import hashlib\n"
            "\n"
            "AWS_KEY = \"AKIAIOSFODNN7EXAMPLE\"\n"
            "\n"
            "def hash_password(password):\n"
            "    return hashlib.md5(password.encode()).hexdigest()\n"
            "\n"
            "def log_user(user):\n"
            "    logger.info(user.email)\n",
        )
        archive.writestr(
            "app/models.py",
            "class User(Base):\n"
            "    email = mapped_column(String)\n"
            "    ssn = mapped_column(String)\n",
        )
        archive.writestr(
            "app/ai.py",
            "import openai\n"
            "import qdrant_client\n"
            "\n"
            "SYSTEM_PROMPT = \"You are a helpful compliance assistant.\"\n"
            "\n"
            "@tool\n"
            "def search_docs(query):\n"
            "    return qdrant_client.QdrantClient().embed(query)\n",
        )
        archive.writestr("requirements.txt", "fastapi>=0.100.0\nrequests\n")
        if marker:
            archive.writestr("MARKER.txt", marker)
    return buf.getvalue()


def _upload_and_wait(client: TestClient, data: bytes, filename: str) -> str:
    response = client.post("/scans", files={"file": (filename, data, "application/zip")})
    scan_id = response.json()["id"]
    status_response = client.get(f"/scans/{scan_id}").json()
    # Eager mode runs the whole 5-stage chain synchronously.
    assert status_response["findings_status"] == "ready"
    assert status_response["privacy_status"] == "ready"
    assert status_response["ai_status"] == "ready"
    return scan_id


def test_three_way_framework_partition():
    client = TestClient(app)
    scan_id = _upload_and_wait(client, _sample_repo_zip(), "combined-repo.zip")

    all_findings = client.get(f"/scans/{scan_id}/findings").json()
    frameworks = {f["framework"] for f in all_findings}
    assert frameworks == {None, "GDPR", "ISO42001"}


def test_ai_findings_include_inventory_and_expected_categories():
    client = TestClient(app)
    scan_id = _upload_and_wait(client, _sample_repo_zip(marker="ai-categories"), "ai-cat.zip")

    ai_findings = client.get(f"/scans/{scan_id}/findings?framework=ISO42001").json()
    categories = {f["category"] for f in ai_findings}
    assert "ai_system_detection" in categories  # openai/qdrant_client imports
    assert "prompt_detection" in categories  # SYSTEM_PROMPT string
    assert "agentic_pattern_detection" in categories  # @tool decorator
    assert "rag_detection" in categories  # qdrant_client + .embed(
    # Threshold met (>=2 signal types) -> inventory + governance findings.
    assert "ai_system_inventory" in categories
    assert "ai_system_documentation" in categories
    assert "human_oversight" in categories


def test_ai_system_inventory_evidence_metadata_shape():
    client = TestClient(app)
    scan_id = _upload_and_wait(client, _sample_repo_zip(marker="inventory-shape"), "inv.zip")

    ai_findings = client.get(f"/scans/{scan_id}/findings?framework=ISO42001").json()
    inventory_finding = next(f for f in ai_findings if f["category"] == "ai_system_inventory")

    detail = client.get(f"/scans/{scan_id}/findings/{inventory_finding['id']}").json()
    assert detail["evidence"], "expected at least one evidence row"
    metadata = detail["evidence"][0]["evidence_metadata"]
    assert metadata["human_oversight"] == "unknown"
    assert metadata["uses_rag"] is True
    assert "OpenAI" in {m["provider"] for m in metadata["models"]}


def test_rerunning_ai_analyzers_does_not_wipe_security_or_gdpr_findings():
    from app.tasks.scan import run_ai_analyzers_task

    client = TestClient(app)
    scan_id = _upload_and_wait(client, _sample_repo_zip(marker="ai-rerun"), "ai-rerun.zip")

    def _counts():
        findings = client.get(f"/scans/{scan_id}/findings").json()
        return (
            len([f for f in findings if f["framework"] is None]),
            len([f for f in findings if f["framework"] == "GDPR"]),
            len([f for f in findings if f["framework"] == "ISO42001"]),
        )

    security_before, gdpr_before, ai_before = _counts()
    assert security_before > 0 and gdpr_before > 0 and ai_before > 0

    run_ai_analyzers_task(scan_id)

    security_after, gdpr_after, ai_after = _counts()
    assert security_after == security_before
    assert gdpr_after == gdpr_before
    assert ai_after == ai_before  # rebuilt, not doubled


def test_rerunning_security_or_privacy_analyzers_does_not_wipe_ai_findings():
    from app.tasks.scan import run_privacy_analyzers_task, run_security_analyzers_task

    client = TestClient(app)
    scan_id = _upload_and_wait(client, _sample_repo_zip(marker="other-rerun"), "other-rerun.zip")

    def _ai_count():
        findings = client.get(f"/scans/{scan_id}/findings?framework=ISO42001").json()
        return len(findings)

    ai_before = _ai_count()
    assert ai_before > 0

    run_security_analyzers_task(scan_id)
    assert _ai_count() == ai_before  # untouched by the security rerun

    run_privacy_analyzers_task(scan_id)
    assert _ai_count() == ai_before  # untouched by the GDPR rerun too
