from app.services.finding_remediation import build_unified_diff


def test_produces_correct_a_b_headers():
    diff = build_unified_diff("app/auth.py", 1, "a\n", "b\n")
    assert "--- a/app/auth.py" in diff
    assert "+++ b/app/auth.py" in diff


def test_hunk_header_reflects_window_start_line_not_window_relative():
    original = "line a\nline b\nBAD LINE\nline d\nline e\n"
    suggested = "line a\nline b\nGOOD LINE\nline d\nline e\n"
    diff = build_unified_diff("x.py", 98, original, suggested)

    assert "@@ -98,5 +98,5 @@" in diff
    assert "@@ -1," not in diff


def test_no_change_produces_empty_diff():
    diff = build_unified_diff("x.py", 100, "same\n", "same\n")
    assert diff == ""


def test_multiline_change_produces_correct_plus_minus_lines():
    original = (
        "import hashlib\n\n"
        "def hash_password(password):\n"
        "    return hashlib.md5(password.encode()).hexdigest()\n"
    )
    suggested = (
        "import hashlib\nimport bcrypt\n\n"
        "def hash_password(password):\n"
        "    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()\n"
    )
    diff = build_unified_diff("app/auth.py", 1, original, suggested)

    assert "+import bcrypt" in diff
    assert "-    return hashlib.md5(password.encode()).hexdigest()" in diff
    assert "+    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()" in diff


def test_output_matches_standard_unified_diff_grammar():
    original = "a\nb\nc\n"
    suggested = "a\nx\nc\n"
    diff = build_unified_diff("f.py", 1, original, suggested)
    lines = diff.splitlines()

    assert lines[0].startswith("--- a/")
    assert lines[1].startswith("+++ b/")
    for line in lines[2:]:
        assert line[0] in ("@", " ", "+", "-")


def test_window_start_line_default_is_one_when_flagged_line_is_early():
    diff = build_unified_diff("f.py", 1, "old\n", "new\n")
    assert "@@ -1,1 +1,1 @@" in diff or "@@ -1 +1 @@" in diff


def test_replaced_final_line_without_trailing_newline_stays_on_its_own_line():
    """Regression: `locate_fix_target`'s real window text (`"\n".join(...)`
    of `str.splitlines()` output) never ends with a trailing newline, so
    whenever the flagged line is the window's last line — the common case
    for a fix near end-of-file — `original_window_text` arrives here with
    no trailing "\n". Caught via live end-to-end verification: without
    normalizing this, difflib emits that line with no terminator, and the
    following "+" line runs directly into it with no separating newline
    once the diff is joined into one string, corrupting the diff.
    """
    original = "import hashlib\n\ndef hash_password(password):\n    return hashlib.md5(password.encode()).hexdigest()"
    suggested = "import hashlib\nimport os\n\ndef hash_password(password):\n    return hashlib.sha256(password.encode()).hexdigest()"
    diff = build_unified_diff("app/auth.py", 1, original, suggested)

    assert "hexdigest()+" not in diff
    lines = diff.splitlines()
    minus_line = next(line for line in lines if line.startswith("-    return hashlib.md5"))
    assert minus_line == "-    return hashlib.md5(password.encode()).hexdigest()"


def test_context_lines_parameter_is_respected():
    original = "\n".join(f"line{i}" for i in range(1, 11)) + "\n"
    suggested_lines = [f"line{i}" for i in range(1, 11)]
    suggested_lines[4] = "CHANGED"
    suggested = "\n".join(suggested_lines) + "\n"

    diff_wide = build_unified_diff("f.py", 1, original, suggested, context_lines=5)
    diff_narrow = build_unified_diff("f.py", 1, original, suggested, context_lines=1)

    assert len(diff_wide) > len(diff_narrow)
