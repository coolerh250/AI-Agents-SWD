PIPELINE_AGENTS = [
    "intake-agent",
    "requirement-agent",
    "development-agent",
    "qa-agent",
    "devops-agent",
]


def _execution_status(stage: str, completed: list[str], failed: list[str]) -> str:
    """Map a workflow stage and agent progress to a single execution status.

    One of: waiting_approval, dispatched, in_progress, completed, failed.
    """
    if stage == "waiting_approval":
        return "waiting_approval"
    if stage in ("rejected", "failed") or failed:
        return "failed"
    if stage == "completed":
        return "completed"
    if completed:
        return "in_progress"
    return "dispatched"


def build_progress(workflow: dict, executions: list[dict]) -> dict:
    """Summarize a workflow's agent-pipeline progress for the progress API."""
    stage = str(workflow.get("stage") or "unknown")
    state = workflow.get("state") if isinstance(workflow.get("state"), dict) else {}
    completed = {e["agent"] for e in executions if e.get("status") == "completed"}
    failed = {e["agent"] for e in executions if e.get("status") == "failed"}
    completed_agents = [a for a in PIPELINE_AGENTS if a in completed]
    failed_agents = [a for a in PIPELINE_AGENTS if a in failed]
    pending_agents = [a for a in PIPELINE_AGENTS if a not in completed and a not in failed]
    return {
        "task_id": workflow.get("task_id"),
        "workflow_id": state.get("workflow_id", ""),
        "current_stage": stage,
        "execution_status": _execution_status(stage, completed_agents, failed_agents),
        "approval_status": workflow.get("approval_status") or "none",
        "completed_agents": completed_agents,
        "pending_agents": pending_agents,
        "failed_agents": failed_agents,
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
