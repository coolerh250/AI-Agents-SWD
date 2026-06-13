"""Stage 41 -- verification audit decision_type and notification event constants."""

# Audit decision types for audit_logs (decision_type column)
DECISION_VERIFICATION_ENVIRONMENT_CHECKED = "verification_environment_checked"
DECISION_VERIFICATION_DEPENDENCY_MISSING = "verification_dependency_missing"
DECISION_VERIFICATION_DEPENDENCY_READY = "verification_dependency_ready"
DECISION_FULL_REGRESSION_STARTED = "full_regression_started"
DECISION_FULL_REGRESSION_PASSED = "full_regression_passed"
DECISION_FULL_REGRESSION_FAILED = "full_regression_failed"
DECISION_FULL_REGRESSION_PASS_WITH_GAPS = "full_regression_pass_with_gaps"
DECISION_HOST_DEPENDENCY_CAVEAT_CLOSED = "host_dependency_caveat_closed"

# Notification event names — all covered by "verification.*" denylist pattern
# in DEFAULT_REAL_DELIVERY_DENYLIST; must NEVER land on a real Discord channel.
EVENT_VERIFICATION_ENVIRONMENT_READY = "verification.environment_ready"
EVENT_VERIFICATION_ENVIRONMENT_FAILED = "verification.environment_failed"
EVENT_FULL_REGRESSION_PASSED = "verification.full_regression_passed"
EVENT_FULL_REGRESSION_FAILED = "verification.full_regression_failed"
EVENT_FULL_REGRESSION_PASS_WITH_GAPS = "verification.full_regression_pass_with_gaps"
