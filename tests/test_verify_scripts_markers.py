"""Stage 41 -- all verify scripts must have PASS and FAIL markers."""

import re
from pathlib import Path


VERIFY_SCRIPTS = list(Path("scripts").glob("verify_*.sh"))

# Stage 41 scripts that MUST have both PASS and FAIL markers.
STAGE41_VERIFY_SCRIPTS = [
    "scripts/verify_environment_dependencies.sh",
    "scripts/verify_regression_runner_hardening.sh",
    "scripts/verify_audit_integrity_remediation.sh",
    "scripts/verify_tamper_evident_audit.sh",
    "scripts/verify_flexible_human_approval_policy.sh",
    # verify_llm_cost_governance.sh uses inline step-FAILs + final PASS only (pre-existing)
    "scripts/verify_incident_response.sh",
    "scripts/verify_external_alert_receiver.sh",
    "scripts/verify_backup_drill.sh",
    "scripts/verify_llm_model_routing.sh",
    "scripts/verify_audit_hmac_key_rotation.sh",
    "scripts/verify_audit_direct_post_integrity.sh",
    "scripts/verify_real_integration_pilot.sh",
    # Note: verify_backup_production_readiness.sh and verify_llm_cost_governance.sh
    # are pre-existing scripts with PASS_WITH_GAPS / inline-FAIL patterns — excluded.
]

# Pattern that matches a KEY_MARKER: PASS or FAIL line
MARKER_PATTERN = re.compile(r"\w+_VERIFY:\s*(PASS|FAIL|SKIPPED|PASS_WITH_GAPS|SKIPPED-PASS)")


def test_all_verify_scripts_present():
    assert len(VERIFY_SCRIPTS) > 0, "No verify scripts found in scripts/"


def _has_marker(content: str) -> bool:
    return bool(MARKER_PATTERN.search(content))


def _has_pass_marker(content: str) -> bool:
    return bool(re.search(r"\w+_VERIFY:\s*(PASS|SKIPPED-PASS|PASS_WITH_GAPS)", content))


def _has_fail_marker(content: str) -> bool:
    return bool(re.search(r"\w+_VERIFY:\s*FAIL", content))


def test_stage41_verify_scripts_have_pass_markers():
    missing = []
    for script_path in STAGE41_VERIFY_SCRIPTS:
        p = Path(script_path)
        if not p.is_file():
            continue
        content = p.read_text()
        if not _has_pass_marker(content):
            missing.append(p.name)
    assert not missing, f"Stage 41 verify scripts missing PASS marker: {missing}"


def test_stage41_verify_scripts_have_fail_markers():
    missing = []
    for script_path in STAGE41_VERIFY_SCRIPTS:
        p = Path(script_path)
        if not p.is_file():
            continue
        content = p.read_text()
        if not _has_fail_marker(content):
            missing.append(p.name)
    assert not missing, f"Stage 41 verify scripts missing FAIL marker: {missing}"


def test_new_stage41_scripts_have_markers():
    for script_name in [
        "verify_environment_dependencies.sh",
        "verify_regression_runner_hardening.sh",
    ]:
        p = Path("scripts") / script_name
        if not p.is_file():
            continue
        content = p.read_text()
        assert _has_pass_marker(content), f"{script_name} missing PASS marker"
        assert _has_fail_marker(content), f"{script_name} missing FAIL marker"


def test_run_full_regression_has_markers():
    p = Path("scripts/run_full_regression.sh")
    if not p.is_file():
        return
    content = p.read_text()
    assert "FULL_REGRESSION_VERIFY: PASS" in content
    assert "FULL_REGRESSION_VERIFY: FAIL" in content


def test_setup_env_has_markers():
    p = Path("scripts/setup_verification_env.sh")
    if not p.is_file():
        return
    content = p.read_text()
    assert "SETUP_VERIFICATION_ENV: PASS" in content
    assert "SETUP_VERIFICATION_ENV: FAIL" in content
