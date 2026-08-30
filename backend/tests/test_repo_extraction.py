import io
import zipfile

import pytest

from app.services.repo_extraction import RepoExtractionError, iter_zip_entries


def _make_zip(entries: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
    return buf.getvalue()


def test_extracts_normal_zip_entries():
    data = _make_zip({"src/main.py": b"print('hi')", "README.md": b"# hello"})
    entries = dict(iter_zip_entries(data))
    assert entries["src/main.py"] == b"print('hi')"
    assert entries["README.md"] == b"# hello"


def test_rejects_not_a_zip():
    with pytest.raises(RepoExtractionError, match="not a valid zip"):
        list(iter_zip_entries(b"this is not a zip file"))


def test_rejects_zip_slip_path():
    data = _make_zip({"../../etc/passwd": b"malicious"})
    with pytest.raises(RepoExtractionError, match="unsafe path"):
        list(iter_zip_entries(data))


def test_rejects_absolute_path():
    data = _make_zip({"/etc/passwd": b"malicious"})
    with pytest.raises(RepoExtractionError, match="unsafe path"):
        list(iter_zip_entries(data))


def test_rejects_too_many_files():
    data = _make_zip({f"file_{i}.txt": b"x" for i in range(10)})
    with pytest.raises(RepoExtractionError, match="exceeding"):
        list(iter_zip_entries(data, max_files=5))


def test_rejects_total_size_over_limit():
    data = _make_zip({"big.bin": b"x" * 1000})
    with pytest.raises(RepoExtractionError, match="exceeds"):
        list(iter_zip_entries(data, max_total_bytes=100))


def test_skips_single_file_over_per_file_limit_without_raising():
    data = _make_zip({"small.txt": b"ok", "huge.bin": b"x" * 1000})
    entries = dict(iter_zip_entries(data, max_file_bytes=100))
    assert entries == {"small.txt": b"ok"}


def test_directory_entries_are_not_yielded():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as archive:
        archive.writestr("src/", b"")
        archive.writestr("src/main.py", b"print(1)")
    entries = dict(iter_zip_entries(buf.getvalue()))
    assert list(entries.keys()) == ["src/main.py"]
