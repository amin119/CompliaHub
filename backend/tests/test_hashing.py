from app.services.hashing import sha256_bytes


def test_sha256_bytes_is_deterministic():
    assert sha256_bytes(b"hello") == sha256_bytes(b"hello")


def test_sha256_bytes_differs_for_different_input():
    assert sha256_bytes(b"hello") != sha256_bytes(b"world")
