from app.models.scan import Evidence, Finding, RepositoryFile
from app.services import repo_discovery, scan_storage, storage
from app.services.ai_analysis import ai_imports
from app.services.ai_analysis import repo_level_checks as ai_repo_level_checks
from app.services.ai_analysis.registry import AI_RULES
from app.services.iso27001.catalog import CATALOG
from app.services.iso27001.mapping import CONTROL_TO_CATEGORIES, decide_control_status
from app.services.privacy_analysis import repo_level_checks
from app.services.privacy_analysis.registry import PRIVACY_RULES
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
        #
        # SCOPED BY FRAMEWORK (fixed in Phase 3): this clear must only touch
        # this framework's own rows. Before Phase 3 this deleted every
        # Finding for the scan regardless of framework; once Phase 3 writes
        # GDPR findings to the same table, an unscoped rerun of *this* task
        # would silently wipe every GDPR finding. Phase 2's rows are exactly
        # those with `framework IS NULL`.
        #
        # Evidence rows are cleared explicitly too, scoped via a
        # `finding_id IN (subquery over this framework's findings)` filter
        # rather than a bare `Evidence.scan_id` match — otherwise this would
        # also delete the GDPR findings' evidence. `Evidence.finding_id` is
        # `ondelete="SET NULL"` (deliberately, see the model's own comment),
        # so deleting a Finding alone would leave its Evidence rows behind as
        # orphans instead of removed.
        security_finding_ids = (
            db.query(Finding.id)
            .filter(Finding.scan_id == scan.id, Finding.framework.is_(None))
            .scalar_subquery()
        )
        db.query(Evidence).filter(
            Evidence.scan_id == scan.id,
            Evidence.finding_id.in_(security_finding_ids),
        ).delete(synchronize_session=False)
        db.query(Finding).filter(
            Finding.scan_id == scan.id, Finding.framework.is_(None)
        ).delete(synchronize_session=False)

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
                        # `hit.category` overrides `rule.category` when a
                        # rule's hits vary by category at runtime — see
                        # `RuleHit.category`'s docstring.
                        category=hit.category or rule.category,
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
                            evidence_metadata=hit.evidence_metadata,
                        )
                    )

        scan.findings_status = "ready"

    return scan_id


