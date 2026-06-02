"""Stage 28 — code-workspace validator unit tests."""

from __future__ import annotations

import os

from shared.sdk.code_workspace import (
    validate_allowlist,
    validate_diff_not_empty,
    validate_generated_files_exist,
    validate_no_denied_paths,
    validate_no_secrets,
    validate_python_syntax_if_py,
    validate_tests_syntax_if_py,
)


def _write(tmp_path, rel, content):
    full = os.path.join(str(tmp_path), rel)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as fh:
        fh.write(content)
    return rel


def test_validate_generated_files_exist_passes(tmp_path):
    rel = _write(tmp_path, "docs/generated/a.md", "# hi")
    ok, reason = validate_generated_files_exist(str(tmp_path), [rel])
    assert ok is True
    assert reason == "all_exist"


def test_validate_generated_files_exist_reports_missing(tmp_path):
    ok, reason = validate_generated_files_exist(str(tmp_path), ["docs/generated/none.md"])
    assert ok is False
    assert "missing" in reason


def test_validate_allowlist_pass_and_fail():
    ok, _ = validate_allowlist(["docs/generated/a.md", "apps/demo-generated/x_api.py"])
    assert ok is True
    ok, reason = validate_allowlist(["apps/orchestrator/src/main.py"])
    assert ok is False
    assert "not_in_allowlist" in reason


def test_validate_no_denied_paths_blocks_secret_files():
    ok, reason = validate_no_denied_paths([".env.staging"])
    assert ok is False
    assert "denied:" in reason


def test_validate_no_secrets_blocks_token_payload(tmp_path):
    rel = _write(tmp_path, "docs/generated/oops.md", "token = ghp_" + "A" * 40)
    ok, reason = validate_no_secrets(str(tmp_path), [rel])
    assert ok is False
    assert "secret_like" in reason


def test_validate_no_secrets_accepts_clean_content(tmp_path):
    rel = _write(tmp_path, "docs/generated/clean.md", "# nothing fishy\n")
    ok, _ = validate_no_secrets(str(tmp_path), [rel])
    assert ok is True


def test_validate_python_syntax_passes_valid_py(tmp_path):
    rel = _write(tmp_path, "apps/demo-generated/ok.py", "def f():\n    return 1\n")
    ok, reason = validate_python_syntax_if_py(str(tmp_path), [rel])
    assert ok is True
    assert reason == "all_py_compile_ok"


def test_validate_python_syntax_rejects_invalid_py(tmp_path):
    rel = _write(tmp_path, "apps/demo-generated/bad.py", "def f(:\n  return 1\n")
    ok, reason = validate_python_syntax_if_py(str(tmp_path), [rel])
    assert ok is False
    assert "py_compile_error" in reason


def test_validate_tests_syntax_targets_only_tests(tmp_path):
    rel_test = _write(tmp_path, "tests/generated/test_x.py", "def test_x():\n    assert True\n")
    rel_app = _write(tmp_path, "apps/demo-generated/bad.py", "def f(:\n  return 1\n")
    # ``validate_tests_syntax_if_py`` only walks tests/ — the broken
    # app file must be ignored.
    ok, _ = validate_tests_syntax_if_py(str(tmp_path), [rel_test, rel_app])
    assert ok is True


def test_validate_diff_not_empty_blocks_blank():
    ok, reason = validate_diff_not_empty("")
    assert ok is False
    assert reason == "empty_diff"


def test_validate_diff_not_empty_requires_hunk():
    ok, reason = validate_diff_not_empty("just a header\n--- a/x\n+++ b/x\n")
    assert ok is False
    assert reason == "no_hunks"


def test_validate_diff_not_empty_accepts_real_diff():
    ok, _ = validate_diff_not_empty("--- a/x\n+++ b/x\n@@ -0,0 +1 @@\n+hello\n")
    assert ok is True
