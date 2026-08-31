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


def _sample_vulnerable_repo_zip(marker: str = "") -> bytes:
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
        archive.writestr("requirements.txt", "fastapi>=0.100.0\nrequests\n")
        if marker:
            # A harmless extra file, present only to make this archive's
            # bytes (and therefore its sha256 hash) distinct from another
            # call's — the upload endpoint dedupes by hash, so two
            # genuinely different `Scan` rows need genuinely different
            # bytes, not just a different filename passed to `/scans`.
            archive.writestr("MARKER.txt", marker)
    return buf.getvalue()


def _upload_and_wait_for_findings(client: TestClient, data: bytes, filename: str) -> str:
    response = client.post("/scans", files={"file": (filename, data, "application/zip")})
    scan_id = response.json()["id"]
    status_response = client.get(f"/scans/{scan_id}")
    assert status_response.json()["findings_status"] == "ready"
    return scan_id


def test_findings_generated_end_to_end():
    client = TestClient(app)
    data = _sample_vulnerable_repo_zip()
    scan_id = _upload_and_wait_for_findings(client, data, "vulnerable-repo.zip")

    findings = client.get(f"/scans/{scan_id}/findings").json()
    categories = {f["category"] for f in findings}
    assert "secrets" in categories
    assert "cryptography" in categories
    assert "logging" in categories
    assert "dependencies" in categories

    secret_finding = next(f for f in findings if f["category"] == "secrets")
    assert secret_finding["severity"] == "CRITICAL"

    crypto_finding = next(f for f in findings if f["category"] == "cryptography")
    assert crypto_finding["severity"] == "HIGH"  # hash_password context


def test_finding_detail_includes_redacted_evidence_snippet():
    client = TestClient(app)
    data = _sample_vulnerable_repo_zip()
    scan_id = _upload_and_wait_for_findings(client, data, "vulnerable-repo-2.zip")

    findings = client.get(f"/scans/{scan_id}/findings").json()
    secret_finding = next(f for f in findings if f["category"] == "secrets")

    detail = client.get(f"/scans/{scan_id}/findings/{secret_finding['id']}").json()
    assert detail["evidence"], "expected at least one evidence row"
    for evidence in detail["evidence"]:
        assert "AKIAIOSFODNN7EXAMPLE" not in (evidence["snippet"] or "")


def test_findings_filter_by_category():
    client = TestClient(app)
    data = _sample_vulnerable_repo_zip()
    scan_id = _upload_and_wait_for_findings(client, data, "vulnerable-repo-3.zip")

    filtered = client.get(f"/scans/{scan_id}/findings?category=secrets").json()
    assert filtered
    assert all(f["category"] == "secrets" for f in filtered)


def test_findings_filter_by_severity():
    client = TestClient(app)
    data = _sample_vulnerable_repo_zip()
    scan_id = _upload_and_wait_for_findings(client, data, "vulnerable-repo-4.zip")

    filtered = client.get(f"/scans/{scan_id}/findings?severity=CRITICAL").json()
    assert filtered
    assert all(f["severity"] == "CRITICAL" for f in filtered)


def test_get_finding_404_for_wrong_scan():
    client = TestClient(app)
    scan_id_a = _upload_and_wait_for_findings(
        client, _sample_vulnerable_repo_zip(), "vulnerable-repo-5.zip"
    )
    scan_id_b = _upload_and_wait_for_findings(
        client, _sample_vulnerable_repo_zip(marker="b"), "vulnerable-repo-6.zip"
    )

    findings_a = client.get(f"/scans/{scan_id_a}/findings").json()
    # A finding that really belongs to scan A must 404 when looked up under scan B.
    response = client.get(f"/scans/{scan_id_b}/findings/{findings_a[0]['id']}")
    assert response.status_code == 404


def test_rerunning_security_analyzers_does_not_duplicate_findings():
    """Same real-bug shape this pipeline already hit once for
    RepositoryFile rows: rerunning the security-analysis stage in
    isolation must be a no-op on finding count, not additive.
    """
    from app.tasks.scan import run_security_analyzers_task

    client = TestClient(app)
    data = _sample_vulnerable_repo_zip()
    scan_id = _upload_and_wait_for_findings(client, data, "vulnerable-repo-7.zip")

    first_count = len(client.get(f"/scans/{scan_id}/findings").json())
    assert first_count > 0

    run_security_analyzers_task(scan_id)

    second_count = len(client.get(f"/scans/{scan_id}/findings").json())
    assert second_count == first_count
