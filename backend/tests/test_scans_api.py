import io
import zipfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.db import engine
from app.main import app
from app.services import storage
from app.tasks.celery_app import celery_app


def _infra_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1 FROM scans LIMIT 1"))
        storage.get_minio_client().list_buckets()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _infra_available(),
    reason="requires docker compose up (postgres+redis+minio) with migrations applied",
)


@pytest.fixture(autouse=True, scope="module")
def _eager_celery():
    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True
    yield
    celery_app.conf.task_always_eager = False
    celery_app.conf.task_eager_propagates = False


def _sample_repo_zip() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as archive:
        archive.writestr("src/app/main.py", "import fastapi\n\napp = fastapi.FastAPI()\n")
        archive.writestr(
            "package.json", '{"dependencies": {"next": "16.0.0", "react": "19.0.0"}}'
        )
        archive.writestr("requirements.txt", "fastapi>=0.100.0\n")
        archive.writestr("Dockerfile", "FROM python:3.12\n")
        archive.writestr(".github/workflows/ci.yml", "name: CI\n")
        archive.writestr("node_modules/lodash/index.js", "module.exports = {};\n")
        archive.writestr("README.md", "# Sample repo\n")
    return buf.getvalue()


def test_upload_scan_processes_end_to_end():
    client = TestClient(app)
    data = _sample_repo_zip()

    response = client.post(
        "/scans", files={"file": ("sample-repo.zip", data, "application/zip")}
    )
    assert response.status_code == 201
    scan_id = response.json()["id"]
    assert response.json()["status"] == "pending"

    status_response = client.get(f"/scans/{scan_id}")
    assert status_response.json()["status"] == "ready"
    assert status_response.json()["file_count"] == 6  # node_modules/* excluded
    assert "python" in status_response.json()["detected_languages"]
    assert "fastapi" in status_response.json()["detected_frameworks"]
    assert "docker" in status_response.json()["detected_frameworks"]
    assert "github-actions" in status_response.json()["detected_frameworks"]
    assert "next.js" in status_response.json()["detected_frameworks"]

    files = client.get(f"/scans/{scan_id}/files").json()
    paths = {f["relative_path"] for f in files}
    assert "node_modules/lodash/index.js" not in paths
    assert "src/app/main.py" in paths

    dockerfile = next(f for f in files if f["relative_path"] == "Dockerfile")
    assert dockerfile["component_type"] == "infrastructure_as_code"

    manifest = next(f for f in files if f["relative_path"] == "package.json")
    assert manifest["component_type"] == "dependency_manifest"


def test_upload_scan_same_archive_twice_is_idempotent():
    client = TestClient(app)
    data = _sample_repo_zip()

    files = {"file": ("sample-repo.zip", data, "application/zip")}
    first = client.post("/scans", files=files)
    second = client.post("/scans", files=files)

    assert first.json()["id"] == second.json()["id"]


def test_scan_list_endpoint_returns_uploaded_scans():
    client = TestClient(app)
    data = _sample_repo_zip()
    response = client.post(
        "/scans", files={"file": ("listed-repo.zip", data, "application/zip")}
    )
    scan_id = response.json()["id"]

    listed = client.get("/scans").json()
    assert any(scan["id"] == scan_id for scan in listed)


def test_rerunning_extract_stage_does_not_duplicate_files():
    """Same real-bug shape as the ingestion pipeline's own
    test_rerunning_chunk_stage_does_not_duplicate_chunks: rerunning the
    extract stage in isolation must be a no-op on file count, not additive.
    """
    from app.tasks.scan import extract_and_classify_files_task

    client = TestClient(app)
    data = _sample_repo_zip()
    response = client.post(
        "/scans", files={"file": ("rerun-repo.zip", data, "application/zip")}
    )
    scan_id = response.json()["id"]
    assert client.get(f"/scans/{scan_id}").json()["status"] == "ready"

    first_count = len(client.get(f"/scans/{scan_id}/files").json())
    assert first_count == 6

    extract_and_classify_files_task(scan_id)

    second_count = len(client.get(f"/scans/{scan_id}/files").json())
    assert second_count == first_count


def test_get_scan_files_filters_by_component_type():
    client = TestClient(app)
    data = _sample_repo_zip()
    response = client.post(
        "/scans", files={"file": ("filtered-repo.zip", data, "application/zip")}
    )
    scan_id = response.json()["id"]

    manifests = client.get(f"/scans/{scan_id}/files?component_type=dependency_manifest").json()
    paths = {f["relative_path"] for f in manifests}
    assert paths == {"package.json", "requirements.txt"}


def test_get_scan_returns_404_for_unknown_id():
    client = TestClient(app)
    response = client.get(f"/scans/{'0' * 8}-0000-0000-0000-{'0' * 12}")
    assert response.status_code in (404, 422)


def test_upload_scan_rejects_empty_file():
    client = TestClient(app)
    response = client.post(
        "/scans", files={"file": ("empty.zip", b"", "application/zip")}
    )
    assert response.status_code == 400
