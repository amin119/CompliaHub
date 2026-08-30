"""Safe in-memory zip extraction for uploaded repositories.

Repository archives are untrusted input (compliance scanner spec section
37: "repository files are untrusted... implement... archive-bomb
protection, path traversal protection"). Every entry is validated before
any of its bytes are trusted, and the whole archive is capped in both file
count and total size before extraction proceeds far enough to matter.
"""

from __future__ import annotations

import zipfile
from collections.abc import Iterator
from io import BytesIO

DEFAULT_MAX_FILES = 5_000
DEFAULT_MAX_TOTAL_BYTES = 200 * 1024 * 1024  # 200 MB, uncompressed
DEFAULT_MAX_FILE_BYTES = 10 * 1024 * 1024  # 10 MB — a single file this
# large inside a source repository is almost always a vendored binary/asset
# that classification will mark ignored anyway; skip storing it rather
# than pulling it fully into memory first.


class RepoExtractionError(ValueError):
    """A malformed or oversized archive — never a server error, since the
    cause is always something about the untrusted upload itself.
    """


def _is_safe_member_path(name: str) -> bool:
    normalized = name.replace("\\", "/")
    if normalized.startswith("/") or ":" in normalized:
        return False  # absolute path or a Windows drive letter
    return ".." not in normalized.split("/")


def iter_zip_entries(
    data: bytes,
    max_files: int = DEFAULT_MAX_FILES,
    max_total_bytes: int = DEFAULT_MAX_TOTAL_BYTES,
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
) -> Iterator[tuple[str, bytes]]:
    """Yields (relative_path, content) for every regular file in the
    archive whose declared uncompressed size is within `max_file_bytes`
    (larger entries are skipped, not read, so a single huge member can't
    force a large in-memory read on its own). Raises `RepoExtractionError`
    before yielding anything if the archive itself is invalid, exceeds
    `max_files`, or exceeds `max_total_bytes` in declared uncompressed size
    — checked from the central directory up front (a zip-bomb defense: this
    never has to decompress a hostile entry to find out it's too big).
    """
    try:
        archive = zipfile.ZipFile(BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise RepoExtractionError(f"not a valid zip archive: {exc}") from exc

    members = [info for info in archive.infolist() if not info.is_dir()]
    if len(members) > max_files:
        raise RepoExtractionError(
            f"archive contains {len(members)} files, exceeding the {max_files} limit"
        )

    total_declared_size = sum(info.file_size for info in members)
    if total_declared_size > max_total_bytes:
        raise RepoExtractionError(
            f"archive's uncompressed size ({total_declared_size} bytes) exceeds the "
            f"{max_total_bytes} byte limit"
        )

    for info in members:
        if not _is_safe_member_path(info.filename):
            raise RepoExtractionError(f"unsafe path in archive: {info.filename!r}")

    with archive:
        for info in members:
            if info.file_size > max_file_bytes:
                continue
            yield info.filename, archive.read(info)
