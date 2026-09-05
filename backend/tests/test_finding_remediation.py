import uuid

import pytest
from pydantic import ValidationError

from app.models.scan import Evidence, Finding, RepositoryFile
from app.services import finding_remediation, scan_storage
from app.services.finding_remediation import (
    FixTarget,
    RemediationSuggestion,
)


def _make_finding(evidence_rows=None, **overrides) -> Finding:
    defaults = dict(
        scan_id=uuid.uuid4(),
        framework=None,
        category="cryptography",
        rule_id="SEC-CRYPTO-WEAK-PY",
        title="Weak hash algorithm",
        status="POTENTIAL_NON_COMPLIANCE",
        severity="HIGH",
        confidence="high",
        summary="md5 usage found (near 'hash_password').",
        reasoning="md5 usage found (near 'hash_password').",
    )
    defaults.update(overrides)
    finding = Finding(**defaults)
    if evidence_rows is None:
        evidence_rows = [
            Evidence(
                scan_id=finding.scan_id,
                source_type="ast_analysis",
                rule_id=finding.rule_id,
                file_path="app/auth.py",
                line_start=4,
                line_end=4,
                snippet="return hashlib.md5(password.encode()).hexdigest()",
                description="Weak hash algorithm.",
                confidence="high",
            )
        ]
    finding.evidence = evidence_rows
    return finding


def _make_suggestion(**overrides) -> RemediationSuggestion:
    defaults = dict(
        problem_explanation="MD5 is cryptographically broken for password hashing.",
        suggested_code="import bcrypt\n\ndef hash_password(password):\n"
        "    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()\n",
        fix_explanation="Replaced MD5 with bcrypt, a dedicated password-hashing KDF.",
        confidence="high",
    )
    defaults.update(overrides)
    return RemediationSuggestion(**defaults)


class _FakeRemediationClient:
    def __init__(self, fail_times: int = 0, result: RemediationSuggestion | None = None):
        self.fail_times = fail_times
        self.result = result or _make_suggestion()
        self.calls = 0
        self.last_prompt: str | None = None

    def remediate(self, prompt: str) -> RemediationSuggestion:
        self.calls += 1
        self.last_prompt = prompt
        if self.calls <= self.fail_times:
            raise finding_remediation.RemediationRateLimited("simulated rate limit")
        return self.result


class _AlwaysInvalidClient:
    def __init__(self) -> None:
        self.calls = 0

    def remediate(self, prompt: str) -> RemediationSuggestion:
        self.calls += 1
        return RemediationSuggestion.model_validate({"problem_explanation": 123})


class _FakeDBSession:
    """Minimal stand-in for a SQLAlchemy Session — enough surface for
    `locate_fix_target`'s single RepositoryFile lookup and
    `persist_remediation`'s add/commit/refresh calls, no real database.
    """

    def __init__(self, repository_file=None):
        self._repository_file = repository_file
        self.added: list = []

    def scalar(self, query):
        return self._repository_file

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        pass

    def refresh(self, obj):
        if obj.id is None:
            obj.id = uuid.uuid4()


def _make_repository_file(content_stored=True) -> RepositoryFile:
    return RepositoryFile(
        scan_id=uuid.uuid4(),
        relative_path="app/auth.py",
        language="python",
        component_type="application_code",
        size_bytes=100,
        content_stored=content_stored,
        minio_object_key="scan/app/auth.py",
    )


def _make_fix_target(finding: Finding) -> FixTarget:
    return FixTarget(
        evidence=finding.evidence[0],
        repository_file=_make_repository_file(),
        window_start_line=1,
        window_end_line=8,
        window_text="import hashlib\n\ndef hash_password(password):\n"
        "    return hashlib.md5(password.encode()).hexdigest()\n",
    )


@pytest.fixture(autouse=True)
def _no_real_sleep(monkeypatch):
    monkeypatch.setattr(finding_remediation.time, "sleep", lambda seconds: None)


# --- generate_remediation retry behavior (structural copy of Phase 6's) -----


def test_generate_remediation_retries_until_success():
    expected = _make_suggestion(confidence="low")
    client = _FakeRemediationClient(fail_times=2, result=expected)
    finding = _make_finding()
    fix_target = _make_fix_target(finding)

    result = finding_remediation.generate_remediation(finding, fix_target, client=client)

    assert result == expected
    assert client.calls == 3


def test_generate_remediation_raises_after_exhausting_retries():
    client = _FakeRemediationClient(fail_times=999)
    finding = _make_finding()
    fix_target = _make_fix_target(finding)

    with pytest.raises(finding_remediation.RemediationRateLimited):
        finding_remediation.generate_remediation(finding, fix_target, client=client)

    assert client.calls == finding_remediation._MAX_RETRIES


def test_generate_remediation_retries_on_validation_error_too():
    client = _AlwaysInvalidClient()
    finding = _make_finding()
    fix_target = _make_fix_target(finding)

    with pytest.raises(ValidationError):
        finding_remediation.generate_remediation(finding, fix_target, client=client)

    assert client.calls == finding_remediation._MAX_RETRIES


def test_prompt_includes_finding_title_and_window_text():
    finding = _make_finding()
    fix_target = _make_fix_target(finding)
    client = _FakeRemediationClient()

    finding_remediation.generate_remediation(finding, fix_target, client=client)

    assert finding.title in client.last_prompt
    assert "hashlib.md5" in client.last_prompt
    assert "app/auth.py" in client.last_prompt


