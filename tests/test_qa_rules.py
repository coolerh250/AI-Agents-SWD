"""Stage 29 — deterministic QA rules unit tests."""

from __future__ import annotations

import os

from shared.sdk.qa.rules import (
    apply_qa_rules,
    classify_finding_auto_fixable,
    is_blocking,
    validate_acceptance_alignment,
    validate_destructive_diff,
    validate_diff_present,
    validate_generated_files_exist,
    validate_no_denied_paths,
    validate_no_secret_patterns,
    validate_pr_draft_sections,
    validate_python_syntax,
    validate_test_files_exist_for_api_task,
)


def _write(tmp_path, rel, content):
    full = os.path.join(str(tmp_path), rel)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as fh:
        fh.write(content)
    return rel


def test_generated_files_exist_passes_when_present(tmp_path):
    rel = _write(tmp_path, "docs/generated/a.md", "# hi")
    findings = validate_generated_files_exist(str(tmp_path), [rel])
    assert findings == []


def test_generated_files_exist_reports_missing(tmp_path):
    findings = validate_generated_files_exist(str(tmp_path), ["docs/generated/none.md"])
    assert len(findings) == 1
    assert findings[0]["severity"] == "error"
    assert findings[0]["auto_fixable"] is True


def test_python_syntax_critical_when_broken(tmp_path):
    rel = _write(tmp_path, "apps/demo-generated/bad.py", "def f(:\n  return 1\n")
    findings = validate_python_syntax(str(tmp_path), [rel])
    assert len(findings) == 1
    assert findings[0]["severity"] == "critical"
    assert findings[0]["auto_fixable"] is True


def test_python_syntax_silent_when_clean(tmp_path):
    rel = _write(tmp_path, "apps/demo-generated/ok.py", "def f():\n    return 1\n")
    findings = validate_python_syntax(str(tmp_path), [rel])
    assert findings == []


def test_missing_api_test_file_finding(tmp_path):
    rel = _write(tmp_path, "apps/demo-generated/t1_api.py", "x = 1\n")
    findings = validate_test_files_exist_for_api_task(
        str(tmp_path), [rel], template_hint="demo_api"
    )
    assert len(findings) == 1
    assert findings[0]["category"] == "test"
    assert findings[0]["auto_fixable"] is True


def test_missing_api_test_no_finding_when_test_exists(tmp_path):
    rel_app = _write(tmp_path, "apps/demo-generated/t1_api.py", "x = 1\n")
    rel_test = _write(tmp_path, "tests/generated/test_t1_api.py", "def test_x():\n    pass\n")
    findings = validate_test_files_exist_for_api_task(
        str(tmp_path), [rel_app, rel_test], template_hint="demo_api"
    )
    assert findings == []


def test_diff_present_flags_empty():
    findings = validate_diff_present([{"file_path": "docs/generated/x.md", "diff_text": ""}])
    assert len(findings) == 1


def test_denied_path_finding_is_critical_and_not_fixable():
    findings = validate_no_denied_paths([".env.staging"])
    assert findings and findings[0]["severity"] == "critical"
    assert findings[0]["auto_fixable"] is False


def test_secret_pattern_finding_critical_not_fixable(tmp_path):
    rel = _write(tmp_path, "docs/generated/oops.md", "token = ghp_" + "A" * 40 + "\n")
    findings = validate_no_secret_patterns(str(tmp_path), [rel])
    assert findings and findings[0]["severity"] == "critical"
    assert findings[0]["auto_fixable"] is False


def test_pr_draft_missing_required_sections():
    findings = validate_pr_draft_sections({"body": "## Summary\nstub\n\n## Changed Files\nx"})
    assert len(findings) == 1
    assert "missing_sections" in findings[0]["metadata"]
    assert findings[0]["auto_fixable"] is True


def test_pr_draft_complete_no_finding():
    body = (
        "## Summary\nx\n## Changed Files\nx\n## Generated Diff Summary\nx\n"
        "## Validation Result\nx\n## Risk Assessment\nx\n## Rollback Plan\nx\n"
        "## Safety Notes\nx\n"
    )
    findings = validate_pr_draft_sections({"body": body})
    assert findings == []


def test_destructive_diff_finding():
    artifacts = [
        {"file_path": "apps/demo-generated/x.py", "diff_text": "+ os.system('rm -rf /tmp/foo')\n"}
    ]
    findings = validate_destructive_diff(artifacts)
    assert findings and findings[0]["severity"] == "critical"
    assert findings[0]["auto_fixable"] is False


def test_acceptance_alignment_unmet_warning():
    findings = validate_acceptance_alignment(
        work_item={"acceptance_criteria": ["expose a /healthz endpoint with tests"]},
        artifacts=[{"file_path": "docs/generated/x.md"}],
        template_hint="documentation",
    )
    assert findings and findings[0]["severity"] == "warning"
    assert findings[0]["auto_fixable"] is False


def test_acceptance_alignment_no_findings_when_aligned():
    """When the file paths or template_hint mention every criterion's
    keywords (here: api, test), no finding is emitted."""
    findings = validate_acceptance_alignment(
        work_item={"acceptance_criteria": ["expose an api with a test"]},
        artifacts=[
            {"file_path": "apps/demo-generated/t1_api.py"},
            {"file_path": "tests/generated/test_t1_api.py"},
        ],
        template_hint="demo_api",
    )
    assert findings == []


def test_classify_finding_auto_fixable_respects_category():
    fix = {"auto_fixable": True, "category": "security"}
    assert classify_finding_auto_fixable(fix) is False
    fix = {"auto_fixable": True, "category": "syntax"}
    assert classify_finding_auto_fixable(fix) is True


def test_is_blocking_marks_error_and_critical():
    assert is_blocking({"severity": "error"}) is True
    assert is_blocking({"severity": "critical"}) is True
    assert is_blocking({"severity": "warning"}) is False
    assert is_blocking({"severity": "info"}) is False


def test_apply_qa_rules_full_pass_path(tmp_path):
    """An API task with both app + test + complete PR draft yields no blocking findings."""
    app_rel = _write(
        tmp_path,
        "apps/demo-generated/task_api.py",
        "TASK_ID = 'task'\n\ndef handle():\n    return None\n",
    )
    test_rel = _write(
        tmp_path,
        "tests/generated/test_task_api.py",
        "def test_x():\n    assert True\n",
    )
    artifacts = [
        {"file_path": app_rel, "diff_text": "--- a/x\n+++ b/x\n@@ -0,0 +1 @@\n+TASK_ID\n"},
        {"file_path": test_rel, "diff_text": "--- a/y\n+++ b/y\n@@ -0,0 +1 @@\n+def test_x():\n"},
    ]
    pr_draft = {
        "body": (
            "## Summary\nx\n## Changed Files\nx\n## Generated Diff Summary\nx\n"
            "## Validation Result\nx\n## Risk Assessment\nx\n## Rollback Plan\nx\n"
            "## Safety Notes\nx\n"
        )
    }
    findings = apply_qa_rules(
        workspace_path=str(tmp_path),
        artifacts=artifacts,
        file_paths=[app_rel, test_rel],
        pr_draft=pr_draft,
        work_item=None,
        template_hint="demo_api",
    )
    assert [f for f in findings if is_blocking(f)] == []
