from io import BytesIO

from minio import Minio

from app.core.config import get_settings

DOCUMENTS_BUCKET = "documents"


def get_minio_client() -> Minio:
    settings = get_settings()
    return Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
    )


def ensure_bucket(client: Minio, bucket: str = DOCUMENTS_BUCKET) -> None:
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)


def upload_document(client: Minio, object_key: str, data: bytes, content_type: str) -> None:
    """Object key convention: `{sha256_hash}/{filename}` — the hash prefix
    means two different documents can never collide on a key, and re-uploading
    the same file maps to the same key (a harmless overwrite of identical bytes).
    """
    ensure_bucket(client)
    client.put_object(
        DOCUMENTS_BUCKET,
        object_key,
        BytesIO(data),
        length=len(data),
        content_type=content_type,
    )
