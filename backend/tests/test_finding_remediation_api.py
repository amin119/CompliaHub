"""Live integration tests for Phase 9's RemediationAgent — structural copy
of `test_finding_validation_api.py`'s pattern. Simpler than Phase 6: no
retrieval involved (no standards to ingest, no Qdrant/embedding/rerank to
mock) — only the Gemini remediation client itself needs mocking.
"""

import io
import uuid
import zipfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.db import engine
from app.main import app
from app.services import finding_remediation, storage
from app.services.finding_remediation import RemediationSuggestion
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


@pytest.fixture(autouse=True)
def _mock_remediation_client(monkeypatch):
    class _FakeRemediationClient:
        def remediate(self, prompt: str) -> RemediationSuggestion:
            return RemediationSuggestion(
                problem_explanation="MD5 is cryptographically broken for password hashing.",
                suggested_code=(
                    "import bcrypt\n\n"
                    "def hash_password(password):\n"
                    "    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()\n"
                ),
                fix_explanation="Replaced MD5 with bcrypt, a dedicated password-hashing KDF.",
                confidence="high",
            )

    monkeypatch.setattr(
        finding_remediation, "get_gemini_remediation_client", lambda: _FakeRemediationClient()
    )


def _sample_repo_zip(marker: str = "") -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as archive:
        archive.writestr(
            "app/auth.py",
            "import hashlib\n"
            "\n"
            "def hash_password(password):\n"
            "    return hashlib.md5(password.encode()).hexdigest()\n",
        )
        archive.writestr("requirements.txt", "fastapi>=0.100.0\n")
        if marker:
            archive.writestr("MARKER.txt", marker)
    return buf.getvalue()


def _upload_and_wait(client: TestClient, data: bytes, filename: str) -> str:
    response = client.post("/scans", files={"file": (filename, data, "application/zip")})
    scan_id = response.json()["id"]
    status_response = client.get(f"/scans/{scan_id}").json()
    assert status_response["iso27001_status"] == "ready"
    return scan_id


def _first_security_finding_id(client: TestClient, scan_id: str) -> str:
    all_findings = client.get(f"/scans/{scan_id}/findings").json()
    findings = [
        f for f in all_findings if f["framework"] is None and f["category"] == "cryptography"
    ]
    return findings[0]["id"]


def test_remediate_finding_creates_llm_remediation_evidence_with_real_file_content():
    client = TestClient(app)
    scan_id = _upload_and_wait(client, _sample_repo_zip(marker="remediate-real"), "r1.zip")
    finding_id = _first_security_finding_id(client, scan_id)

    response = client.post(f"/scans/{scan_id}/findings/{finding_id}/remediate")

    assert response.status_code == 200
    body = response.json()
    assert body["source_type"] == "llm_remediation"
    assert body["rule_id"] == "llm_finding_remediation"
    assert body["file_path"] == "app/auth.py"
    assert "--- a/app/auth.py" in body["snippet"]
    assert "+++ b/app/auth.py" in body["snippet"]
    assert "@@" in body["snippet"]
    assert "bcrypt" in body["snippet"]
    assert body["evidence_metadata"]["target_file_path"] == "app/auth.py"

    # The finding's own status/recommendation must never change as a side effect.
    finding_detail = client.get(f"/scans/{scan_id}/findings/{finding_id}").json()
    assert finding_detail["status"] == "POTENTIAL_NON_COMPLIANCE"
    llm_evidence = [
        e for e in finding_detail["evidence"] if e["source_type"] == "llm_remediation"
    ]
    assert len(llm_evidence) == 1


def test_remediate_finding_404s_for_wrong_scan_or_finding_id():
    client = TestClient(app)
    scan_id = _upload_and_wait(client, _sample_repo_zip(marker="remediate-404"), "r2.zip")
    bogus_finding_id = str(uuid.uuid4())

    response = client.post(f"/scans/{scan_id}/findings/{bogus_finding_id}/remediate")
    assert response.status_code == 404

    bogus_scan_id = str(uuid.uuid4())
    finding_id = _first_security_finding_id(client, scan_id)
    response = client.post(f"/scans/{bogus_scan_id}/findings/{finding_id}/remediate")
    assert response.status_code == 404


def test_remediate_finding_422s_when_no_locatable_evidence():
    client = TestClient(app)
    scan_id = _upload_and_wait(client, _sample_repo_zip(marker="remediate-422"), "r3.zip")

    # ISO27001 control-assessment findings with zero mapped source findings
    # get a synthetic repo_aggregate Evidence row with file_path=None — no
    # concrete code location to generate a fix suggestion against.
    all_findings = client.get(f"/scans/{scan_id}/findings?framework=ISO27001").json()
    not_verified = next(f for f in all_findings if f["status"] == "NOT_VERIFIED")

    response = client.post(f"/scans/{scan_id}/findings/{not_verified['id']}/remediate")

    assert response.status_code == 422


def test_remediate_finding_never_changes_finding_status_or_recommendation():
    client = TestClient(app)
    scan_id = _upload_and_wait(client, _sample_repo_zip(marker="remediate-unchanged"), "r4.zip")
    finding_id = _first_security_finding_id(client, scan_id)

    before = client.get(f"/scans/{scan_id}/findings/{finding_id}").json()
    client.post(f"/scans/{scan_id}/findings/{finding_id}/remediate")
    after = client.get(f"/scans/{scan_id}/findings/{finding_id}").json()

    assert after["status"] == before["status"]
    assert after["recommendation"] == before["recommendation"]
