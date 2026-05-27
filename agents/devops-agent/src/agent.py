import contextlib
import json
import os

import asyncpg

from shared.sdk.base_agent.stream_agent import StreamAgent
from shared.sdk.http_clients.github_http_client import GitHubAutomationHttpClient
from shared.sdk.observability.metrics import (
    GITHUB_PIPELINE_INTEGRATION_FAILURES_TOTAL,
    GITHUB_PIPELINE_INTEGRATION_TOTAL,
)
from shared.sdk.observability.tracing import start_span

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres@localhost:5432/aiagents")
GITHUB_DEFAULT_REPO = os.environ.get("GITHUB_DEFAULT_REPO", "coolerh250/AI-Agents-SWD")
GITHUB_INTEGRATION_DEFAULT = (
    os.environ.get("GITHUB_INTEGRATION_DEFAULT", "true").strip().lower() != "false"
)
GITHUB_DRY_RUN_DEFAULT = os.environ.get("GITHUB_DRY_RUN", "true").strip().lower() != "false"


def _dry_run_label(value: bool) -> str:
    return "true" if value else "false"


def _resolve_github_config(payload: dict, task_id: str) -> dict:
    """Pull the github automation directive off ``payload.request.github``.

    Returns a dict with: enabled / dry_run / repo / base_branch / branch_name /
    file_path / disabled_reason. Defaults stay dry-run-safe — if the caller
    didn't ask, the agent still attempts a dry-run PR so the pipeline keeps
    its full surface, but a real-mode flip requires an explicit
    ``request.github.dry_run = false`` *and* an in-cluster
    ``GITHUB_TOKEN`` (which the SDK enforces).
    """
    request = payload.get("request") if isinstance(payload.get("request"), dict) else {}
    raw = request.get("github") if isinstance(request, dict) else {}
    if not isinstance(raw, dict):
        raw = {}

    enabled_value = raw.get("enabled", GITHUB_INTEGRATION_DEFAULT)
    if isinstance(enabled_value, str):
        enabled = enabled_value.strip().lower() != "false"
    else:
        enabled = bool(enabled_value)

    dry_run_value = raw.get("dry_run", GITHUB_DRY_RUN_DEFAULT)
    if isinstance(dry_run_value, str):
        dry_run = dry_run_value.strip().lower() != "false"
    else:
        dry_run = bool(dry_run_value)

    return {
        "enabled": enabled,
        "dry_run": dry_run,
        "repo": str(raw.get("repo") or GITHUB_DEFAULT_REPO),
        "base_branch": str(raw.get("base_branch") or "main"),
        "branch_name": str(raw.get("branch_name") or f"ai-agents/{task_id}"),
        "file_path": str(raw.get("file_path") or "docs/automation-demo.md"),
        "disabled_reason": str(raw.get("disabled_reason") or ""),
    }


def _file_content(task_id: str, workflow_id: str) -> str:
    return (
        "# AI Agents SWD automated demo\n\n"
        f"- task_id: {task_id}\n"
        f"- workflow_id: {workflow_id}\n"
        "- generated_by: devops-agent\n"
        "- production_executed: false\n"
        "- mock: true\n"
    )


def _disabled_result(reason: str, dry_run: bool, branch_name: str) -> dict:
    return {
        "status": "disabled",
        "dry_run": dry_run,
        "issue_url": "",
        "branch": branch_name,
        "pr_url": "",
        "checks_status": "unknown",
        "event_type": "github.pr.skipped",
        "disabled_reason": reason or "request.github.enabled=false",
    }


