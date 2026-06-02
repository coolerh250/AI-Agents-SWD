"""Stage 28 — policy / allowlist / risk-classification unit tests."""

from __future__ import annotations

from shared.sdk.code_workspace import (
    DEFAULT_ALLOWED_PATHS,
    DEFAULT_DENIED_PATHS,
    classify_change_risk,
    validate_allowed_path,
    validate_change_type,
    validate_no_destructive_change,
    validate_no_secret_content,
)


def test_allowed_path_under_docs_generated_passes():
    ok, reason = validate_allowed_path("docs/generated/t1.md")
    assert ok is True
    assert reason.startswith("allowed:")


def test_allowed_path_under_apps_demo_generated_passes():
    ok, _ = validate_allowed_path("apps/demo-generated/task_api.py")
    assert ok is True


def test_path_outside_allowlist_is_blocked():
    ok, reason = validate_allowed_path("apps/orchestrator/src/operations.py")
    assert ok is False
    assert reason == "not_in_allowlist"


def test_dot_dot_traversal_is_blocked():
    ok, reason = validate_allowed_path("docs/generated/../../etc/passwd")
    assert ok is False
    assert reason == "path_traversal"


def test_absolute_path_is_blocked():
    ok, reason = validate_allowed_path("/etc/passwd")
    assert ok is False
    assert reason == "absolute_path"


def test_denylist_blocks_dotgithub_even_under_allowlist():
    # An attacker tries to write under an "allowed" prefix that resolves
    # to a denied path — denylist must win.
    ok, reason = validate_allowed_path(".github/workflows/ci.yml")
    assert ok is False
    assert reason.startswith("denied:")


def test_denylist_blocks_progress_md():
    ok, reason = validate_allowed_path("source/progress.md")
    assert ok is False
    assert reason.startswith("denied:")


def test_denylist_blocks_secret_files():
    for path in ("config.env", "production.key", "API_secret.pem", ".env.staging"):
        ok, reason = validate_allowed_path(path)
        assert ok is False, f"{path} should be denied"
        assert reason.startswith("denied:"), reason


def test_change_type_delete_is_refused():
    ok, _ = validate_change_type("delete")
    assert ok is False


def test_change_type_create_and_update_pass():
    assert validate_change_type("create")[0] is True
    assert validate_change_type("update")[0] is True


def test_secret_content_detector_blocks_github_token():
    ok, reason = validate_no_secret_content("token = ghp_" + "A" * 40)
    assert ok is False
    assert "github_token" in reason


def test_secret_content_detector_blocks_aws_key():
    ok, reason = validate_no_secret_content('AWS_ACCESS_KEY_ID="AKIA' + "A" * 16 + '"')
    assert ok is False
    assert "aws_access_key" in reason


def test_secret_content_detector_blocks_private_key_header():
    ok, _ = validate_no_secret_content("-----BEGIN RSA PRIVATE KEY-----\nMIIEv...")
    assert ok is False


def test_secret_content_detector_passes_normal_text():
    ok, _ = validate_no_secret_content("# documentation\n\nthis is fine\n")
    assert ok is True


def test_destructive_diff_detector_blocks_rm_rf():
    ok, reason = validate_no_destructive_change("+ subprocess.run(['rm', '-rf', '/'])")
    assert ok is False
    assert "destructive:rm_rf" in reason
    # also catches the shell form
    ok2, reason2 = validate_no_destructive_change("+ os.system('rm -rf /tmp/foo')")
    assert ok2 is False
    assert "destructive:rm_rf" in reason2


def test_destructive_diff_detector_blocks_drop_database():
    ok, reason = validate_no_destructive_change("+ DROP DATABASE aiagents;")
    assert ok is False
    assert "destructive:drop_database" in reason


def test_destructive_diff_detector_passes_normal_diff():
    diff = "@@ -1,1 +1,2 @@\n hello\n+world\n"
    ok, _ = validate_no_destructive_change(diff)
    assert ok is True


def test_risk_low_for_docs_only():
    risk = classify_change_risk([{"file_path": "docs/generated/t1.md"}])
    assert risk["risk_level"] == "low"
    assert risk["docs_count"] == 1


def test_risk_medium_for_app_code():
    risk = classify_change_risk(
        [
            {"file_path": "docs/generated/t1.md"},
            {"file_path": "apps/demo-generated/t1_api.py"},
        ]
    )
    assert risk["risk_level"] == "medium"
    assert risk["app_count"] == 1


def test_risk_high_when_outside_allowlist():
    risk = classify_change_risk([{"file_path": "apps/orchestrator/src/operations.py"}])
    assert risk["risk_level"] == "high"
    assert "outside_allowlist" in risk["reason"]


def test_default_allow_and_deny_lists_have_expected_anchors():
    assert "docs/generated/" in DEFAULT_ALLOWED_PATHS
    assert "apps/demo-generated/" in DEFAULT_ALLOWED_PATHS
    assert "source/progress.md" in DEFAULT_DENIED_PATHS
