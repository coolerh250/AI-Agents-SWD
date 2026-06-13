"""Stage 41 -- regression result classification logic.

Used by run_full_regression.sh (via shell logic) and tested independently.
"""

from __future__ import annotations

# Allowed outcome classes for a full regression run
ALLOWED_RESULT_CLASSES = frozenset(
    {
        "pass",
        "skipped_pass",
        "pass_with_gaps",
        "pass_with_documented_gaps",
    }
)

# Scripts allowed to emit pass_with_gaps (documented allowed gaps)
ALLOWED_GAPS_SCRIPTS = frozenset(
    {
        "scripts/verify_backup_production_readiness.sh",
    }
)

# Documented gap reasons for backup readiness
DOCUMENTED_GAP_REASONS = frozenset(
    {
        "encryption_no_key",
        "storage_not_off_host",
        "schedule_dry_run_only",
        "migration_down_gaps",
    }
)


def classify_regression_result(
    *,
    script: str,
    exit_code: int,
    output: str,
    allowed_gap: bool = False,
) -> str:
    """Classify a single regression script run.

    Returns one of:
        pass, fail, skipped_pass, pass_with_gaps,
        environment_failure, regression_failure, safety_failure, unknown_failure
    """
    if "ModuleNotFoundError" in output or "No module named" in output:
        return "environment_failure"
    if any(
        tag in output
        for tag in [
            "_VERIFY: FAIL (production_safety)",
            "production_executed_true",
        ]
    ):
        return "safety_failure"
    if any(
        tag in output
        for tag in [
            "_VERIFY: FAIL (audit_integrity)",
            "_VERIFY: FAIL (tamper",
            "_VERIFY: FAIL (direct_post",
        ]
    ):
        return "regression_failure"
    if "SKIPPED-PASS" in output or "SKIPPED: PASS" in output:
        return "skipped_pass"
    if "PASS_WITH_GAPS" in output:
        if allowed_gap:
            return "pass_with_gaps"
        return "fail"
    if exit_code == 0 and "_VERIFY: PASS" in output:
        return "pass"
    if exit_code != 0:
        return "unknown_failure"
    return "pass"


def is_allowed_result(result_class: str, *, script: str = "") -> bool:
    """Return True if a result class is an allowed regression outcome."""
    if result_class in ("pass", "skipped_pass"):
        return True
    if result_class == "pass_with_gaps":
        return script in ALLOWED_GAPS_SCRIPTS or not script
    if result_class == "pass_with_documented_gaps":
        return True
    return False
