from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

# Workflow-level metrics (orchestrator)
WORKFLOW_TOTAL = Counter(
    "workflow_total",
    "Workflows dispatched, labelled by terminal status when known",
    ["status"],
)
WORKFLOW_COMPLETED_TOTAL = Counter(
    "workflow_completed_total",
    "Workflows that reached stage=completed",
)
WORKFLOW_FAILED_TOTAL = Counter(
    "workflow_failed_total",
    "Workflows that ended in a non-success terminal stage",
    ["reason"],  # canceled | aborted | rejected | failed
)
WORKFLOW_DURATION_SECONDS = Histogram(
    "workflow_duration_seconds",
    "End-to-end workflow duration (dispatch -> completed)",
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60, 120, 300),
)

# Agent-level metrics
AGENT_EXECUTION_TOTAL = Counter(
    "agent_execution_total",
    "Agent execution invocations",
    ["agent", "status"],  # status = completed | failed
)
AGENT_EXECUTION_FAILURES_TOTAL = Counter(
    "agent_execution_failures_total",
    "Agent execution failures",
    ["agent"],
)
AGENT_LATENCY_SECONDS = Histogram(
    "agent_latency_seconds",
    "Per-agent processing latency",
    ["agent"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)

# Retry / dead-letter / scheduler metrics
DEADLETTER_TOTAL = Counter(
    "deadletter_total",
    "Dead-letter publications, labelled by the original stream",
    ["original_stream"],
)
RETRY_TOTAL = Counter(
    "retry_total",
    "Retry events, labelled by kind",
    ["kind"],  # requeued | terminal_failure | manual_replay
)

# Notification metrics
NOTIFICATION_TOTAL = Counter(
    "notification_total",
    "Notifications published, labelled by event_type",
    ["event_type"],
)

# GitHub automation metrics
GITHUB_ISSUE_CREATED_TOTAL = Counter(
    "github_issue_created_total",
    "GitHub issues created (labelled by dry_run mode)",
    ["dry_run"],
)
GITHUB_BRANCH_CREATED_TOTAL = Counter(
    "github_branch_created_total",
    "GitHub branches created (labelled by dry_run mode)",
    ["dry_run"],
)
GITHUB_PR_CREATED_TOTAL = Counter(
    "github_pr_created_total",
    "GitHub pull requests created (labelled by dry_run mode)",
    ["dry_run"],
)
GITHUB_CHECKS_READ_TOTAL = Counter(
    "github_checks_read_total",
    "GitHub check-runs read (labelled by dry_run mode)",
    ["dry_run"],
)
GITHUB_AUTOMATION_FAILURES_TOTAL = Counter(
    "github_automation_failures_total",
    "Failures in the github-automation pipeline (labelled by operation)",
    ["operation"],
)
GITHUB_PIPELINE_INTEGRATION_TOTAL = Counter(
    "github_pipeline_integration_total",
    "Agent-pipeline -> github-automation integrations (labelled by dry_run mode)",
    ["dry_run"],
)
GITHUB_PIPELINE_INTEGRATION_FAILURES_TOTAL = Counter(
    "github_pipeline_integration_failures_total",
    "Agent-pipeline -> github-automation integration failures",
    ["reason"],  # http_error | safe_failure | disabled (informational)
)

# Controlled real GitHub validation metrics (Stage 23)
GITHUB_REAL_TEST_ATTEMPTS_TOTAL = Counter(
    "github_real_test_attempts_total",
    "Controlled real GitHub test attempts (labelled by repo+result)",
    ["repo", "result"],  # result: attempted (guard passed, run started)
)
GITHUB_REAL_TEST_SUCCESS_TOTAL = Counter(
    "github_real_test_success_total",
    "Controlled real GitHub tests that completed the full PR flow",
    ["repo", "result"],  # result: completed
)
GITHUB_REAL_TEST_BLOCKED_TOTAL = Counter(
    "github_real_test_blocked_total",
    "Controlled real GitHub tests refused by the safety guard",
    ["repo", "reason"],
)
GITHUB_REAL_TEST_FAILURES_TOTAL = Counter(
    "github_real_test_failures_total",
    "Controlled real GitHub tests that started but failed mid-flow",
    ["repo", "reason"],
)
GITHUB_REAL_TEST_DURATION_SECONDS = Histogram(
    "github_real_test_duration_seconds",
    "Controlled real GitHub test wall-clock duration (full PR flow)",
    ["repo", "result"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60),
)

# Audit-worker metrics (Stage 19 stream.audit -> audit_logs persistence)
AUDIT_WORKER_PROCESSED_TOTAL = Counter(
    "audit_worker_processed_total",
    "Audit events persisted into audit_logs by audit-worker",
    ["decision_type"],
)
AUDIT_WORKER_FAILURES_TOTAL = Counter(
    "audit_worker_failures_total",
    "Audit events whose persistence failed (labelled by reason)",
    ["reason"],  # normalize_error | db_error | deadletter_error
)
AUDIT_WORKER_DEADLETTERED_TOTAL = Counter(
    "audit_worker_deadlettered_total",
    "Audit events routed to stream.deadletter by audit-worker",
)
AUDIT_WORKER_SKIPPED_TOTAL = Counter(
    "audit_worker_skipped_total",
    "Audit events skipped without persisting (labelled by reason)",
    ["reason"],  # audit_recorded_echo | duplicate | empty
)
AUDIT_WORKER_PROCESSING_SECONDS = Histogram(
    "audit_worker_processing_seconds",
    "End-to-end audit-worker processing time per event",
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5),
)

