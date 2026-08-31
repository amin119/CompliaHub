from app.models.scan import Evidence, Finding, RepositoryFile
from app.services import repo_discovery, scan_storage, storage
from app.services.repo_extraction import iter_zip_entries
from app.services.security_analysis.ast_utils import safe_parse
from app.services.security_analysis.base import RuleContext
from app.services.security_analysis.registry import ALL_RULES
from app.tasks.celery_app import celery_app
from app.tasks.scan_pipeline import scan_stage

# Files whose classified component_type is worth reading back for framework
# detection — anything else in the repo is irrelevant to "what frameworks
# does this project use" and isn't worth a second MinIO round-trip.
_FRAMEWORK_RELEVANT_TYPES = {"dependency_manifest", "infrastructure_as_code", "ci_cd_config"}


@celery_app.task(name="scanner.extract_repository")
def extract_and_classify_files_task(scan_id: str) -> str:
    """Stage 1: fetch the archive from MinIO, walk it, classify every
    non-ignored entry, and store non-ignored/non-binary content so later
    stages/phases can read it back.

    Returns `scan_id` unchanged so the chain can thread it into
    `detect_frameworks_task` the same way `parse_document_task` threads its
    parsed tree into `chunk_document_task` — Celery's `chain()` always
    passes a stage's return value as the next stage's first positional
    argument.
    """
    with scan_stage(scan_id, "extract_and_classify", "extracting") as (db, scan):
        # Idempotency: rerunning this stage (e.g. after `detect_frameworks`
        # failed and the chain is retried) must not double every row — same
        # clear-then-rebuild pattern `chunk_document_task` already uses.
        db.query(RepositoryFile).filter(RepositoryFile.scan_id == scan.id).delete(
            synchronize_session=False
        )

        client = storage.get_minio_client()
        archive_bytes = scan_storage.download_object(client, scan.archive_object_key)

        file_count = 0
        total_size_bytes = 0
        for relative_path, content in iter_zip_entries(archive_bytes):
            classification = repo_discovery.classify_file(relative_path, content[:64])
            if classification.is_ignored:
                continue

            file_count += 1
            total_size_bytes += len(content)

            content_stored = not classification.is_binary_heuristic
            object_key = None
            if content_stored:
                object_key = f"{scan.id}/files/{relative_path}"
                scan_storage.upload_object(
                    client, object_key, content, "application/octet-stream"
                )

            db.add(
                RepositoryFile(
                    scan_id=scan.id,
                    relative_path=relative_path,
                    language=classification.language,
                    component_type=classification.component_type,
                    size_bytes=len(content),
                    content_stored=content_stored,
                    minio_object_key=object_key,
                )
            )

        scan.file_count = file_count
        scan.total_size_bytes = total_size_bytes
        # Framework detection is the next stage in the chain — leave the
        # scan in an intermediate status rather than "ready" here.
        scan.status = "classifying"

    return scan_id


@celery_app.task(name="scanner.detect_frameworks")
def detect_frameworks_task(scan_id: str) -> str:
    """Stage 2: read back only the small set of manifest/config files
    already classified during stage 1, detect languages/frameworks from
    them, and mark the scan ready.

    Returns `scan_id` unchanged — this stage now has a successor
    (`run_security_analyzers_task`) in the chain, so it needs to thread
    `scan_id` forward the same way `extract_and_classify_files_task` does
    (the exact bug already hit once: a chained task that returns `None`
    while the next stage also receives an explicit `.s()` arg ends up
    called with two positional arguments).
    """
    with scan_stage(scan_id, "detect_frameworks", "detecting_frameworks") as (db, scan):
        client = storage.get_minio_client()

        relevant_files = (
            db.query(RepositoryFile)
            .filter(
                RepositoryFile.scan_id == scan.id,
                RepositoryFile.component_type.in_(_FRAMEWORK_RELEVANT_TYPES),
                RepositoryFile.content_stored.is_(True),
            )
            .all()
        )

        manifest_contents: dict[str, bytes] = {}
        for repository_file in relevant_files:
            manifest_contents[repository_file.relative_path] = scan_storage.download_object(
                client, repository_file.minio_object_key
            )

        languages = (
            db.query(RepositoryFile.language)
            .filter(
                RepositoryFile.scan_id == scan.id,
                RepositoryFile.language.is_not(None),
            )
            .distinct()
            .all()
        )

        scan.detected_languages = sorted({language for (language,) in languages})
        scan.detected_frameworks = repo_discovery.detect_frameworks(manifest_contents)
        scan.status = "ready"

    return scan_id


@celery_app.task(name="scanner.run_security_analyzers")
def run_security_analyzers_task(scan_id: str) -> str:
    """Stage 3: run every rule in the security-analysis registry against
    every stored, decodable file, recording a `Finding` + `Evidence` pair
    per hit. Tracked on `Scan.findings_status`, independent of `Scan.status`
    (see `scan_stage`'s docstring) — file browsing already works once
    stage 2 finishes; this stage can still be running, or fail, without
    affecting that.
    """
    with scan_stage(
        scan_id,
        "run_security_analyzers",
        "analyzing_security",
        status_field="findings_status",
        error_field="findings_error_message",
    ) as (db, scan):
        # Idempotency: rerunning this stage must not double every finding —
        # same clear-then-rebuild pattern used throughout this pipeline.
        # Evidence rows are cleared explicitly too: `Evidence.finding_id`
        # is `ondelete="SET NULL"` (deliberately, see the model's own
        # comment), so deleting a Finding alone would leave its Evidence
        # rows behind as orphans instead of removed.
        db.query(Evidence).filter(Evidence.scan_id == scan.id).delete(synchronize_session=False)
        db.query(Finding).filter(Finding.scan_id == scan.id).delete(synchronize_session=False)

        client = storage.get_minio_client()
        repository_files = (
            db.query(RepositoryFile)
            .filter(
                RepositoryFile.scan_id == scan.id,
                RepositoryFile.content_stored.is_(True),
            )
            .all()
        )

        for repository_file in repository_files:
            raw = scan_storage.download_object(client, repository_file.minio_object_key)
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                continue  # Not actually text despite passing the binary heuristic — skip.

            tree = safe_parse(text) if repository_file.language == "python" else None
            context = RuleContext(
                relative_path=repository_file.relative_path,
                language=repository_file.language,
                component_type=repository_file.component_type,
                text=text,
                tree=tree,
            )

            for rule in ALL_RULES:
                for hit in rule.detect(context):
                    finding = Finding(
                        scan_id=scan.id,
                        category=rule.category,
                        rule_id=rule.rule_id,
                        title=hit.title,
                        status=hit.status,
                        severity=hit.severity,
                        confidence=hit.confidence,
                        summary=hit.summary,
                        reasoning=hit.reasoning,
                        recommendation=hit.recommendation,
                        automated=True,
                        human_review_required=(
                            hit.status == "REQUIRES_HUMAN_REVIEW" or hit.severity == "CRITICAL"
                        ),
                    )
                    db.add(finding)
                    db.flush()  # assigns finding.id without ending the transaction

                    db.add(
                        Evidence(
                            scan_id=scan.id,
                            repository_file_id=repository_file.id,
                            finding_id=finding.id,
                            source_type=rule.evidence_source_type,
                            rule_id=rule.rule_id,
                            file_path=repository_file.relative_path,
                            line_start=hit.line_start,
                            line_end=hit.line_end,
                            snippet=hit.snippet,
                            description=hit.summary,
                            confidence=hit.confidence,
                        )
                    )

        scan.findings_status = "ready"

    return scan_id
