from datetime import datetime

PIPELINE_AGENTS = [
    "intake-agent",
    "requirement-agent",
    "development-agent",
    "qa-agent",
    "devops-agent",
]


def _duration_ms(started: str | None, completed: str | None) -> int | None:
    if not started or not completed:
        return None
    try:
        s = datetime.fromisoformat(str(started))
        c = datetime.fromisoformat(str(completed))
    except (TypeError, ValueError):
        return None
    return max(int((c - s).total_seconds() * 1000), 0)


def build_agent_timeline(executions: list[dict]) -> list[dict]:
    """Return a chronological per-agent timeline derived from agent_executions."""
    ordered = sorted(executions, key=lambda e: str(e.get("started_at") or ""))
    return [
        {
            "phase": e.get("agent"),
            "status": e.get("status"),
            "started_at": e.get("started_at"),
            "completed_at": e.get("completed_at"),
            "duration_ms": _duration_ms(e.get("started_at"), e.get("completed_at")),
        }
        for e in ordered
    ]


def build_retry_timeline(dead_letters: list[dict]) -> list[dict]:
    """Reduce raw DLQ entries to the fields a retry timeline needs."""
    timeline: list[dict] = []
    for entry in dead_letters:
        payload = entry.get("payload") if isinstance(entry, dict) else None
        if not isinstance(payload, dict):
            continue
        timeline.append(
            {
                "message_id": entry.get("id"),
                "original_stream": payload.get("original_stream") or payload.get("source_stream"),
                "retry_count": payload.get("retry_count"),
                "max_retries": payload.get("max_retries"),
                "failure_reason": payload.get("failure_reason") or payload.get("error", ""),
                "failed_at": payload.get("failed_at") or payload.get("dead_lettered_at"),
            }
        )
    timeline.sort(key=lambda entry: str(entry.get("failed_at") or ""))
    return timeline


def _execution_status(stage: str, completed: list[str], failed: list[str]) -> str:
    """Map a workflow stage and agent progress to a single execution status.

    One of: waiting_approval, dispatched, in_progress, completed, failed,
    canceled, aborted.
    """
    if stage == "waiting_approval":
        return "waiting_approval"
    if stage == "canceled":
        return "canceled"
    if stage == "aborted":
        return "aborted"
    if stage in ("rejected", "failed") or failed:
        return "failed"
    if stage == "completed":
        return "completed"
    if completed:
        return "in_progress"
    return "dispatched"


def build_github_summary(workflow: dict) -> dict | None:
    """Extract the github-automation envelope the orchestrator backfilled.

    Returns ``None`` when the workflow has no ``execution_result.github``
    block (e.g. pre-Stage-18 rows or workflows that explicitly disabled the
    integration via ``request.github.enabled=false``).
    """
    state = workflow.get("state") if isinstance(workflow.get("state"), dict) else {}
    execution_result = (
        state.get("execution_result")
        if isinstance(state.get("execution_result"), dict)
        else (
            workflow.get("execution_result")
            if isinstance(workflow.get("execution_result"), dict)
            else {}
        )
    )
    github = execution_result.get("github") if isinstance(execution_result, dict) else None
    if not isinstance(github, dict) or not github:
        return None
    return {
        "status": github.get("status", "unknown"),
        "dry_run": bool(github.get("dry_run", True)),
        "pr_url": github.get("pr_url", ""),
        "pr_number": github.get("pr_number"),
        "issue_url": github.get("issue_url", ""),
        "branch": github.get("branch", ""),
        "checks_status": github.get("checks_status", "unknown"),
        "event_type": github.get("event_type", ""),
        "error": github.get("error", ""),
    }


def _github_timeline_event(github: dict | None, updated_at: str | None) -> dict | None:
    """Render a single timeline entry for the github-automation result."""
    if not github:
        return None
    status = github.get("status", "unknown")
    dry_run = github.get("dry_run", True)
    if status == "failed":
        phase = "github.demo_pr.failed"
    elif status == "disabled":
        phase = "github.demo_pr.skipped"
    elif dry_run:
        phase = "github.demo_pr.dry_run"
    else:
        phase = "github.demo_pr.created"
    return {
        "phase": phase,
        "status": status,
        "started_at": updated_at,
        "completed_at": updated_at,
        "duration_ms": None,
        "pr_url": github.get("pr_url", ""),
        "branch": github.get("branch", ""),
        "dry_run": dry_run,
    }


def build_progress(
    workflow: dict, executions: list[dict], retry_timeline: list[dict] | None = None
) -> dict:
    """Summarize a workflow's agent-pipeline progress for the progress API.

    Adds three observability fields on top of the original progress payload:
    ``traces`` (workflow-level trace id), ``agent_timeline`` (one ordered entry
    per agent_executions row), and ``retry_timeline`` (DLQ entries observed
    for the task, when supplied).
    """
    stage = str(workflow.get("stage") or "unknown")
    state = workflow.get("state") if isinstance(workflow.get("state"), dict) else {}
    completed = {e["agent"] for e in executions if e.get("status") == "completed"}
    failed = {e["agent"] for e in executions if e.get("status") == "failed"}
    completed_agents = [a for a in PIPELINE_AGENTS if a in completed]
    failed_agents = [a for a in PIPELINE_AGENTS if a in failed]
    pending_agents = [a for a in PIPELINE_AGENTS if a not in completed and a not in failed]
    github = build_github_summary(workflow)
    agent_timeline = build_agent_timeline(executions)
    gh_event = _github_timeline_event(github, workflow.get("updated_at"))
    if gh_event is not None:
        agent_timeline.append(gh_event)
    return {
        "task_id": workflow.get("task_id"),
        "workflow_id": state.get("workflow_id", ""),
        "current_stage": stage,
        "execution_status": _execution_status(stage, completed_agents, failed_agents),
        "approval_status": workflow.get("approval_status") or "none",
        "completed_agents": completed_agents,
        "pending_agents": pending_agents,
        "failed_agents": failed_agents,
        "traces": {
            "trace_id": state.get("trace_id", ""),
            "workflow_id": state.get("workflow_id", ""),
        },
        "agent_timeline": agent_timeline,
        "retry_timeline": retry_timeline or [],
        "github": github,
        "pr_url": (github or {}).get("pr_url", ""),
        "github_status": (github or {}).get("status", "unknown") if github else "",
        "github_dry_run": (github or {}).get("dry_run", True) if github else None,
        "timestamps": {
            "created_at": workflow.get("created_at"),
            "updated_at": workflow.get("updated_at"),
            "agents": {
                e["agent"]: {
                    "started_at": e.get("started_at"),
                    "completed_at": e.get("completed_at"),
                }
                for e in executions
            },
        },
    }