# Operations Control API metrics (Stage 20 — unified read-only operator view)
OPERATIONS_REQUESTS_TOTAL = Counter(
    "operations_requests_total",
    "Operations Control API requests (labelled by endpoint and result)",
    ["endpoint", "result"],  # result = ok | error | not_found
)
OPERATIONS_REQUEST_FAILURES_TOTAL = Counter(
    "operations_request_failures_total",
    "Operations Control API failures (labelled by endpoint and reason)",
    ["endpoint", "reason"],  # reason = store_error | not_found | bad_request
)
OPERATIONS_REQUEST_DURATION_SECONDS = Histogram(
    "operations_request_duration_seconds",
    "Operations Control API per-endpoint duration",
    ["endpoint"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5),
)

# Discord Gateway sandbox metrics (Stage 21)
DISCORD_MESSAGES_RECEIVED_TOTAL = Counter(
    "discord_messages_received_total",
    "Discord-sandbox messages received by the gateway",
    ["command_type", "sandbox"],
)
DISCORD_TASKS_DISPATCHED_TOTAL = Counter(
    "discord_tasks_dispatched_total",
    "Discord-sandbox messages that produced a workflow dispatch",
    ["command_type", "result", "sandbox"],
)
DISCORD_INTAKE_FAILURES_TOTAL = Counter(
    "discord_intake_failures_total",
    "Discord-sandbox intake failures (labelled by reason)",
    ["reason"],  # parse_error | gateway_error | dispatch_error
)
DISCORD_NOTIFICATIONS_PUBLISHED_TOTAL = Counter(
    "discord_notifications_published_total",
    "Discord-sandbox notifications published to stream.notifications",
    ["event_type", "sandbox"],
)
DISCORD_REQUEST_DURATION_SECONDS = Histogram(
    "discord_request_duration_seconds",
    "Discord-gateway per-endpoint duration",
    ["endpoint"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5),
)

# Notification-worker metrics (Stage 22 — controlled Discord delivery)
NOTIFICATION_WORKER_PROCESSED_TOTAL = Counter(
    "notification_worker_processed_total",
    "Notification events consumed from stream.notifications",
    ["event_type"],
)
NOTIFICATION_WORKER_DELIVERED_TOTAL = Counter(
    "notification_worker_delivered_total",
    "Notifications dispatched as real Discord deliveries",
    ["event_type", "channel"],
)
NOTIFICATION_WORKER_SIMULATED_TOTAL = Counter(
    "notification_worker_simulated_total",
    "Notifications recorded as sandbox simulations (no external API call)",
    ["event_type", "channel"],
)
NOTIFICATION_WORKER_FAILURES_TOTAL = Counter(
    "notification_worker_failures_total",
    "Notification deliveries that failed (labelled by reason)",
    ["reason"],  # render_error | store_error | discord_error | deadletter_error
)
NOTIFICATION_WORKER_SKIPPED_TOTAL = Counter(
    "notification_worker_skipped_total",
    "Notifications skipped without delivery (labelled by reason)",
    ["reason"],  # duplicate | empty | sandbox_self_test
)
NOTIFICATION_WORKER_PROCESSING_SECONDS = Histogram(
    "notification_worker_processing_seconds",
    "End-to-end notification-worker processing time per event",
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5),
)