class DevOpsAgent(StreamAgent):
    """Consumes test reports from stream.deployments and produces a mock
    deployment record. It writes a dev/test deployment row to deployment_records,
    publishes a devops.deployment_simulated event to stream.devops for the
    orchestrator, and records an agent execution, an audit event, and a
    notification.

    After the deployment record lands, the agent ALSO calls
    ``github-automation /github/workflow/demo-pr`` (dry-run by default) so the
    workflow timeline can expose a PR URL. The github automation outcome is
    written into ``deployment_records.metadata.github`` and surfaced in the
    devops.deployment_simulated event so the orchestrator can backfill
    ``workflow_states.execution_result.github``.

    Mock-safe: it never deploys to production and makes no Kubernetes / cloud
    calls. The default GitHub path is dry-run; a real-mode flip needs both
    an explicit ``request.github.dry_run=false`` and ``GITHUB_TOKEN`` inside
    the github-automation container.
    """

    name = "devops-agent"
    input_stream = "stream.deployments"
    output_stream = "stream.devops"
    group = "devops-agent-group"
    consumer = "devops-agent-1"

    def __init__(self, github_client: GitHubAutomationHttpClient | None = None, **kwargs):
        super().__init__(**kwargs)
        self._github_client = github_client

    def _client(self) -> GitHubAutomationHttpClient:
        if self._github_client is None:
            self._github_client = GitHubAutomationHttpClient()
        return self._github_client

    def build_deployment_record(self, payload: dict) -> dict:
        """Produce a mock dev/test deployment record (no production deploy)."""
        task_id = str(payload.get("task_id", "unknown"))
        return {
            "artifact_type": "deployment_record",
            "task_id": task_id,
            "workflow_id": payload.get("workflow_id", ""),
            "environment": "test",
            "status": "simulated",
            "production_executed": False,
            "produced_by": self.name,
            "mock": True,
        }

    async def _persist_deployment_record(self, record: dict) -> str | None:
        """Best-effort write of a mock deployment record; returns its row id."""
        with start_span(
            "deployment_records.insert",
            **{
                "db.table": "deployment_records",
                "task_id": record.get("task_id", ""),
                "workflow_id": record.get("workflow_id", ""),
                "environment": record.get("environment", ""),
            },
        ):
            try:
                conn = await asyncpg.connect(dsn=DATABASE_URL, timeout=5)
            except Exception:
                return None
            try:
                row = await conn.fetchrow(
                    "INSERT INTO deployment_records (task_id, environment, status, metadata) "
                    "VALUES ($1, $2, $3, $4::jsonb) RETURNING id",
                    record["task_id"],
                    record["environment"],
                    record["status"],
                    json.dumps(record),
                )
                return str(row["id"]) if row else None
            except Exception:
                return None
            finally:
                await conn.close()

    async def _run_github_automation(self, payload: dict, record: dict) -> dict:
        """Call github-automation /demo-pr. Safe-fail; never raises."""
        task_id = record["task_id"]
        workflow_id = str(record.get("workflow_id") or "")
        config = _resolve_github_config(payload, task_id)
        branch_name = config["branch_name"]

        if not config["enabled"]:
            GITHUB_PIPELINE_INTEGRATION_FAILURES_TOTAL.labels(reason="disabled").inc()
            return _disabled_result(config["disabled_reason"], config["dry_run"], branch_name)

        body = {
            "task_id": task_id,
            "workflow_id": workflow_id,
            "repo": config["repo"],
            "base_branch": config["base_branch"],
            "branch_name": branch_name,
            "title": f"[AI-Agents-SWD] Automated demo PR for {task_id}",
            "body_summary": (
                f"Automated demo PR generated by devops-agent for workflow {workflow_id}."
            ),
            "file_path": config["file_path"],
            "file_content": _file_content(task_id, workflow_id),
            "risk_assessment": (
                "Low — dry-run path; contacts no real GitHub API; " "production_executed=false."
            ),
            "test_result": ("devops-agent simulated test deployment + github-automation dry-run."),
            "rollback_plan": (
                "Dry-run: no rollback required. Real run: close PR + delete head branch."
            ),
            "dry_run": config["dry_run"],
        }

        with start_span(
            "devops.github_automation",
            **{
                "service.name": self.name,
                "agent": self.name,
                "github.repo": config["repo"],
                "github.dry_run": _dry_run_label(config["dry_run"]),
                "task_id": task_id,
                "workflow_id": workflow_id,
            },
        ) as span:
            result = await self._client().run_demo_pr(
                body, task_id=task_id, workflow_id=workflow_id
            )
            with contextlib.suppress(Exception):
                if hasattr(span, "set_attribute") and result.get("pr_url"):
                    span.set_attribute("github.pr_url", str(result["pr_url"]))

        label = _dry_run_label(bool(result.get("dry_run", config["dry_run"])))
        if result.get("status") == "success":
            GITHUB_PIPELINE_INTEGRATION_TOTAL.labels(dry_run=label).inc()
        else:
            GITHUB_PIPELINE_INTEGRATION_FAILURES_TOTAL.labels(reason="http_error").inc()
        return result

    async def handle(self, payload: dict) -> dict:
        record = self.build_deployment_record(payload)
        task_id = record["task_id"]
        deployment_record_id = await self._persist_deployment_record(record)
        record["deployment_record_id"] = deployment_record_id

        github_result = await self._run_github_automation(payload, record)
        record["github"] = github_result

        message = {
            "event": "devops.deployment_simulated",
            **self.correlation_ids(payload),
            "deployment_record_id": deployment_record_id,
            "artifact": record,
            "github": github_result,
            "produced_by": self.name,
        }
        await self.publish_next(message)

        decision_type = (
            "github_pr_integration"
            if github_result.get("status") in ("success", "failed")
            else "deployment"
        )
        result_label = (
            "success"
            if github_result.get("status") == "success"
            else ("failed" if github_result.get("status") == "failed" else "deployment.simulated")
        )
        github_event = github_result.get(
            "event_type",
            "github.pr.dry_run" if github_result.get("dry_run") else "github.pr.created",
        )
        return {
            "task_id": task_id,
            "decision_type": decision_type,
            "summary": (
                f"devops-agent simulated a test deployment + github-automation "
                f"({github_result.get('status', 'unknown')}) for {task_id}"
            ),
            "result": result_label,
            "artifact_refs": {
                "environment": "test",
                "production_executed": False,
                "deployment_record_id": deployment_record_id,
                "pr_url": github_result.get("pr_url", ""),
                "branch": github_result.get("branch", ""),
                "issue_url": github_result.get("issue_url", ""),
                "dry_run": bool(github_result.get("dry_run", True)),
            },
            "event_type": github_event,
            "message": (
                f"devops-agent simulated a test deployment for {task_id}; "
                f"github status={github_result.get('status', 'unknown')}"
            ),
            "execution_metadata": record,
        }