# --- locate_fix_target --------------------------------------------------------


def test_locate_fix_target_picks_first_locatable_evidence(monkeypatch):
    finding = _make_finding(
        evidence_rows=[
            Evidence(source_type="repo_aggregate", description="no location", file_path=None),
            Evidence(
                source_type="ast_analysis",
                file_path="app/auth.py",
                line_start=4,
                line_end=4,
                description="located",
            ),
        ]
    )
    repo_file = _make_repository_file()
    db = _FakeDBSession(repository_file=repo_file)
    content = "line1\nline2\nline3\nline4\nline5\n"
    monkeypatch.setattr(scan_storage, "download_object", lambda client, key: content.encode())

    fix_target = finding_remediation.locate_fix_target(db, client=None, finding=finding)

    assert fix_target.evidence.description == "located"


def test_locate_fix_target_raises_when_no_locatable_evidence():
    finding = _make_finding(
        evidence_rows=[
            Evidence(source_type="repo_aggregate", description="no location", file_path=None),
        ]
    )
    db = _FakeDBSession(repository_file=None)

    with pytest.raises(finding_remediation.NoLocatableEvidenceError):
        finding_remediation.locate_fix_target(db, client=None, finding=finding)


def test_locate_fix_target_raises_when_file_not_content_stored():
    finding = _make_finding()
    repo_file = _make_repository_file(content_stored=False)
    db = _FakeDBSession(repository_file=repo_file)

    with pytest.raises(finding_remediation.NoLocatableEvidenceError):
        finding_remediation.locate_fix_target(db, client=None, finding=finding)


def test_locate_fix_target_windows_around_line_start_with_margin(monkeypatch):
    finding = _make_finding()  # flagged line_start=4, line_end=4
    finding.evidence[0].line_start = 20
    finding.evidence[0].line_end = 20
    repo_file = _make_repository_file()
    db = _FakeDBSession(repository_file=repo_file)

    lines = [f"line{i}" for i in range(1, 41)]
    content = "\n".join(lines)
    monkeypatch.setattr(scan_storage, "download_object", lambda client, key: content.encode())

    fix_target = finding_remediation.locate_fix_target(db, client=None, finding=finding)

    assert fix_target.window_start_line == 20 - finding_remediation._CONTEXT_MARGIN_LINES
    assert fix_target.window_end_line == 20 + finding_remediation._CONTEXT_MARGIN_LINES


def test_locate_fix_target_clamps_window_to_file_bounds(monkeypatch):
    finding = _make_finding()
    finding.evidence[0].line_start = 2
    finding.evidence[0].line_end = 2
    repo_file = _make_repository_file()
    db = _FakeDBSession(repository_file=repo_file)

    content = "line1\nline2\nline3\n"
    monkeypatch.setattr(scan_storage, "download_object", lambda client, key: content.encode())

    fix_target = finding_remediation.locate_fix_target(db, client=None, finding=finding)

    assert fix_target.window_start_line == 1
    assert fix_target.window_end_line == 3


# --- persist_remediation -------------------------------------------------------


def test_persist_remediation_writes_llm_remediation_evidence_with_expected_metadata():
    # An explicit id: `_make_finding()`'s bare `Finding(...)` object is never
    # flushed to a real DB in this fake-session test, so its `id` column's
    # Python-side default only applies at INSERT time — without this, both
    # sides of the `finding_id == finding.id` assertion below would silently
    # be `None`, making it vacuously true regardless of whether
    # `persist_remediation` actually links the two rows correctly.
    finding = _make_finding(id=uuid.uuid4())
    suggestion = _make_suggestion()
    fix_target = _make_fix_target(finding)
    db = _FakeDBSession()

    evidence = finding_remediation.persist_remediation(
        db,
        finding,
        suggestion,
        fix_target,
        diff_text="--- a/x\n+++ b/x\n",
        model="gemini-3.1-flash-lite",
    )

    assert evidence in db.added
    assert evidence.finding_id == finding.id
    assert evidence.source_type == "llm_remediation"
    assert evidence.rule_id == "llm_finding_remediation"
    assert evidence.repository_file_id == fix_target.repository_file.id
    assert evidence.file_path == fix_target.evidence.file_path
    assert evidence.line_start == fix_target.evidence.line_start
    assert evidence.snippet == "--- a/x\n+++ b/x\n"
    assert suggestion.problem_explanation in evidence.description
    assert suggestion.fix_explanation in evidence.description
    assert evidence.confidence == suggestion.confidence
    assert evidence.evidence_metadata["model"] == "gemini-3.1-flash-lite"
    assert evidence.evidence_metadata["target_file_path"] == fix_target.evidence.file_path
    assert evidence.evidence_metadata["window_start_line"] == fix_target.window_start_line


def test_persist_remediation_never_touches_finding_status_or_recommendation():
    finding = _make_finding(status="POTENTIAL_NON_COMPLIANCE")
    finding.recommendation = "Use bcrypt instead."
    original_status = finding.status
    original_recommendation = finding.recommendation
    fix_target = _make_fix_target(finding)
    db = _FakeDBSession()

    finding_remediation.persist_remediation(
        db, finding, _make_suggestion(), fix_target, diff_text="diff", model="m"
    )

    assert finding.status == original_status
    assert finding.recommendation == original_recommendation