# Stage 27 — flexible task execution loop metrics.
TASK_WORK_ITEMS_TOTAL = Counter(
    "task_work_items_total",
    "Task work items written (one row per upsert)",
    ["execution_mode", "status"],
)
TASK_EXECUTION_MODE_TOTAL = Counter(
    "task_execution_mode_total",
    "Classifier decisions, labelled by chosen execution mode + request_type",
    ["execution_mode", "request_type"],
)
CLARIFICATION_REQUESTS_TOTAL = Counter(
    "clarification_requests_total",
    "Clarification requests by lifecycle (requested | answered)",
    ["status"],
)
TASK_READY_FOR_DEVELOPMENT_TOTAL = Counter(
    "task_ready_for_development_total",
    "Work items that reached status=ready_for_development",
    ["execution_mode"],
)
TASK_BLOCKED_TOTAL = Counter(
    "task_blocked_total",
    "Work items that were marked blocked",
    ["reason"],
)
AGENT_DISCUSSIONS_TOTAL = Counter(
    "agent_discussions_total",
    "Agent discussion rows appended",
    ["agent", "message_type"],
)


# Stage 28 — controlled code generation workspace metrics.
CODE_WORKSPACES_TOTAL = Counter(
    "code_workspaces_total",
    "Code workspaces created (one row per upsert)",
    ["execution_mode", "generator_mode", "status"],
)
CODE_GENERATION_ATTEMPTS_TOTAL = Counter(
    "code_generation_attempts_total",
    "Deterministic code generation attempts",
    ["execution_mode", "generator_mode"],
)
CODE_GENERATION_SUCCESS_TOTAL = Counter(
    "code_generation_success_total",
    "Code generation runs that produced at least one valid artifact",
    ["execution_mode", "generator_mode", "risk_level"],
)
CODE_GENERATION_BLOCKED_TOTAL = Counter(
    "code_generation_blocked_total",
    "Code generation runs blocked by policy / allowlist / classifier",
    ["reason"],
)
CODE_VALIDATION_FAILURES_TOTAL = Counter(
    "code_validation_failures_total",
    "Per-file validation failures (labelled by failure kind)",
    ["check"],  # check = allowlist | secret_content | py_compile | diff_empty | file_missing
)
PR_DRAFT_ARTIFACTS_TOTAL = Counter(
    "pr_draft_artifacts_total",
    "PR draft artifacts created",
    ["execution_mode", "status", "risk_level"],
)


# Stage 29 — QA-guided validation + deterministic auto-fix loop.
QA_VALIDATION_RUNS_TOTAL = Counter(
    "qa_validation_runs_total",
    "QA validation runs started",
    ["status"],
)
QA_VALIDATION_PASSED_TOTAL = Counter(
    "qa_validation_passed_total",
    "QA validation runs that ended with final_result=pass",
)
QA_VALIDATION_FAILED_TOTAL = Counter(
    "qa_validation_failed_total",
    "QA validation runs that ended with final_result=fail",
    ["reason"],  # auto_fix_max_attempts | blocked | validation_error
)
QA_FINDINGS_TOTAL = Counter(
    "qa_findings_total",
    "QA findings recorded",
    ["severity", "category", "auto_fixable"],
)
QA_AUTO_FIX_REQUESTS_TOTAL = Counter(
    "qa_auto_fix_requests_total",
    "Auto-fix requests filed by the qa-agent",
    ["status"],  # requested | completed | failed | max_attempts_exceeded
)
QA_BLOCKED_FOR_HUMAN_REVIEW_TOTAL = Counter(
    "qa_blocked_for_human_review_total",
    "QA runs that escalated to human review",
    ["reason"],
)
QA_AUTO_FIX_ATTEMPTS_TOTAL = Counter(
    "qa_auto_fix_attempts_total",
    "Auto-fix attempts executed by the development-agent",
    ["result"],  # completed | failed | max_attempts_exceeded
)


def metrics_response() -> tuple[bytes, str]:
    """Render the default Prometheus registry as (body, content_type)."""
    return generate_latest(), CONTENT_TYPE_LATEST


def install_metrics_endpoint(app) -> None:
    """Attach the /metrics endpoint to a FastAPI app."""
    from fastapi.responses import Response

    @app.get("/metrics")
    def _metrics():
        data, content_type = metrics_response()
        return Response(content=data, media_type=content_type)
