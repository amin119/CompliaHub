"""Live integration tests for Phase 7's Human Review endpoint — structural
copy of `test_iso27001_findings_api.py`'s scaffolding. No LLM/embedding
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


def _first_finding_id(client: TestClient, scan_id: str) -> str:
    findings = client.get(f"/scans/{scan_id}/findings").json()
    return findings[0]["id"]


def test_create_review_updates_finding_status():
    client = TestClient(app)
    scan_id = _upload_and_wait(client, _sample_repo_zip(marker="review-status"), "r1.zip")
    finding_id = _first_finding_id(client, scan_id)
    original_status = client.get(f"/scans/{scan_id}/findings/{finding_id}").json()["status"]

    response = client.post(
        f"/scans/{scan_id}/findings/{finding_id}/reviews",
        json={
            "reviewer_name": "Jane Doe",
            "decision": "NOT_APPLICABLE",
            "notes": "This key only appears in a test fixture, not production code.",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["previous_status"] == original_status
    assert body["decision"] == "NOT_APPLICABLE"
    assert body["reviewer_name"] == "Jane Doe"

    detail = client.get(f"/scans/{scan_id}/findings/{finding_id}").json()
    assert detail["status"] == "NOT_APPLICABLE"
    assert len(detail["reviews"]) == 1
    assert detail["reviews"][0]["decision"] == "NOT_APPLICABLE"


def test_review_history_accumulates_and_orders_newest_first():
    client = TestClient(app)
    scan_id = _upload_and_wait(client, _sample_repo_zip(marker="review-history"), "r2.zip")
    finding_id = _first_finding_id(client, scan_id)

    first = client.post(
        f"/scans/{scan_id}/findings/{finding_id}/reviews",
        json={"decision": "REQUIRES_HUMAN_REVIEW", "notes": "Needs a second opinion from legal."},
    )
    second = client.post(
        f"/scans/{scan_id}/findings/{finding_id}/reviews",
        json={"decision": "VERIFIED", "notes": "Legal confirmed this is an accepted risk."},
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert second.json()["previous_status"] == "REQUIRES_HUMAN_REVIEW"

    detail = client.get(f"/scans/{scan_id}/findings/{finding_id}").json()
    reviews = detail["reviews"]
    assert len(reviews) == 2
    assert reviews[0]["decision"] == "VERIFIED"  # newest first
    assert reviews[1]["decision"] == "REQUIRES_HUMAN_REVIEW"


def test_review_requires_non_empty_notes():
    client = TestClient(app)
    scan_id = _upload_and_wait(client, _sample_repo_zip(marker="review-blank-notes"), "r3.zip")
    finding_id = _first_finding_id(client, scan_id)

    response = client.post(
        f"/scans/{scan_id}/findings/{finding_id}/reviews",
        json={"decision": "VERIFIED", "notes": "   "},
    )

    assert response.status_code == 422


def test_review_rejects_invalid_decision_value():
    client = TestClient(app)
    scan_id = _upload_and_wait(client, _sample_repo_zip(marker="review-bad-decision"), "r4.zip")
    finding_id = _first_finding_id(client, scan_id)

    response = client.post(
        f"/scans/{scan_id}/findings/{finding_id}/reviews",
        json={"decision": "MAYBE", "notes": "This is a substantive note."},
    )

    assert response.status_code == 422


def test_review_404s_for_wrong_scan_or_finding_id():
    client = TestClient(app)
    scan_id = _upload_and_wait(client, _sample_repo_zip(marker="review-404"), "r5.zip")
    bogus_finding_id = str(uuid.uuid4())

    response = client.post(
        f"/scans/{scan_id}/findings/{bogus_finding_id}/reviews",
        json={"decision": "VERIFIED", "notes": "This is a substantive note."},
    )
    assert response.status_code == 404

    finding_id = _first_finding_id(client, scan_id)
    bogus_scan_id = str(uuid.uuid4())
    response = client.post(
        f"/scans/{bogus_scan_id}/findings/{finding_id}/reviews",
        json={"decision": "VERIFIED", "notes": "This is a substantive note."},
    )
    assert response.status_code == 404


def test_review_sets_human_review_required_false_unless_re_escalated():
    client = TestClient(app)
    scan_id = _upload_and_wait(client, _sample_repo_zip(marker="review-flag"), "r6.zip")
    finding_id = _first_finding_id(client, scan_id)

    client.post(
        f"/scans/{scan_id}/findings/{finding_id}/reviews",
        json={"decision": "VERIFIED", "notes": "Manually confirmed this is not an issue."},
    )
    detail = client.get(f"/scans/{scan_id}/findings/{finding_id}").json()
    assert detail["human_review_required"] is False

    client.post(
        f"/scans/{scan_id}/findings/{finding_id}/reviews",
        json={
            "decision": "REQUIRES_HUMAN_REVIEW",
            "notes": "Actually, escalating to a second reviewer.",
        },
    )
    detail = client.get(f"/scans/{scan_id}/findings/{finding_id}").json()
    assert detail["human_review_required"] is True


def test_review_never_touches_evidence_rows():
    client = TestClient(app)
    scan_id = _upload_and_wait(client, _sample_repo_zip(marker="review-evidence"), "r7.zip")
    finding_id = _first_finding_id(client, scan_id)

    before = client.get(f"/scans/{scan_id}/findings/{finding_id}").json()["evidence"]

    client.post(
        f"/scans/{scan_id}/findings/{finding_id}/reviews",
        json={"decision": "VERIFIED", "notes": "Manually confirmed this is not an issue."},
    )

    after = client.get(f"/scans/{scan_id}/findings/{finding_id}").json()["evidence"]
    assert after == before
