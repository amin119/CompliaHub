"""Live integration tests for Phase 3's GDPR pipeline stage — the one
thing the unit tests in `test_privacy_rules_*.py` can't cover: the full
4-stage chain running through the real API, and — most importantly — the
bidirectional delete-scoping fix that lets security (Phase 2) and GDPR
(Phase 3) findings coexist in the same `Finding` table without one rule
pass's rerun wiping the other's rows.
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
    """A repo with content relevant to *both* frameworks: Phase 2's
    security rules (AWS key, MD5-in-hash_password, logger.email, unpinned
    dependency) and Phase 3's GDPR rules (a SQLAlchemy-shaped model with
    `email`/`ssn` fields, a third-party import, a `set_cookie` call). No
    privacy-policy doc, no delete route — so the repo-level "gap" findings
    are expected too.
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
            "import cohere\n"
            "\n"
            "class User(Base):\n"
            "    email = mapped_column(String)\n"
            "    ssn = mapped_column(String)\n"
            "\n"
            "def set_session_cookie(response):\n"
            "    response.set_cookie('session_id', 'abc')\n",
        )
        archive.writestr("requirements.txt", "fastapi>=0.100.0\nrequests\n")
        if marker:
            archive.writestr("MARKER.txt", marker)
    return buf.getvalue()


def _upload_and_wait(client: TestClient, data: bytes, filename: str) -> str:
    response = client.post("/scans", files={"file": (filename, data, "application/zip")})
    scan_id = response.json()["id"]
    status_response = client.get(f"/scans/{scan_id}").json()
    # Celery's eager mode runs the whole chain synchronously, so by the
    # time the upload response comes back, all four stages have already
    # completed — including the new privacy stage.
    assert status_response["findings_status"] == "ready"
    assert status_response["privacy_status"] == "ready"
    return scan_id


def test_gdpr_findings_generated_alongside_security_findings():
    client = TestClient(app)
    scan_id = _upload_and_wait(client, _sample_repo_zip(), "combined-repo.zip")

    all_findings = client.get(f"/scans/{scan_id}/findings").json()
    frameworks = {f["framework"] for f in all_findings}
    assert None in frameworks  # Phase 2's security findings, unchanged
    assert "GDPR" in frameworks

    gdpr_findings = client.get(f"/scans/{scan_id}/findings?framework=GDPR").json()
    gdpr_categories = {f["category"] for f in gdpr_findings}
    assert "data_minimisation" in gdpr_categories  # email field
    assert "special_category_data" in gdpr_categories  # ssn field
    assert "third_party_processors" in gdpr_categories  # cohere import
    assert "consent_mechanisms" in gdpr_categories  # set_cookie call
    assert "security_of_processing" in gdpr_categories  # logger(user.email), GDPR-framed
    # The six always-on organizational findings + the deletion-route
    # absence finding (no privacy doc, no delete route in this repo).
    assert "lawful_basis" in gdpr_categories
    assert "dpia" in gdpr_categories
    assert "data_subject_rights" in gdpr_categories

    # Phase 2's security findings are unaffected by Phase 3 existing —
    # still present, still framework=None.
    security_findings = [f for f in all_findings if f["framework"] is None]
    security_categories = {f["category"] for f in security_findings}
    assert "secrets" in security_categories
    assert "cryptography" in security_categories
    assert "dependencies" in security_categories


def test_logging_email_produces_two_distinct_findings_same_line():
    client = TestClient(app)
    scan_id = _upload_and_wait(client, _sample_repo_zip(marker="logging-check"), "logging.zip")

    all_findings = client.get(f"/scans/{scan_id}/findings").json()
    email_log_findings = [
        f for f in all_findings if "email" in f["summary"].lower() and "log" in f["rule_id"].lower()
    ]
    # Phase 2's SEC-LOG-SENSITIVE-PY (framework=None) and Phase 3's
    # GDPR-LOG-PII-PY (framework="GDPR") both fire on the same line — two
    # rows, not a silent duplicate or a dropped one.
    assert len(email_log_findings) == 2
    assert {f["framework"] for f in email_log_findings} == {None, "GDPR"}


def test_rerunning_privacy_analyzers_does_not_wipe_security_findings():
    """The critical regression this whole delete-scoping fix exists for:
    a rerun of the GDPR pass must never touch Phase 2's rows.
    """
    from app.tasks.scan import run_privacy_analyzers_task

    client = TestClient(app)
    scan_id = _upload_and_wait(client, _sample_repo_zip(marker="privacy-rerun"), "rerun-a.zip")

    security_before = [
        f for f in client.get(f"/scans/{scan_id}/findings").json() if f["framework"] is None
    ]
    gdpr_before = [
        f for f in client.get(f"/scans/{scan_id}/findings").json() if f["framework"] == "GDPR"
    ]
    assert len(security_before) > 0
    assert len(gdpr_before) > 0

    run_privacy_analyzers_task(scan_id)

    all_after = client.get(f"/scans/{scan_id}/findings").json()
    security_after = [f for f in all_after if f["framework"] is None]
    gdpr_after = [f for f in all_after if f["framework"] == "GDPR"]

    assert len(security_after) == len(security_before)
    assert len(gdpr_after) == len(gdpr_before)  # rebuilt, not doubled


def test_rerunning_security_analyzers_does_not_wipe_gdpr_findings():
    """The symmetric half: a rerun of Phase 2's own task must never touch
    Phase 3's GDPR rows either.
    """
    from app.tasks.scan import run_security_analyzers_task

    client = TestClient(app)
    scan_id = _upload_and_wait(client, _sample_repo_zip(marker="security-rerun"), "rerun-b.zip")

    security_before = [
        f for f in client.get(f"/scans/{scan_id}/findings").json() if f["framework"] is None
    ]
    gdpr_before = [
        f for f in client.get(f"/scans/{scan_id}/findings").json() if f["framework"] == "GDPR"
    ]
    assert len(security_before) > 0
    assert len(gdpr_before) > 0

    run_security_analyzers_task(scan_id)

    all_after = client.get(f"/scans/{scan_id}/findings").json()
    security_after = [f for f in all_after if f["framework"] is None]
    gdpr_after = [f for f in all_after if f["framework"] == "GDPR"]

    assert len(security_after) == len(security_before)  # rebuilt, not doubled
    assert len(gdpr_after) == len(gdpr_before)  # completely untouched
