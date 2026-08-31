"""Repository discovery/classification — pure, deterministic, no LLM calls.

Deliberately shallow for Phase 1: extension/filename matching only, no file
content parsing beyond a binary heuristic and (for a small set of manifest
files) simple substring/JSON-key checks. Full AST-based analysis (compliance
scanner spec section 21) is a later phase's job, not this one's — per the
spec's own "deterministic analysis first" principle (section 3) and "never
send a whole repo to an LLM" principle (section 35), Phase 1 doesn't need
either an LLM or a parsing library to produce a useful file inventory.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

# Directories never worth walking into: generated/vendored/cache content
# that would otherwise dominate the file list and hide what actually
# matters. One data-driven list in one place, so reconciling it against a
# more precise spec later is a one-file edit.
DEFAULT_IGNORE_DIRS = frozenset(
    {
        ".git",
        "node_modules",
        "dist",
        "build",
        "target",
        "vendor",
        "__pycache__",
        ".venv",
        "venv",
        "coverage",
        ".next",
        ".nuxt",
        ".idea",
        ".vscode",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "egg-info",
    }
)

# Suffixes never worth storing/classifying as source — binary/lockfile
# noise that would otherwise pollute the file inventory.
DEFAULT_IGNORE_SUFFIXES = frozenset(
    {".min.js", ".min.css", ".lock", ".map", ".pyc", ".so", ".dll", ".exe"}
)

_LANGUAGE_BY_EXTENSION = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".java": "java",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".go": "go",
    ".rs": "rust",
    ".rb": "ruby",
    ".php": "php",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".hpp": "cpp",
    ".cs": "csharp",
    ".swift": "swift",
    ".sql": "sql",
    ".sh": "shell",
    ".bash": "shell",
}

# Well-known filenames/paths mapped straight to a component_type, checked
# before falling back to extension-based classification — a Dockerfile has
# no extension at all, and a manifest's importance has nothing to do with
# which language it's written in.
_FILENAME_COMPONENT_TYPES = {
    "dockerfile": "infrastructure_as_code",
    "docker-compose.yml": "infrastructure_as_code",
    "docker-compose.yaml": "infrastructure_as_code",
    "jenkinsfile": "ci_cd_config",
    ".gitlab-ci.yml": "ci_cd_config",
    "package.json": "dependency_manifest",
    "requirements.txt": "dependency_manifest",
    "pyproject.toml": "dependency_manifest",
    "pipfile": "dependency_manifest",
    "pom.xml": "dependency_manifest",
    "build.gradle": "dependency_manifest",
    "build.gradle.kts": "dependency_manifest",
    "composer.json": "dependency_manifest",
    "go.mod": "dependency_manifest",
    "cargo.toml": "dependency_manifest",
    "gemfile": "dependency_manifest",
    "codeowners": "governance",
    "security.md": "governance",
    "license": "governance",
    "readme.md": "documentation",
    "readme": "documentation",
    "changelog.md": "documentation",
    # Privacy-policy docs (added in scanner Phase 3): without these, a
    # repo's own PRIVACY.md falls through to "unknown", so the GDPR
    # analyzer's "unless documentary evidence exists" carve-out
    # (repo_level_checks.privacy_policy_doc_present) could never trigger for
    # the single most common real case.
    "privacy.md": "documentation",
    "privacy-policy.md": "documentation",
    "privacy_policy.md": "documentation",
    "data-protection.md": "documentation",
    # Model-card/AI-governance docs (added in scanner Phase 4): same
    # rationale as the privacy-doc additions above — without these, a
    # repo's own MODEL_CARD.md falls through to "unknown", so the AI
    # analyzer's "unless documentary evidence exists" carve-out
    # (ai_analysis.repo_level_checks.model_card_doc_present) could never
    # trigger for the single most common real case.
    "model_card.md": "documentation",
    "model-card.md": "documentation",
    "ai_governance.md": "documentation",
    "ai-governance.md": "documentation",
    "model_cards.md": "documentation",
}

_PATH_SUBSTRING_COMPONENT_TYPES = (
    (".github/workflows/", "ci_cd_config"),
    (".azure-pipelines", "ci_cd_config"),
    ("/migrations/", "database_migration"),
    ("/alembic/versions/", "database_migration"),
    ("/tests/", "test_code"),
    ("/test/", "test_code"),
    ("/docs/", "documentation"),
    ("k8s/", "infrastructure_as_code"),
    ("kubernetes/", "infrastructure_as_code"),
    ("helm/", "infrastructure_as_code"),
    ("terraform/", "infrastructure_as_code"),
    (".tf", "infrastructure_as_code"),
)

# Substrings in a manifest's raw text that indicate a known framework —
# simple presence checks, not a real package-manifest parser. Good enough
# for Phase 1's "what frameworks does this repo likely use" inventory;
# false positives here cost nothing since nothing downstream treats this
# as evidence yet.
_FRAMEWORK_MARKERS: dict[str, tuple[str, ...]] = {
    "fastapi": ("fastapi",),
    "django": ("django",),
    "flask": ("flask",),
    "express": ('"express"',),
    "react": ('"react"',),
    "next.js": ('"next"',),
    "vue": ('"vue"',),
    "angular": ('"@angular/core"',),
    "spring": ("springframework",),
}


@dataclass(frozen=True)
class FileClassification:
    language: str | None
    component_type: str
    is_ignored: bool
    is_binary_heuristic: bool


def is_ignored_path(relative_path: str) -> bool:
    parts = relative_path.replace("\\", "/").split("/")
    if any(part in DEFAULT_IGNORE_DIRS or part.endswith(".egg-info") for part in parts[:-1]):
        return True
    return any(relative_path.endswith(suffix) for suffix in DEFAULT_IGNORE_SUFFIXES)


def _extension(relative_path: str) -> str:
    name = relative_path.rsplit("/", 1)[-1]
    if "." not in name:
        return ""
    return "." + name.rsplit(".", 1)[-1].lower()


def classify_file(relative_path: str, content_head: bytes = b"") -> FileClassification:
    """Classify one file by path/filename/extension alone — no need to read
    the whole file. `content_head` (a small prefix, if available) only
    feeds the binary heuristic below; classification itself never depends
    on it.
    """
    normalized = relative_path.replace("\\", "/")
    if is_ignored_path(normalized):
        return FileClassification(None, "unknown", True, False)

    filename = normalized.rsplit("/", 1)[-1].lower()
    component_type = _FILENAME_COMPONENT_TYPES.get(filename)
    if component_type is None:
        # A leading "/" is added before matching so a directory-boundary
        # substring like "/docs/" matches a file at the repository root
        # ("docs/x.md" -> "/docs/x.md") the same way it already matches a
        # nested one ("backend/docs/x.md") — without it, only the nested
        # case matched, which is exactly the kind of inconsistency a real
        # repository's top-level docs/tests/migrations directory would hit.
        anchored = "/" + normalized.lower()
        for substring, mapped_type in _PATH_SUBSTRING_COMPONENT_TYPES:
            if substring in anchored:
                component_type = mapped_type
                break

    language = _LANGUAGE_BY_EXTENSION.get(_extension(normalized))
    if component_type is None:
        component_type = "application_code" if language else "unknown"

    # A null byte anywhere in the first chunk is a reliable, dependency-free
    # binary signal — real text files (including UTF-16 with a BOM) don't
    # produce one in practice at this scale, and this project deliberately
    # avoids adding a `python-magic`/libmagic dependency for Phase 1.
    is_binary = b"\x00" in content_head

    return FileClassification(language, component_type, False, is_binary)


def detect_frameworks(manifest_contents: dict[str, bytes]) -> list[str]:
    """`manifest_contents` maps relative_path -> raw bytes, for the small
    subset of files already classified `dependency_manifest` (plus
    Dockerfile/CI config) during the walk — never the whole repository.
    """
    frameworks: set[str] = set()
    combined_text = ""
    for path, data in manifest_contents.items():
        try:
            combined_text += data.decode("utf-8", errors="ignore").lower() + "\n"
        except Exception:
            continue
        lower_path = path.lower()
        if lower_path.endswith("dockerfile") or "docker-compose" in lower_path:
            frameworks.add("docker")
        if ".github/workflows/" in lower_path.replace("\\", "/"):
            frameworks.add("github-actions")

    for framework, markers in _FRAMEWORK_MARKERS.items():
        if any(marker in combined_text for marker in markers):
            frameworks.add(framework)

    return sorted(frameworks)


def parse_package_json_dependencies(data: bytes) -> list[str]:
    """Best-effort dependency-name extraction from `package.json`, used only
    to widen what `detect_frameworks` can see — a malformed manifest just
    yields an empty list rather than failing the whole scan.
    """
    try:
        payload = json.loads(data.decode("utf-8", errors="ignore"))
    except Exception:
        return []
    names: list[str] = []
    for key in ("dependencies", "devDependencies"):
        section = payload.get(key)
        if isinstance(section, dict):
            names.extend(section.keys())
    return names
