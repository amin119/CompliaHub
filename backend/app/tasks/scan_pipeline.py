import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

from app.core.db import SessionLocal
from app.models.scan import Scan, ScanProcessingJob


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _fail(db, scan: Scan, job: ScanProcessingJob, error: Exception) -> None:
    """Same failure boundary as `tasks/pipeline.py`'s `_fail`, applied to a
    Scan instead of a Document: roll back first (the triggering error may
    have come from a failed flush, leaving the transaction unusable for
    anything else), then record the failure on both the job and the scan
    so the API/UI can show why a scan is stuck.
    """
    db.rollback()
    job.status = "failed"
    job.error_message = str(error)
    job.finished_at = _now()
    scan.status = "failed"
    scan.error_message = str(error)
    db.commit()


@contextmanager
def scan_stage(scan_id: str, task_name: str, in_progress_status: str):
    """A new sibling to `tasks/pipeline.py`'s `pipeline_stage`, not a
    generalization of it: same open-session/load-row/create-job/
    commit-or-fail shape, operating on `Scan`/`ScanProcessingJob` instead of
    `Document`/`ProcessingJob`. This project already treats structurally-
    identical-but-distinct concerns this way elsewhere (see
    `query_classifier.py`'s comment on why its adapter isn't code-shared
    with `extraction.py`'s despite an identical shape) — generalizing
    `pipeline_stage` over model/job classes would be an invasive rewrite of
    a function `test_pipeline_stage.py` already asserts specific behavior
    against, for a benefit that only this one new pipeline needs.

    Yields `(db, scan)`.
    """
    db = SessionLocal()
    try:
        scan = db.get(Scan, uuid.UUID(scan_id))
        if scan is None:
            raise ValueError(f"scan {scan_id} not found")

        job = ScanProcessingJob(
            scan_id=scan.id, task_name=task_name, status="running", started_at=_now()
        )
        db.add(job)
        scan.status = in_progress_status
        db.commit()

        try:
            yield db, scan
        except Exception as exc:
            _fail(db, scan, job, exc)
            raise

        job.status = "success"
        job.finished_at = _now()
        db.commit()
    finally:
        db.close()
