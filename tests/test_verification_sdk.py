"""Stage 41 -- verification SDK (audit events, classifier) correctness."""

from shared.sdk.verification.audit_events import (
    DECISION_FULL_REGRESSION_FAILED,
    DECISION_FULL_REGRESSION_PASS_WITH_GAPS,
    DECISION_FULL_REGRESSION_PASSED,
    DECISION_FULL_REGRESSION_STARTED,
    DECISION_HOST_DEPENDENCY_CAVEAT_CLOSED,
    DECISION_VERIFICATION_DEPENDENCY_MISSING,
    DECISION_VERIFICATION_DEPENDENCY_READY,
    DECISION_VERIFICATION_ENVIRONMENT_CHECKED,
    EVENT_FULL_REGRESSION_FAILED,
    EVENT_FULL_REGRESSION_PASS_WITH_GAPS,
    EVENT_FULL_REGRESSION_PASSED,
    EVENT_VERIFICATION_ENVIRONMENT_FAILED,
    EVENT_VERIFICATION_ENVIRONMENT_READY,
)
from shared.sdk.verification.classifier import classify_regression_result, is_allowed_result


def test_audit_decision_constants_non_empty():
    for const in [
        DECISION_VERIFICATION_ENVIRONMENT_CHECKED,
        DECISION_VERIFICATION_DEPENDENCY_MISSING,
        DECISION_VERIFICATION_DEPENDENCY_READY,
        DECISION_FULL_REGRESSION_STARTED,
        DECISION_FULL_REGRESSION_PASSED,
        DECISION_FULL_REGRESSION_FAILED,
        DECISION_FULL_REGRESSION_PASS_WITH_GAPS,
        DECISION_HOST_DEPENDENCY_CAVEAT_CLOSED,
    ]:
        assert isinstance(const, str) and const, f"constant must be a non-empty string: {const!r}"


def test_notification_event_constants_start_with_verification():
    for event in [
        EVENT_VERIFICATION_ENVIRONMENT_READY,
        EVENT_VERIFICATION_ENVIRONMENT_FAILED,
        EVENT_FULL_REGRESSION_PASSED,
        EVENT_FULL_REGRESSION_FAILED,
        EVENT_FULL_REGRESSION_PASS_WITH_GAPS,
    ]:
        assert event.startswith("verification."), (
            f"notification event must start with 'verification.': {event!r}"
        )


def test_classify_pass():
    assert (
        classify_regression_result(
            script="scripts/x.sh", exit_code=0, output="X_VERIFY: PASS\n"
        )
        == "pass"
    )


def test_classify_env_failure():
    assert (
        classify_regression_result(
            script="scripts/x.sh",
            exit_code=1,
            output="ModuleNotFoundError: No module named 'asyncpg'\n",
        )
        == "environment_failure"
    )


def test_classify_skipped_pass():
    assert (
        classify_regression_result(
            script="scripts/x.sh",
            exit_code=0,
            output="X_VERIFY: SKIPPED-PASS (no LLM key)\n",
        )
        == "skipped_pass"
    )


def test_is_allowed_result_pass():
    assert is_allowed_result("pass") is True


def test_is_allowed_result_env_failure():
    assert is_allowed_result("environment_failure") is False


def test_is_allowed_result_safety_failure():
    assert is_allowed_result("safety_failure") is False
