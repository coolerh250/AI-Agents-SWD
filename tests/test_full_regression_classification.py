"""Stage 41 -- regression result classification logic."""

import pytest

from shared.sdk.verification.classifier import (
    ALLOWED_GAPS_SCRIPTS,
    classify_regression_result,
    is_allowed_result,
)


@pytest.mark.parametrize(
    "output,exit_code,expected",
    [
        ("SOME_VERIFY: PASS\n", 0, "pass"),
        ("SOME_VERIFY: FAIL\n", 1, "unknown_failure"),
        ("SOME_VERIFY: SKIPPED-PASS\n", 0, "skipped_pass"),
        ("SOME_VERIFY: PASS_WITH_GAPS\n", 0, "pass_with_gaps"),
        ("ModuleNotFoundError: No module named 'asyncpg'\n", 1, "environment_failure"),
        ("No module named 'asyncpg'\n", 1, "environment_failure"),
        ("_VERIFY: FAIL (production_safety)\n", 1, "safety_failure"),
        ("_VERIFY: FAIL (tamper_evident)\n", 1, "regression_failure"),
        ("_VERIFY: FAIL (direct_post)\n", 1, "regression_failure"),
        ("_VERIFY: FAIL (audit_integrity)\n", 1, "regression_failure"),
    ],
)
def test_classify_regression_result(output: str, exit_code: int, expected: str):
    result = classify_regression_result(
        script="scripts/verify_something.sh",
        exit_code=exit_code,
        output=output,
        allowed_gap=True,
    )
    assert result == expected, f"expected {expected!r}, got {result!r}"


def test_pass_with_gaps_allowed_for_backup_script():
    result = classify_regression_result(
        script="scripts/verify_backup_production_readiness.sh",
        exit_code=0,
        output="BACKUP_VERIFY: PASS_WITH_GAPS\n",
        allowed_gap=True,
    )
    assert result == "pass_with_gaps"


def test_pass_with_gaps_not_allowed_for_other_script():
    result = classify_regression_result(
        script="scripts/verify_other.sh",
        exit_code=0,
        output="OTHER_VERIFY: PASS_WITH_GAPS\n",
        allowed_gap=False,
    )
    assert result == "fail"


@pytest.mark.parametrize(
    "result_class,script,expected",
    [
        ("pass", "", True),
        ("skipped_pass", "", True),
        ("pass_with_documented_gaps", "", True),
        ("pass_with_gaps", "scripts/verify_backup_production_readiness.sh", True),
        ("pass_with_gaps", "scripts/verify_other.sh", False),
        ("fail", "", False),
        ("environment_failure", "", False),
        ("safety_failure", "", False),
        ("regression_failure", "", False),
        ("unknown_failure", "", False),
    ],
)
def test_is_allowed_result(result_class: str, script: str, expected: bool):
    assert is_allowed_result(result_class, script=script) == expected


def test_module_not_found_classified_as_env_failure():
    result = classify_regression_result(
        script="scripts/verify_audit_integrity_remediation.sh",
        exit_code=1,
        output="Traceback (most recent call last):\nModuleNotFoundError: No module named 'asyncpg'\n",
        allowed_gap=False,
    )
    assert result == "environment_failure"


def test_allowed_gaps_scripts_contains_backup():
    assert "scripts/verify_backup_production_readiness.sh" in ALLOWED_GAPS_SCRIPTS
