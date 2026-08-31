import uuid

from celery import chain
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.scan import Finding, RepositoryFile, Scan
from app.schemas.scan import (
    FindingDetailResponse,
    FindingResponse,
    RepositoryFileResponse,
    ScanResponse,
)
from app.services import scan_storage, storage
from app.services.hashing import sha256_bytes
from app.tasks.scan import (
    detect_frameworks_task,
    extract_and_classify_files_task,
    run_security_analyzers_task,
)

router = APIRouter(prefix="/scans", tags=["scans"])


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
