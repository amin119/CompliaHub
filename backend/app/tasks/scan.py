from app.models.scan import RepositoryFile
from app.services import repo_discovery, scan_storage, storage
from app.services.repo_extraction import iter_zip_entries
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
def detect_frameworks_task(scan_id: str) -> None:
    """Stage 2: read back only the small set of manifest/config files
    already classified during stage 1, detect languages/frameworks from
    them, and mark the scan ready.
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
