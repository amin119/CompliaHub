import hashlib


def sha256_bytes(data: bytes) -> str:
    """Content hash used for upload dedup/idempotency: re-uploading the same
    bytes always produces the same hash, so the caller can detect "already
    ingested" without touching the parse/chunk pipeline at all.
    """
    return hashlib.sha256(data).hexdigest()
