from app.services.repo_discovery import classify_file, detect_frameworks, is_ignored_path


def test_ignores_node_modules_and_git():
    assert is_ignored_path("node_modules/foo/index.js")
    assert is_ignored_path(".git/HEAD")
    assert is_ignored_path("backend/.venv/lib/x.py")


def test_does_not_ignore_normal_source():
    assert not is_ignored_path("src/app/main.py")


def test_classifies_python_application_code():
    result = classify_file("src/app/main.py")
    assert result.language == "python"
    assert result.component_type == "application_code"
    assert not result.is_ignored


def test_classifies_dependency_manifests():
    assert classify_file("requirements.txt").component_type == "dependency_manifest"
    assert classify_file("frontend/package.json").component_type == "dependency_manifest"
    assert classify_file("backend/pyproject.toml").component_type == "dependency_manifest"


def test_classifies_dockerfile_as_infrastructure():
    result = classify_file("Dockerfile")
    assert result.component_type == "infrastructure_as_code"
    assert result.language is None


def test_classifies_ci_workflow():
    result = classify_file(".github/workflows/ci.yml")
    assert result.component_type == "ci_cd_config"


def test_classifies_test_code():
    result = classify_file("backend/tests/test_scans_api.py")
    assert result.component_type == "test_code"
    assert result.language == "python"


def test_classifies_readme_as_documentation():
    assert classify_file("README.md").component_type == "documentation"
    assert classify_file("docs/architecture.md").component_type == "documentation"


def test_ignored_file_returns_ignored_classification():
    result = classify_file("node_modules/lodash/index.js")
    assert result.is_ignored is True
    assert result.component_type == "unknown"


def test_binary_heuristic_detects_null_byte():
    result = classify_file("assets/logo.bin", content_head=b"\x89PNG\x00\x01\x02")
    assert result.is_binary_heuristic is True


def test_binary_heuristic_false_for_text():
    result = classify_file("src/app/main.py", content_head=b"import os\n")
    assert result.is_binary_heuristic is False


def test_detect_frameworks_from_package_json():
    manifest = {"package.json": b'{"dependencies": {"next": "16.0.0", "react": "19.0.0"}}'}
    frameworks = detect_frameworks(manifest)
    assert "next.js" in frameworks
    assert "react" in frameworks


def test_detect_frameworks_from_requirements_txt():
    manifest = {"requirements.txt": b"fastapi>=0.100.0\nuvicorn\n"}
    assert "fastapi" in detect_frameworks(manifest)


def test_detect_frameworks_finds_docker_and_ci():
    manifest = {
        "Dockerfile": b"FROM python:3.12",
        ".github/workflows/ci.yml": b"name: CI",
    }
    frameworks = detect_frameworks(manifest)
    assert "docker" in frameworks
    assert "github-actions" in frameworks


def test_detect_frameworks_empty_for_no_markers():
    assert detect_frameworks({"README.md": b"# Hello"}) == []
