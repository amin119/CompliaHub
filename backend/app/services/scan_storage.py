from io import BytesIO

from minio import Minio

from app.services import storage

# Its own bucket, not the `documents` bucket — a scanned repository's
# archive and extracted files are a different kind of object with a
# different lifecycle (Phase 1 never links them to a Document), and
# keeping them separate means a bucket-level policy/retention rule can
# differ later without touching standards-document storage.
SCANS_BUCKET = "scans"


def upload_object(client: Minio, object_key: str, data: bytes, content_type: str) -> None:
    storage.ensure_bucket(client, SCANS_BUCKET)
    client.put_object(
        SCANS_BUCKET,
        object_key,
        BytesIO(data),
        length=len(data),
        content_type=content_type,
    )


def download_object(client: Minio, object_key: str) -> bytes:
    response = client.get_object(SCANS_BUCKET, object_key)
    try:
        return response.read()
    finally:
        response.close()
        response.release_conn()
