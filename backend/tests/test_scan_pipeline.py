import uuid

import pytest
from sqlalchemy import text

from app.core.db import SessionLocal, engine
from app.models.scan import Scan
from app.tasks.scan_pipeline import scan_stage


def _infra_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1 FROM scans LIMIT 1"))
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _infra_available(),
    reason="requires docker compose up (postgres) with migrations applied",
)


def _make_scan() -> Scan:
    db = SessionLocal()
    try:
        scan = Scan(
            original_filename="scan_pipeline_test.zip",
            sha256_hash=uuid.uuid4().hex,
            archive_object_key="test/scan_pipeline_test_key",
            status="pending",
        )
        db.add(scan)
        db.commit()
        db.refresh(scan)
        return scan
    finally:
        db.close()


def _reload(scan_id: uuid.UUID) -> Scan:
    db = SessionLocal()
    try:
        return db.get(Scan, scan_id)
    finally:
        db.close()


def test_scan_stage_marks_scan_status_and_commits_on_success():
    scan = _make_scan()

    with scan_stage(str(scan.id), "test_stage", "running_test") as (_db, stage_scan):
        assert stage_scan.status == "running_test"

    refreshed = _reload(scan.id)
    assert refreshed.status == "running_test"


def test_scan_stage_marks_scan_failed_on_exception():
    scan = _make_scan()

    with pytest.raises(ValueError, match="simulated failure"):
        with scan_stage(str(scan.id), "test_stage", "running_test") as (_db, _scan):
            raise ValueError("simulated failure")

    refreshed = _reload(scan.id)
    assert refreshed.status == "failed"
    assert refreshed.error_message == "simulated failure"


def test_scan_stage_raises_for_missing_scan():
    with pytest.raises(ValueError, match="not found"):
        with scan_stage(str(uuid.uuid4()), "test_stage", "running_test"):
            pass