@celery_app.task(name="scanner.run_privacy_analyzers")
def run_privacy_analyzers_task(scan_id: str) -> str:
    """Stage 4: run every rule in the privacy-analysis (GDPR) registry
    against every stored, decodable file, plus the repo-level aggregate
    checks, recording `Finding` (`framework="GDPR"`) + `Evidence` pairs.

    Tracked on `Scan.privacy_status`/`Scan.privacy_error_message` — a third
    independent status track, distinct from `findings_status`. This is a
    genuinely separate failure domain: the two rule passes have *different*
    idempotent-clear scopes (see below), and getting either wrong is a real
    data-loss bug.
    """
    with scan_stage(
        scan_id,
        "run_privacy_analyzers",
        "analyzing_privacy",
        status_field="privacy_status",
        error_field="privacy_error_message",
    ) as (db, scan):
        # Idempotency, SCOPED BY FRAMEWORK (the symmetric half of Phase 2's
        # fix): this clear must only touch this framework's own rows —
        # `Finding.framework == "GDPR"` — so a rerun of *this* task never
        # wipes Phase 2's security findings (`framework IS NULL`). Evidence
        # is cleared via a `finding_id IN (subquery over GDPR findings)`
        # filter rather than a bare `Evidence.scan_id` match or a join-delete,
        # for the same orphan-avoidance reason Phase 2's clear documents.
        gdpr_finding_ids = (
            db.query(Finding.id)
            .filter(Finding.scan_id == scan.id, Finding.framework == "GDPR")
            .scalar_subquery()
        )
        db.query(Evidence).filter(
            Evidence.scan_id == scan.id,
            Evidence.finding_id.in_(gdpr_finding_ids),
        ).delete(synchronize_session=False)
        db.query(Finding).filter(
            Finding.scan_id == scan.id, Finding.framework == "GDPR"
        ).delete(synchronize_session=False)

        client = storage.get_minio_client()
        repository_files = (
            db.query(RepositoryFile)
            .filter(
                RepositoryFile.scan_id == scan.id,
                RepositoryFile.content_stored.is_(True),
            )
            .all()
        )

        # Accumulated across the whole file loop — a repo-level aggregate
        # fact, not a per-file one (see repo_level_checks' module docstring).
        found_deletion_route = False

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

            if not found_deletion_route:
                found_deletion_route = repo_level_checks.weak_positive_deletion_signal(context)

            for rule in PRIVACY_RULES:
                for hit in rule.detect(context):
                    _write_finding(
                        db,
                        scan,
                        # `hit.category` overrides `rule.category` when a
                        # rule's hits vary by category at runtime (e.g.
                        # `pii_fields`'s data_minimisation vs.
                        # special_category_data) — see `RuleHit.category`.
                        hit.category or rule.category,
                        rule.rule_id,
                        hit,
                        framework="GDPR",
                        evidence_source_type=rule.evidence_source_type,
                        repository_file=repository_file,
                    )

        # Repo-level fixed + absence-only findings — always emitted once per
        # scan, called directly (not registered in PRIVACY_RULES). These
        # have no per-file evidence, so no Evidence row is attached. Each
        # comes back paired with its own category (not re-derived from the
        # hit's title text — see `build_repo_level_findings`'s docstring).
        privacy_doc_present = repo_level_checks.privacy_policy_doc_present(repository_files)
        for category, hit in repo_level_checks.build_repo_level_findings(
            found_deletion_route, privacy_doc_present
        ):
            _write_finding(
                db,
                scan,
                category,
                "GDPR-REPO-LEVEL",
                hit,
                framework="GDPR",
                evidence_source_type="repo_aggregate",
                repository_file=None,
            )

        scan.privacy_status = "ready"

    return scan_id


@celery_app.task(name="scanner.run_ai_analyzers")
def run_ai_analyzers_task(scan_id: str) -> str:
    """Stage 5: run every rule in the AI-analysis (ISO 42001) registry
    against every stored, decodable file, plus the repo-level aggregate
    inventory/governance checks, recording `Finding` (`framework=
    "ISO42001"`) + `Evidence` pairs.

    Tracked on `Scan.ai_status`/`Scan.ai_error_message` — a fourth
    independent status track. Its idempotent-clear scope
    (`Finding.framework == "ISO42001"`) differs from both Phase 2's
    (`framework IS NULL`) and Phase 3's (`framework == "GDPR"`), the same
    "genuinely separate failure domain" reasoning that justified
    `privacy_status` as its own track rather than sharing `findings_status`.
    """
    with scan_stage(
        scan_id,
        "run_ai_analyzers",
        "analyzing_ai",
        status_field="ai_status",
        error_field="ai_error_message",
    ) as (db, scan):
        # Idempotency, SCOPED BY FRAMEWORK (same pattern as Phase 3's fix):
        # this clear must only touch `framework == "ISO42001"` rows, so a
        # rerun of *this* task never wipes Phase 2's or Phase 3's findings,
        # and vice versa.
        ai_finding_ids = (
            db.query(Finding.id)
            .filter(Finding.scan_id == scan.id, Finding.framework == "ISO42001")
            .scalar_subquery()
        )
        db.query(Evidence).filter(
            Evidence.scan_id == scan.id,
            Evidence.finding_id.in_(ai_finding_ids),
        ).delete(synchronize_session=False)
        db.query(Finding).filter(
            Finding.scan_id == scan.id, Finding.framework == "ISO42001"
        ).delete(synchronize_session=False)

        client = storage.get_minio_client()
        repository_files = (
            db.query(RepositoryFile)
            .filter(
                RepositoryFile.scan_id == scan.id,
                RepositoryFile.content_stored.is_(True),
            )
            .all()
        )

        # Accumulated across the whole file loop: which AI_RULES categories
        # fired at least once anywhere (the per-file rules' own results
        # *are* the signal — no separate detection pass needed), and which
        # distinct LLM/embedding-provider labels were imported anywhere
        # (for the inventory's "models" list). See
        # `repo_level_checks.build_ai_repo_level_findings`'s docstring for
        # why the signal-type threshold exists at all.
        signal_categories: set[str] = set()
        ai_provider_labels: set[str] = set()

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

            for _name, label, kind, _line in ai_imports.detect_ai_imports(context):
                if kind == "llm_provider":
                    ai_provider_labels.add(label)

            for rule in AI_RULES:
                hits = rule.detect(context)
                if hits:
                    signal_categories.add(rule.category)
                for hit in hits:
                    _write_finding(
                        db,
                        scan,
                        hit.category or rule.category,
                        rule.rule_id,
                        hit,
                        framework="ISO42001",
                        evidence_source_type=rule.evidence_source_type,
                        repository_file=repository_file,
                    )

        # Repo-level inventory + governance findings — only emitted when
        # at least two independent signal types were seen anywhere in the
        # scan (see the module docstring: a single AI import must not turn
        # a plain CRUD repo into nine "AI governance missing" findings).
        model_card_present = ai_repo_level_checks.model_card_doc_present(repository_files)
        for category, hit in ai_repo_level_checks.build_ai_repo_level_findings(
            signal_categories, ai_provider_labels, model_card_present
        ):
            _write_finding(
                db,
                scan,
                category,
                "AI-REPO-LEVEL",
                hit,
                framework="ISO42001",
                evidence_source_type="repo_aggregate",
                repository_file=None,
            )

        scan.ai_status = "ready"

    return scan_id


