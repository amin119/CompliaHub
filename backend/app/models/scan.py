import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import DateTime

from app.core.db import Base


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Scan(Base):
    """One uploaded repository (currently: a zip archive) submitted for
    compliance-evidence scanning. Mirrors `Document`'s shape deliberately —
    same upload/hash-dedup/status-tracking idiom, applied to a repository
    instead of a single standards file.
    """

    __tablename__ = "scans"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    # Free-text label the user supplies, not a foreign key to a `Repository`
    # entity — there's no such entity yet. A persistent Repository (tracked
    # branch/URL, diffed across scans) only becomes meaningful once
    # git-connect ingestion exists, which is a later phase.
    repository_name: Mapped[str | None] = mapped_column(String, nullable=True)
    # "zip" is the only value Phase 1 produces; "git"/"local" are reserved
    # for later phases so this column doesn't need a migration to grow.
    source_type: Mapped[str] = mapped_column(String, nullable=False, default="zip")
    original_filename: Mapped[str] = mapped_column(String, nullable=False)
    sha256_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    archive_object_key: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    detected_languages: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    detected_frameworks: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    # Independent of `status` above: a scan's files are browsable (`status
    # == "ready"`) well before the heavier security-rule pass has finished,
    # exactly the same reasoning `Document.graph_status` uses to stay
    # independent of `Document.status` (see `tasks/pipeline.py`'s
    # docstring) — extraction/analysis is an explicit, separate stage.
    findings_status: Mapped[str] = mapped_column(String, nullable=False, default="not_started")
    findings_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )

    files: Mapped[list["RepositoryFile"]] = relationship(
        back_populates="scan", cascade="all, delete-orphan"
    )
    processing_jobs: Mapped[list["ScanProcessingJob"]] = relationship(
        back_populates="scan", cascade="all, delete-orphan"
    )
    evidence: Mapped[list["Evidence"]] = relationship(
        back_populates="scan", cascade="all, delete-orphan"
    )
    findings: Mapped[list["Finding"]] = relationship(
        back_populates="scan", cascade="all, delete-orphan"
    )


class RepositoryFile(Base):
    """One file discovered inside a scanned repository, after ignore-list
    filtering and classification. `content_stored` is false for files this
    project deliberately never uploads to MinIO at all (binaries, anything
    over the per-file size cap) — `minio_object_key` is only meaningful when
    it's true.
    """

    __tablename__ = "repository_files"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    scan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scans.id", ondelete="CASCADE"), nullable=False
    )
    relative_path: Mapped[str] = mapped_column(String, nullable=False)
    language: Mapped[str | None] = mapped_column(String, nullable=True)
    component_type: Mapped[str] = mapped_column(String, nullable=False, default="unknown")
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    content_stored: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    minio_object_key: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    scan: Mapped["Scan"] = relationship(back_populates="files")


class ScanProcessingJob(Base):
    """One pipeline stage's execution record for a scan (extract, classify,
    detect_frameworks, ...) — same role as `ProcessingJob` for `Document`.
    """

    __tablename__ = "scan_processing_jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    scan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scans.id", ondelete="CASCADE"), nullable=False
    )
    task_name: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    scan: Mapped["Scan"] = relationship(back_populates="processing_jobs")


class Evidence(Base):
    """Normalized evidence schema (compliance-scanner spec section 16).
    Nothing writes to this table yet — Phase 1 only defines the shape.
    Populated starting with Phase 2's deterministic security analyzer, and
    every finding from later phases must reference evidence rows here
    rather than asserting a conclusion with nothing to point at.
    """

    __tablename__ = "evidence"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    scan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scans.id", ondelete="CASCADE"), nullable=False
    )
    repository_file_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("repository_files.id", ondelete="SET NULL"),
        nullable=True,
    )
    # A plain one-to-many from Finding's side (nullable FK on the "many"
    # side, SET NULL on delete) — the same shape as `repository_file_id`
    # above, not a join table: nothing in this project's rules produces
    # one Evidence row shared across multiple distinct Findings, so a
    # many-to-many association table would be unused structure.
    finding_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("findings.id", ondelete="SET NULL"), nullable=True
    )
    # Which kind of analyzer produced this — e.g. "static_pattern",
    # "config_file", "manifest", "ast_analysis", "llm_reasoning". Populated
    # by later phases; Phase 1 defines the column, nothing writes it yet.
    source_type: Mapped[str | None] = mapped_column(String, nullable=True)
    rule_id: Mapped[str | None] = mapped_column(String, nullable=True)
    # Denormalized so a finding can display its evidence location without a
    # join, even if the originating file row is later deleted (SET NULL).
    file_path: Mapped[str | None] = mapped_column(String, nullable=True)
    line_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    line_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # An excerpt only — never a whole-file dump, per the spec's data-
    # minimization principle for evidence storage.
    snippet: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    # "high" | "medium" | "low" — deliberately not a numeric score here;
    # never a binary pass/fail, per the spec's evidence-based principle.
    confidence: Mapped[str | None] = mapped_column(String, nullable=True)
    evidence_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    scan: Mapped["Scan"] = relationship(back_populates="evidence")
    finding: Mapped["Finding | None"] = relationship(back_populates="evidence")


class Finding(Base):
    """One security/compliance finding produced by a rule (Phase 2:
    deterministic security rules only — GDPR/ISO clause mapping and any
    LLM-based reasoning are later phases). Never a binary pass/fail:
    `status` is the compliance-scanner spec's own 6-value vocabulary
    (VERIFIED/PARTIALLY_VERIFIED/NOT_VERIFIED/POTENTIAL_NON_COMPLIANCE/
    NOT_APPLICABLE/REQUIRES_HUMAN_REVIEW) — Phase 2 rules only ever write
    POTENTIAL_NON_COMPLIANCE or REQUIRES_HUMAN_REVIEW, since the other
    four values only become meaningful once a real compliance clause
    exists to verify against (later phases) or a human/LLM has acted on
    the finding.
    """

    __tablename__ = "findings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    scan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scans.id", ondelete="CASCADE"), nullable=False
    )
    # Stays NULL throughout Phase 2 — these are framework-agnostic security
    # findings; mapping to a specific ISO/GDPR clause starts in a later
    # phase, once that compliance-knowledge layer exists.
    framework: Mapped[str | None] = mapped_column(String, nullable=True)
    category: Mapped[str] = mapped_column(String, nullable=False)
    rule_id: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    severity: Mapped[str] = mapped_column(String, nullable=False)
    confidence: Mapped[str] = mapped_column(String, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    reasoning: Mapped[str] = mapped_column(Text, nullable=False)
    # A static, per-rule one-liner — not generated remediation (that's a
    # later phase's `RemediationAgent`).
    recommendation: Mapped[str | None] = mapped_column(Text, nullable=True)
    automated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    human_review_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    scan: Mapped["Scan"] = relationship(back_populates="findings")
    evidence: Mapped[list["Evidence"]] = relationship(back_populates="finding")
