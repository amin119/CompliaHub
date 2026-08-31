import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

from app.core.db import SessionLocal
from app.models.scan import Scan, ScanProcessingJob


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _fail(
    db,
    scan: Scan,
    job: ScanProcessingJob,
    error: Exception,
    status_field: str = "status",
    error_field: str = "error_message",
) -> None:
    """Same failure boundary as `tasks/pipeline.py`'s `_fail`, applied to a
    Scan instead of a Document: roll back first (the triggering error may
    have come from a failed flush, leaving the transaction unusable for
    anything else), then record the failure on both the job and the scan
    so the API/UI can show why a scan is stuck.

    `status_field`/`error_field` let Phase 2's security-analysis stage
    write to `findings_status`/`findings_error_message` instead of the
    file-classification pipeline's own `status` — same independent-status-
    track rationale `pipeline_stage` already uses for
    `Document.graph_status`.
    """
    db.rollback()
    job.status = "failed"
    job.error_message = str(error)
    job.finished_at = _now()
    setattr(scan, status_field, "failed")
    setattr(scan, error_field, str(error))
    db.commit()


@contextmanager
def scan_stage(
    scan_id: str,
    task_name: str,
    in_progress_status: str,
    status_field: str = "status",
    error_field: str = "error_message",
):
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

    `status_field`/`error_field` default to the file-classification
    pipeline's own `status`/`error_message` columns (Phase 1's behavior,
    unchanged). Phase 2's `run_security_analyzers_task` passes
    `status_field="findings_status"`, `error_field="findings_error_message"`
    instead — a separate, independent status track, since a scan's files
    are browsable long before the heavier security-rule pass has finished
    (exactly the same reasoning `pipeline_stage` documents for
    `Document.graph_status` being independent of `Document.status`).

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
        setattr(scan, status_field, in_progress_status)
        db.commit()

        try:
            yield db, scan
        except Exception as exc:
            _fail(db, scan, job, exc, status_field=status_field, error_field=error_field)
            raise

        job.status = "success"
        job.finished_at = _now()
        db.commit()
    finally:
        db.close()
