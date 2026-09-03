"""Live integration tests for Phase 5's ISO 27001 mapping pipeline stage —
structural copy of `test_ai_findings_api.py`'s pattern, extended to a
four-way framework partition and the bidirectional delete-scoping
regression across all four rule-pass tasks.
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
    """A repo with content relevant to all four frameworks: Phase 2's
    security rules (a hardcoded AWS key -> `secrets` -> A.8.24/A.8.5),
    Phase 3's GDPR rules, and Phase 4's AI rules — same fixture shape as
    `test_ai_findings_api.py`'s, since Phase 5 needs upstream findings
    from all three prior frameworks to map from.
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
    # Eager mode runs the whole 6-stage chain synchronously.
    assert status_response["findings_status"] == "ready"
    assert status_response["privacy_status"] == "ready"
    assert status_response["ai_status"] == "ready"
    assert status_response["iso27001_status"] == "ready"
    return scan_id


def test_four_way_framework_partition():
    client = TestClient(app)
    scan_id = _upload_and_wait(client, _sample_repo_zip(), "combined-repo-iso.zip")

    all_findings = client.get(f"/scans/{scan_id}/findings").json()
    frameworks = {f["framework"] for f in all_findings}
    assert frameworks == {None, "GDPR", "ISO42001", "ISO27001"}


def test_iso27001_produces_one_finding_per_catalogued_control():
    client = TestClient(app)
    scan_id = _upload_and_wait(client, _sample_repo_zip(marker="one-per-control"), "one.zip")

    iso_findings = client.get(f"/scans/{scan_id}/findings?framework=ISO27001").json()
    assert len(iso_findings) == 48
    rule_ids = {f["rule_id"] for f in iso_findings}
    assert len(rule_ids) == 48


def test_iso27001_never_produces_verified_or_partially_verified():
    client = TestClient(app)
    scan_id = _upload_and_wait(client, _sample_repo_zip(marker="never-verified"), "nv.zip")

    iso_findings = client.get(f"/scans/{scan_id}/findings?framework=ISO27001").json()
    statuses = {f["status"] for f in iso_findings}
    assert "VERIFIED" not in statuses
    assert "PARTIALLY_VERIFIED" not in statuses


def test_not_automatable_control_always_requires_human_review():
    client = TestClient(app)
    scan_id = _upload_and_wait(client, _sample_repo_zip(marker="not-automatable"), "na.zip")

    iso_findings = client.get(f"/scans/{scan_id}/findings?framework=ISO27001").json()
    a81 = next(f for f in iso_findings if f["rule_id"] == "A.8.1")
    assert a81["status"] == "REQUIRES_HUMAN_REVIEW"


def test_hardcoded_secret_traces_to_a824_potential_non_compliance():
    client = TestClient(app)
    scan_id = _upload_and_wait(client, _sample_repo_zip(marker="a824-trace"), "a824.zip")

    security_findings = client.get(f"/scans/{scan_id}/findings").json()
    source_finding = next(
        f
        for f in security_findings
        if f["framework"] is None and f["category"] == "secrets"
    )

    iso_findings = client.get(f"/scans/{scan_id}/findings?framework=ISO27001").json()
    a824 = next(f for f in iso_findings if f["rule_id"] == "A.8.24")
    assert a824["status"] == "POTENTIAL_NON_COMPLIANCE"

    detail = client.get(f"/scans/{scan_id}/findings/{a824['id']}").json()
    control_mapping_evidence = [
        e for e in detail["evidence"] if e["source_type"] == "control_mapping"
    ]
    assert control_mapping_evidence
    source_finding_ids = {
        e["evidence_metadata"]["source_finding_id"] for e in control_mapping_evidence
    }
    assert source_finding["id"] in source_finding_ids


def test_control_with_zero_mapped_findings_is_not_verified_with_synthetic_evidence():
    client = TestClient(app)
    scan_id = _upload_and_wait(client, _sample_repo_zip(marker="zero-mapped"), "zero.zip")

    iso_findings = client.get(f"/scans/{scan_id}/findings?framework=ISO27001").json()
    # A.8.23 (web filtering) has no category mapped to it anywhere in
    # CATEGORY_TO_CONTROLS, so it should always be zero-mapped.
    a823 = next(f for f in iso_findings if f["rule_id"] == "A.8.23")
    assert a823["status"] == "NOT_VERIFIED"

    detail = client.get(f"/scans/{scan_id}/findings/{a823['id']}").json()
    assert len(detail["evidence"]) == 1
    assert detail["evidence"][0]["source_type"] == "repo_aggregate"


def test_rerunning_iso27001_analyzers_does_not_wipe_other_frameworks():
    from app.tasks.scan import run_iso27001_analyzers_task

    client = TestClient(app)
    scan_id = _upload_and_wait(client, _sample_repo_zip(marker="iso-rerun"), "iso-rerun.zip")

    def _counts():
        findings = client.get(f"/scans/{scan_id}/findings").json()
        return (
            len([f for f in findings if f["framework"] is None]),
            len([f for f in findings if f["framework"] == "GDPR"]),
            len([f for f in findings if f["framework"] == "ISO42001"]),
            len([f for f in findings if f["framework"] == "ISO27001"]),
        )

    security_before, gdpr_before, ai_before, iso_before = _counts()
    assert security_before > 0 and gdpr_before > 0 and ai_before > 0 and iso_before == 48

    run_iso27001_analyzers_task(scan_id)

    security_after, gdpr_after, ai_after, iso_after = _counts()
    assert security_after == security_before
    assert gdpr_after == gdpr_before
    assert ai_after == ai_before
    assert iso_after == iso_before  # rebuilt, not doubled


@pytest.mark.parametrize(
    "task_name",
    [
        "run_security_analyzers_task",
        "run_privacy_analyzers_task",
        "run_ai_analyzers_task",
    ],
)
def test_rerunning_any_upstream_analyzer_does_not_change_iso27001_finding_count(task_name):
    """The four-way extension of the bidirectional delete-scoping
    regression: rerunning any one of the four rule-pass tasks must never
    change the finding counts of the other three."""
    import app.tasks.scan as scan_tasks

    client = TestClient(app)
    scan_id = _upload_and_wait(
        client, _sample_repo_zip(marker=f"upstream-rerun-{task_name}"), f"{task_name}.zip"
    )

    def _iso_count():
        findings = client.get(f"/scans/{scan_id}/findings?framework=ISO27001").json()
        return len(findings)

    iso_before = _iso_count()
    assert iso_before == 48

    task = getattr(scan_tasks, task_name)
    task(scan_id)

    assert _iso_count() == iso_before
