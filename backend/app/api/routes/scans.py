import uuid

from celery import chain
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.models.scan import Finding, RepositoryFile, Scan
from app.schemas.scan import (
    BulkValidationRequest,
    BulkValidationResult,
    EvidenceResponse,
    FindingDetailResponse,
    FindingResponse,
    RepositoryFileResponse,
    ScanResponse,
)
from app.services import compliance_retrieval, finding_validation, scan_storage, storage
from app.services.hashing import sha256_bytes
from app.tasks.scan import (
    detect_frameworks_task,
    extract_and_classify_files_task,
    run_ai_analyzers_task,
    run_iso27001_analyzers_task,
    run_privacy_analyzers_task,
    run_security_analyzers_task,
)

router = APIRouter(prefix="/scans", tags=["scans"])

# Phase 6: a bulk validate call runs sequentially (never parallel, to stay
# under Voyage's tight per-account rate limit), so this cap keeps even the
# worst case in the tens-of-seconds range rather than needing a Celery task
# the way the scanner's multi-minute per-file passes do.
_MAX_BULK_FINDINGS = 10


@router.post("", response_model=ScanResponse, status_code=201)
def upload_scan(file: UploadFile = File(...), db: Session = Depends(get_db)):
    data = file.file.read()
    if not data:
        raise HTTPException(status_code=400, detail="uploaded file is empty")

    file_hash = sha256_bytes(data)

    # Idempotency: the same archive bytes always hash the same way, so a
    # re-upload returns the existing scan untouched — same rationale as
    # `upload_document`.
    existing = db.scalar(select(Scan).where(Scan.sha256_hash == file_hash))
    if existing is not None:
        return existing

    object_key = f"{file_hash}/{file.filename}"
    client = storage.get_minio_client()
    scan_storage.upload_object(
        client, object_key, data, file.content_type or "application/zip"
    )

    scan = Scan(
        original_filename=file.filename,
        sha256_hash=file_hash,
        archive_object_key=object_key,
        status="pending",
    )
    db.add(scan)
    db.commit()
    db.refresh(scan)

    # `detect_frameworks_task` takes its `scan_id` from the chain (Celery
    # feeds a stage's return value as the next stage's first positional
    # arg — `extract_and_classify_files_task` returns `scan_id` unchanged
    # for exactly this), not from an explicit `.s()` argument here — the
    # same threading pattern `parse_document_task`/`chunk_document_task`
    # already use for the ingestion chain.
    chain(
        extract_and_classify_files_task.s(str(scan.id)),
        detect_frameworks_task.s(),
        run_security_analyzers_task.s(),
        run_privacy_analyzers_task.s(),
        run_ai_analyzers_task.s(),
        run_iso27001_analyzers_task.s(),
    ).apply_async()

    return scan


@router.get("", response_model=list[ScanResponse])
def list_scans(db: Session = Depends(get_db)):
    return db.scalars(select(Scan).order_by(Scan.created_at.desc())).all()


@router.get("/{scan_id}", response_model=ScanResponse)
def get_scan(scan_id: uuid.UUID, db: Session = Depends(get_db)):
    scan = db.get(Scan, scan_id)
    if scan is None:
        raise HTTPException(status_code=404, detail="scan not found")
    return scan


@router.get("/{scan_id}/files", response_model=list[RepositoryFileResponse])
def get_scan_files(
    scan_id: uuid.UUID,
    component_type: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    if db.get(Scan, scan_id) is None:
        raise HTTPException(status_code=404, detail="scan not found")

    query = select(RepositoryFile).where(RepositoryFile.scan_id == scan_id)
    if component_type is not None:
        query = query.where(RepositoryFile.component_type == component_type)
    query = query.order_by(RepositoryFile.relative_path)

    return db.scalars(query).all()


@router.get("/{scan_id}/findings", response_model=list[FindingResponse])
def get_scan_findings(
    scan_id: uuid.UUID,
    severity: str | None = Query(default=None),
    status: str | None = Query(default=None),
    category: str | None = Query(default=None),
    framework: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    if db.get(Scan, scan_id) is None:
        raise HTTPException(status_code=404, detail="scan not found")

    query = select(Finding).where(Finding.scan_id == scan_id)
    if severity is not None:
        query = query.where(Finding.severity == severity)
    if status is not None:
        query = query.where(Finding.status == status)
    if category is not None:
        query = query.where(Finding.category == category)
    if framework is not None:
        query = query.where(Finding.framework == framework)
    query = query.order_by(Finding.created_at.desc())

    return db.scalars(query).all()


@router.get("/{scan_id}/findings/{finding_id}", response_model=FindingDetailResponse)
def get_scan_finding(scan_id: uuid.UUID, finding_id: uuid.UUID, db: Session = Depends(get_db)):
    finding = db.scalar(
        select(Finding).where(Finding.id == finding_id, Finding.scan_id == scan_id)
    )
    if finding is None:
        raise HTTPException(status_code=404, detail="finding not found")
    return finding


def _validate_one_finding(db: Session, scan_id: uuid.UUID, finding_id: uuid.UUID):
    """Shared by the single and bulk validate endpoints: retrieve
    grounding context, call the validation LLM, persist the verdict as a
    new Evidence row. Synchronous, in-request — like `/query`, a single
    retrieval+LLM round trip is seconds, not the multi-minute per-file
    passes the scanner's own Celery chain exists for, so no queueing is
    needed here.
    """
    finding = db.scalar(
        select(Finding).where(Finding.id == finding_id, Finding.scan_id == scan_id)
    )
    if finding is None:
        raise HTTPException(status_code=404, detail="finding not found")

    try:
        context = compliance_retrieval.retrieve_context_for_finding(db, finding)
    except compliance_retrieval.NoStandardsContextError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    try:
        verdict = finding_validation.validate_finding(finding, context.chunks)
    except (finding_validation.ValidationRateLimited, ValidationError) as exc:
        raise HTTPException(
            status_code=503, detail="AI validation is temporarily unavailable, try again shortly."
        ) from exc

    settings = get_settings()
    return finding_validation.persist_verdict(
        db, finding, verdict, context, model=settings.gemini_validation_model, top_k=5
    )


@router.post("/{scan_id}/findings/{finding_id}/validate", response_model=EvidenceResponse)
def validate_finding_endpoint(
    scan_id: uuid.UUID, finding_id: uuid.UUID, db: Session = Depends(get_db)
):
    return _validate_one_finding(db, scan_id, finding_id)


@router.post("/{scan_id}/findings/validate-bulk", response_model=list[BulkValidationResult])
def validate_findings_bulk(
    scan_id: uuid.UUID, request: BulkValidationRequest, db: Session = Depends(get_db)
):
    if len(request.finding_ids) > _MAX_BULK_FINDINGS:
        raise HTTPException(
            status_code=400,
            detail=f"at most {_MAX_BULK_FINDINGS} findings per bulk validation call",
        )

    results: list[BulkValidationResult] = []
    for finding_id in request.finding_ids:
        try:
            evidence = _validate_one_finding(db, scan_id, finding_id)
        except HTTPException as exc:
            # A single item's failure (not found / no standards context /
            # LLM unavailable) must never abort the rest of the batch.
            results.append(
                BulkValidationResult(
                    finding_id=finding_id, ok=False, evidence=None, error=str(exc.detail)
                )
            )
            continue
        results.append(
            BulkValidationResult(finding_id=finding_id, ok=True, evidence=evidence, error=None)
        )
    return results
