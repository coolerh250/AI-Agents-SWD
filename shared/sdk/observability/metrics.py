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
