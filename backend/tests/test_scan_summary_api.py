"""Live integration tests for Phase 8's scan-summary endpoint — structural
copy of `test_finding_review_api.py`'s scaffolding. No LLM/embedding
mocking needed: this phase makes zero external calls.
"""

import io
import uuid
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
            conn.execute(text("SELECT 1 FROM finding_reviews LIMIT 1"))
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
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as archive:
        archive.writestr(
            "app/auth.py",
            "AWS_KEY = \"AKIA\" + \"IOSFODNN7EXAMPLE\"\n",
        )
        archive.writestr("requirements.txt", "fastapi>=0.100.0\n")
        if marker:
            archive.writestr("MARKER.txt", marker)
    return buf.getvalue()


def _upload_and_wait(client: TestClient, data: bytes, filename: str) -> str:
    response = client.post("/scans", files={"file": (filename, data, "application/zip")})
    scan_id = response.json()["id"]
    status_response = client.get(f"/scans/{scan_id}").json()
    assert status_response["findings_status"] == "ready"
    return scan_id


def test_summary_404s_for_bogus_scan_id():
    client = TestClient(app)
    response = client.get(f"/scans/{uuid.uuid4()}/summary")
    assert response.status_code == 404


def test_summary_metadata_matches_scan_and_findings():
    client = TestClient(app)
    scan_id = _upload_and_wait(client, _sample_repo_zip(marker="summary-metadata"), "s1.zip")

    scan = client.get(f"/scans/{scan_id}").json()
    findings = client.get(f"/scans/{scan_id}/findings").json()
    summary = client.get(f"/scans/{scan_id}/summary").json()

    assert summary["scan_id"] == scan_id
    assert summary["original_filename"] == scan["original_filename"]
    assert summary["detected_languages"] == scan["detected_languages"]
    assert summary["detected_frameworks"] == scan["detected_frameworks"]
    assert summary["file_count"] == scan["file_count"]
    assert summary["status"] == scan["status"]
    assert summary["findings_status"] == scan["findings_status"]
    assert summary["privacy_status"] == scan["privacy_status"]
    assert summary["ai_status"] == scan["ai_status"]
    assert summary["iso27001_status"] == scan["iso27001_status"]
    assert summary["total_findings"] == len(findings)
    assert "generated_at" in summary


def test_summary_breakdowns_zero_fill_and_sum_to_total():
    client = TestClient(app)
    scan_id = _upload_and_wait(client, _sample_repo_zip(marker="summary-breakdowns"), "s2.zip")
    summary = client.get(f"/scans/{scan_id}/summary").json()

    severity_names = {c["severity"] for c in summary["severity_counts"]}
    assert severity_names == {"CRITICAL", "HIGH", "MEDIUM", "LOW", "INFORMATIONAL"}
    assert sum(c["count"] for c in summary["severity_counts"]) == summary["total_findings"]

    status_names = {c["status"] for c in summary["status_counts"]}
    assert status_names == {
        "VERIFIED",
        "PARTIALLY_VERIFIED",
        "NOT_VERIFIED",
        "POTENTIAL_NON_COMPLIANCE",
        "NOT_APPLICABLE",
        "REQUIRES_HUMAN_REVIEW",
    }
    assert sum(c["count"] for c in summary["status_counts"]) == summary["total_findings"]

    framework_names = {c["framework"] for c in summary["framework_counts"]}
    assert framework_names == {None, "GDPR", "ISO42001", "ISO27001"}
    assert sum(c["count"] for c in summary["framework_counts"]) == summary["total_findings"]


def test_summary_never_includes_a_score_or_percentage_field():
    """Direct regression test for the standing 'technical evidence
    coverage, not certification' constraint — this response must only ever
    carry raw counts, never a synthesized score/percentage/grade."""
    client = TestClient(app)
    scan_id = _upload_and_wait(client, _sample_repo_zip(marker="summary-no-score"), "s3.zip")
    summary = client.get(f"/scans/{scan_id}/summary").json()

    forbidden_terms = ("score", "percent", "grade", "rating")
    for key in summary:
        assert not any(term in key.lower() for term in forbidden_terms), key
    for key in summary["review_coverage"]:
        assert not any(term in key.lower() for term in forbidden_terms), key


def test_review_coverage_before_any_review():
    client = TestClient(app)
    scan_id = _upload_and_wait(client, _sample_repo_zip(marker="summary-before-review"), "s4.zip")
    findings = client.get(f"/scans/{scan_id}/findings").json()
    summary = client.get(f"/scans/{scan_id}/summary").json()
    coverage = summary["review_coverage"]

    expected_flagged = sum(1 for f in findings if f["human_review_required"])
    assert coverage["reviewed_findings"] == 0
    assert coverage["unreviewed_findings"] == coverage["total_findings"]
    assert coverage["requires_human_review_unreviewed_count"] == expected_flagged
    assert coverage["total_reviews"] == 0


def test_review_coverage_updates_after_submitting_a_review():
    client = TestClient(app)
    scan_id = _upload_and_wait(client, _sample_repo_zip(marker="summary-after-review"), "s5.zip")
    findings = client.get(f"/scans/{scan_id}/findings").json()
    flagged = next(f for f in findings if f["human_review_required"])
    before = client.get(f"/scans/{scan_id}/summary").json()["review_coverage"]

    client.post(
        f"/scans/{scan_id}/findings/{flagged['id']}/reviews",
        json={"decision": "VERIFIED", "notes": "Manually confirmed this is not an issue."},
    )
    after = client.get(f"/scans/{scan_id}/summary").json()["review_coverage"]

    assert after["reviewed_findings"] == before["reviewed_findings"] + 1
    assert after["unreviewed_findings"] == before["unreviewed_findings"] - 1
    assert after["total_reviews"] == before["total_reviews"] + 1
    assert (
        after["requires_human_review_unreviewed_count"]
        == before["requires_human_review_unreviewed_count"] - 1
    )

    # A second review on the same finding still counts it as reviewed once.
    client.post(
        f"/scans/{scan_id}/findings/{flagged['id']}/reviews",
        json={"decision": "REQUIRES_HUMAN_REVIEW", "notes": "Escalating to a second reviewer."},
    )
    final = client.get(f"/scans/{scan_id}/summary").json()["review_coverage"]
    assert final["reviewed_findings"] == after["reviewed_findings"]
    assert final["total_reviews"] == after["total_reviews"] + 1