@celery_app.task(name="scanner.run_iso27001_analyzers")
def run_iso27001_analyzers_task(scan_id: str) -> str:
    """Stage 6: map every existing Finding (Phases 2-4) onto ISO/IEC
    27001:2022 Annex A controls via the hand-authored category mapping,
    writing one Finding (`framework="ISO27001"`) per catalogued control.

    Tracked on `Scan.iso27001_status`/`Scan.iso27001_error_message` — a
    fifth independent status track, same "genuinely separate failure
    domain" reasoning as every prior phase (its idempotent-clear scope,
    `Finding.framework == "ISO27001"`, is distinct from all four prior
    scopes).

    Unlike every prior stage, this one reads no repository files at all —
    only Finding rows Phases 2-4 already wrote. And unlike every prior
    stage's Finding:Evidence being roughly 1:1, one ISO27001 Finding here
    aggregates potentially many mapped findings' worth of evidence.
    `Evidence.finding_id` is a single nullable FK, so those rows are
    *copied* (new Evidence rows, `source_type="control_mapping"`), not
    re-pointed — forced, not stylistic: every prior task clear-then-
    rebuilds its own findings with new UUIDs on every rerun, so
    referencing the original rows by FK would let a routine upstream
    rerun silently orphan this stage's evidence via the existing
    `ondelete="SET NULL"`. A control with zero mapped findings still gets
    one synthetic `repo_aggregate` Evidence row, matching the repo-level-
    finding pattern Phase 3/4 already use.
    """
    with scan_stage(
        scan_id,
        "run_iso27001_analyzers",
        "mapping_iso27001",
        status_field="iso27001_status",
        error_field="iso27001_error_message",
    ) as (db, scan):
        # Idempotency, SCOPED BY FRAMEWORK (same pattern as every prior
        # phase): this clear must only touch `framework == "ISO27001"` rows.
        iso27001_finding_ids = (
            db.query(Finding.id)
            .filter(Finding.scan_id == scan.id, Finding.framework == "ISO27001")
            .scalar_subquery()
        )
        db.query(Evidence).filter(
            Evidence.scan_id == scan.id,
            Evidence.finding_id.in_(iso27001_finding_ids),
        ).delete(synchronize_session=False)
        db.query(Finding).filter(
            Finding.scan_id == scan.id, Finding.framework == "ISO27001"
        ).delete(synchronize_session=False)

        for control in CATALOG:
            category_pairs = CONTROL_TO_CATEGORIES.get(control.control_id, [])

            mapped_findings: dict[str, Finding] = {}
            for framework, category in category_pairs:
                query = db.query(Finding).filter(
                    Finding.scan_id == scan.id, Finding.category == category
                )
                query = (
                    query.filter(Finding.framework.is_(None))
                    if framework is None
                    else query.filter(Finding.framework == framework)
                )
                for source_finding in query.all():
                    mapped_findings[str(source_finding.id)] = source_finding

            assessment = decide_control_status(control.automatable, list(mapped_findings.values()))

            finding = Finding(
                scan_id=scan.id,
                framework="ISO27001",
                category=control.theme.lower(),
                rule_id=control.control_id,
                title=f"{control.control_id} {control.title}",
                status=assessment.status,
                severity=assessment.severity,
                confidence="medium" if mapped_findings else "low",
                summary=f"{control.title}. {assessment.reasoning} {control.source_note}",
                reasoning=assessment.reasoning,
                recommendation=(
                    "Review the mapped findings below and confirm this control's status "
                    "with a qualified assessor."
                    if mapped_findings
                    else "Confirm this control's status directly; no related findings were "
                    "detected by earlier scan stages."
                ),
                automated=control.automatable,
                human_review_required=(
                    assessment.status == "REQUIRES_HUMAN_REVIEW"
                    or assessment.severity == "CRITICAL"
                ),
            )
            db.add(finding)
            db.flush()  # assigns finding.id without ending the transaction

            if mapped_findings:
                for source_finding in mapped_findings.values():
                    source_evidence_rows = (
                        db.query(Evidence)
                        .filter(Evidence.finding_id == source_finding.id)
                        .all()
                    )
                    for source_evidence in source_evidence_rows:
                        db.add(
                            Evidence(
                                scan_id=scan.id,
                                repository_file_id=source_evidence.repository_file_id,
                                finding_id=finding.id,
                                source_type="control_mapping",
                                rule_id=source_evidence.rule_id,
                                file_path=source_evidence.file_path,
                                line_start=source_evidence.line_start,
                                line_end=source_evidence.line_end,
                                snippet=source_evidence.snippet,
                                description=source_evidence.description,
                                confidence=source_evidence.confidence,
                                evidence_metadata={
                                    "source_finding_id": str(source_finding.id),
                                    "source_framework": source_finding.framework,
                                    "source_category": source_finding.category,
                                    "catalog_source_note": control.source_note,
                                },
                            )
                        )
            else:
                db.add(
                    Evidence(
                        scan_id=scan.id,
                        repository_file_id=None,
                        finding_id=finding.id,
                        source_type="repo_aggregate",
                        rule_id=control.control_id,
                        file_path=None,
                        line_start=None,
                        line_end=None,
                        snippet=None,
                        description=(
                            f"No findings from earlier scan stages were mapped to "
                            f"{control.control_id}."
                        ),
                        confidence="low",
                        evidence_metadata={"catalog_source_note": control.source_note},
                    )
                )

        scan.iso27001_status = "ready"

    return scan_id


def _write_finding(
    db,
    scan,
    category: str,
    rule_id: str,
    hit,
    *,
    framework: str | None,
    evidence_source_type: str,
    repository_file,
) -> None:
    """Shared Finding+Evidence writer. Factored out so the privacy task's
    per-file rule loop and its repo-level loop write rows identically; the
    Phase 2 task keeps its own inline version unchanged to avoid churning
    already-shipped, verified code.
    """
    finding = Finding(
        scan_id=scan.id,
        framework=framework,
        category=category,
        rule_id=rule_id,
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
            repository_file_id=repository_file.id if repository_file is not None else None,
            finding_id=finding.id,
            source_type=evidence_source_type,
            rule_id=rule_id,
            file_path=repository_file.relative_path if repository_file is not None else None,
            line_start=hit.line_start,
            line_end=hit.line_end,
            snippet=hit.snippet,
            description=hit.summary,
            confidence=hit.confidence,
            evidence_metadata=hit.evidence_metadata,
        )
    )
