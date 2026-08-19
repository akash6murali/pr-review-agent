from app.diff_parser import parse_diff, format_diff_for_review

SAMPLE_DIFF = """\
diff --git a/app/main.py b/app/main.py
index abc123..def456 100644
--- a/app/main.py
+++ b/app/main.py
@@ -10,6 +10,9 @@ def existing():
     line_10
     line_11
+    new_line_12
+    new_line_13
     line_14
     line_15
+    new_line_16
"""


def test_parse_diff_extracts_python_files():
    files = parse_diff(SAMPLE_DIFF)
    assert len(files) == 1
    assert files[0].path == "app/main.py"


def test_parse_diff_valid_lines():
    files = parse_diff(SAMPLE_DIFF)
    # Lines 12, 13, 16 are new (+), context lines also in valid_lines
    assert 12 in files[0].valid_lines
    assert 13 in files[0].valid_lines
    assert 16 in files[0].valid_lines


def test_parse_diff_non_python_ignored():
    diff = SAMPLE_DIFF.replace("app/main.py", "app/main.js")
    files = parse_diff(diff)
    assert len(files) == 0


def test_format_diff_respects_budget():
    files = parse_diff(SAMPLE_DIFF)
    formatted = format_diff_for_review(files, max_chars=50)
    assert len(formatted) <= 50 + len("\n... [truncated]")
