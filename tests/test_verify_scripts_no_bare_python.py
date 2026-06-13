"""Stage 41 -- verify scripts that use shared.sdk must source verify_env.sh."""

import re
from pathlib import Path


SCRIPTS_DIR = Path("scripts")

# Scripts that import from shared.sdk (asyncpg-dependent) and must source verify_env.sh.
SDK_DEPENDENT_SCRIPTS = [
    "scripts/backfill_audit_integrity.sh",
    "scripts/simulate_audit_tamper_detection.sh",
    "scripts/verify_flexible_human_approval_policy.sh",
    "scripts/verify_llm_cost_governance.sh",
    "scripts/verify_tamper_evident_audit.sh",
    "scripts/check_runtime_state.sh",
]

# Patterns that indicate shared SDK usage (asyncpg-dependent)
SDK_IMPORT_PATTERNS = [
    r"from shared\.sdk",
    r"import asyncpg",
    r"sys\.path\.insert.*shared",
]


def test_sdk_dependent_scripts_source_verify_env():
    for script_path in SDK_DEPENDENT_SCRIPTS:
        p = Path(script_path)
        if not p.is_file():
            continue
        content = p.read_text()
        assert "verify_env.sh" in content, (
            f"{script_path} uses shared.sdk but does not source verify_env.sh"
        )


def test_verify_env_lib_exists():
    assert Path("scripts/lib/verify_env.sh").is_file()


def test_backfill_uses_python_var():
    p = Path("scripts/backfill_audit_integrity.sh")
    if not p.is_file():
        return
    content = p.read_text()
    # Must use $PY or ${PYTHON:-...} not bare python3 for SDK calls
    assert 'PY="${PYTHON:-python3}"' in content or "$PYTHON" in content, (
        "backfill_audit_integrity.sh must use PYTHON variable for SDK calls"
    )


def test_simulate_tamper_uses_python_var():
    p = Path("scripts/simulate_audit_tamper_detection.sh")
    if not p.is_file():
        return
    content = p.read_text()
    assert 'PY="${PYTHON:-python3}"' in content or "$PYTHON" in content


def test_flexible_policy_uses_python_var():
    p = Path("scripts/verify_flexible_human_approval_policy.sh")
    if not p.is_file():
        return
    content = p.read_text()
    # Should NOT have bare python3 for SDK calls — must use ${PYTHON:-python3}
    sdk_calls = re.findall(r'python3\s+(-c|-).*sys\.path', content)
    bare_calls = [c for c in sdk_calls if "${PYTHON" not in c]
    assert not bare_calls, (
        f"verify_flexible_human_approval_policy.sh has bare python3 SDK calls: {bare_calls}"
    )


def test_llm_cost_governance_uses_python_var():
    p = Path("scripts/verify_llm_cost_governance.sh")
    if not p.is_file():
        return
    content = p.read_text()
    # Must use ${PYTHON:-python3} not bare python3 for SDK imports
    assert '${PYTHON:-python3}' in content, (
        "verify_llm_cost_governance.sh must use ${PYTHON:-python3}"
    )


def test_check_runtime_state_sources_verify_env():
    p = Path("scripts/check_runtime_state.sh")
    if not p.is_file():
        return
    content = p.read_text()
    assert "verify_env.sh" in content, (
        "check_runtime_state.sh must source scripts/lib/verify_env.sh"
    )


def test_run_full_regression_sources_verify_env():
    p = Path("scripts/run_full_regression.sh")
    if not p.is_file():
        return
    content = p.read_text()
    assert "verify_env.sh" in content


def test_verify_regression_runner_hardening_sources_verify_env():
    p = Path("scripts/verify_regression_runner_hardening.sh")
    if not p.is_file():
        return
    content = p.read_text()
    assert "verify_env.sh" in content
