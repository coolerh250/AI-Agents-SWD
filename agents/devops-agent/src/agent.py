import contextlib
import json
import os

import asyncpg

from shared.sdk.audit.publisher import publish_audit_event
from shared.sdk.base_agent.stream_agent import StreamAgent
from shared.sdk.code_workspace import CodeWorkspaceStore
from shared.sdk.http_clients.github_http_client import GitHubAutomationHttpClient
from shared.sdk.notifications.client import send_notification
from shared.sdk.observability.metrics import (
    AGENT_DISCUSSIONS_TOTAL,
    GITHUB_PIPELINE_INTEGRATION_FAILURES_TOTAL,
    GITHUB_PIPELINE_INTEGRATION_TOTAL,
)
from shared.sdk.observability.tracing import start_span
from shared.sdk.task_execution import TaskExecutionStore

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
        self._task_store = TaskExecutionStore()
        self._code_store = CodeWorkspaceStore()

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
        """Call github-automation /demo-pr. Safe-fail; never raises.

        Stage 28: if the development-agent left a PR draft artifact, we
        forward its title / body / risk / rollback to github-automation
        so the dry-run PR carries the controlled-generation context
        instead of the generic demo body. The file_path stays under
        ``docs/automation-demo.md`` for the demo-pr endpoint — the
        real generated files live in the workspace and are surfaced
        via ``/operations/code/*`` not via the dry-run PR body's
        ``file_content``.
        """
        task_id = record["task_id"]
        workflow_id = str(record.get("workflow_id") or "")
        config = _resolve_github_config(payload, task_id)
        branch_name = config["branch_name"]

        if not config["enabled"]:
            GITHUB_PIPELINE_INTEGRATION_FAILURES_TOTAL.labels(reason="disabled").inc()
            return _disabled_result(config["disabled_reason"], config["dry_run"], branch_name)

        # Pull the Stage 28 PR draft if the development-agent produced one.
        pr_draft = None
        try:
            pr_draft = await self._code_store.get_pr_draft_artifact(task_id)
        except Exception:
            pr_draft = None

        title = (
            pr_draft.title
            if pr_draft and pr_draft.title
            else f"[AI-Agents-SWD] Automated demo PR for {task_id}"
        )
        body_summary = (
            pr_draft.body
            if pr_draft and pr_draft.body
            else f"Automated demo PR generated by devops-agent for workflow {workflow_id}."
        )
        risk_text = "Low — dry-run path; contacts no real GitHub API; production_executed=false."
        if pr_draft and isinstance(pr_draft.risk_assessment, dict):
            risk_text = (
                f"Controlled code generation — risk_level="
                f"{pr_draft.risk_assessment.get('risk_level', 'unknown')} "
                f"(files={pr_draft.risk_assessment.get('files_count', 0)}); "
                "dry-run path; contacts no real GitHub API; production_executed=false."
            )
        rollback_text = (
            pr_draft.rollback_plan
            if pr_draft and pr_draft.rollback_plan
            else "Dry-run: no rollback required. Real run: close PR + delete head branch."
        )
        test_result_text = (
            f"controlled code generation pr_draft={pr_draft.pr_draft_id}; "
            f"validation={pr_draft.test_results.get('status', 'unknown')}."
            if pr_draft
            else "devops-agent simulated test deployment + github-automation dry-run."
        )

        body = {
            "task_id": task_id,
            "workflow_id": workflow_id,
            "repo": config["repo"],
            "base_branch": config["base_branch"],
            "branch_name": branch_name,
            "title": title,
            "body_summary": body_summary,
            "file_path": config["file_path"],
            "file_content": _file_content(task_id, workflow_id),
            "risk_assessment": risk_text,
            "test_result": test_result_text,
            "rollback_plan": rollback_text,
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

    async def _write_github_audit(self, record: dict, github_result: dict) -> None:
        """Publish a ``github_pr_integration`` audit event onto ``stream.audit``.

        Stage 19 unified audit path: the audit-worker consumes stream.audit and
        writes audit_logs, so devops-agent no longer needs the direct
        ``audit-service`` HTTP call to land the row in Postgres. We rely on the
        StreamAgent's existing ``write_audit`` call (which already publishes to
        the same stream) — but the StreamAgent audit only covers the base
        deployment decision_type, not ``github_pr_integration``. This explicit
        call adds the github-specific row.
        """
        with contextlib.suppress(Exception):
            await publish_audit_event(
                task_id=record["task_id"],
                workflow_id=str(record.get("workflow_id", "")),
                agent=self.name,
                decision_type="github_pr_integration",
                summary=(
                    f"github-automation {github_result.get('status', 'unknown')} "
                    f"(dry_run={github_result.get('dry_run', True)}) for {record['task_id']}"
                ),
                result=str(github_result.get("status", "unknown")),
                artifact_refs={
                    "pr_url": github_result.get("pr_url", ""),
                    "branch": github_result.get("branch", ""),
                    "issue_url": github_result.get("issue_url", ""),
                    "dry_run": bool(github_result.get("dry_run", True)),
                },
            )

    async def handle(self, payload: dict) -> dict:
        record = self.build_deployment_record(payload)
        task_id = record["task_id"]
        deployment_record_id = await self._persist_deployment_record(record)
        record["deployment_record_id"] = deployment_record_id

        github_result = await self._run_github_automation(payload, record)
        record["github"] = github_result

        # Persist github_pr_integration audit row in addition to the
        # StreamAgent's stream-based audit so the audit-service DB carries it.
        await self._write_github_audit(record, github_result)

        # Stage 28 — if there's a PR draft, write the dry-run PR result
        # back so /operations/code/pr-drafts/{task_id} surfaces the
        # github metadata too.
        try:
            existing_draft = await self._code_store.get_pr_draft_artifact(task_id)
            if existing_draft is not None:
                await self._code_store.create_pr_draft_artifact(
                    task_id=task_id,
                    workflow_id=existing_draft.workflow_id,
                    workspace_id=existing_draft.workspace_id,
                    title=existing_draft.title,
                    body=existing_draft.body,
                    changed_files=existing_draft.changed_files,
                    test_results=existing_draft.test_results,
                    risk_assessment=existing_draft.risk_assessment,
                    rollback_plan=existing_draft.rollback_plan,
                    github_dry_run_result={
                        "dry_run": bool(github_result.get("dry_run", True)),
                        "status": github_result.get("status", "unknown"),
                        "pr_url": github_result.get("pr_url", ""),
                        "branch": github_result.get("branch", ""),
                        "issue_url": github_result.get("issue_url", ""),
                        "checks_status": github_result.get("checks_status", ""),
                        "event_type": github_result.get("event_type", ""),
                        "production_executed": False,
                    },
                    status=existing_draft.status,
                )
                with contextlib.suppress(Exception):
                    await send_notification(
                        task_id,
                        "code.pr_draft_ready",
                        (
                            f"github dry-run delivered for {task_id} "
                            f"(pr_url={github_result.get('pr_url', '') or 'n/a'})"
                        ),
                    )
        except Exception:
            pass

        message = {
            "event": "devops.deployment_simulated",
            **self.correlation_ids(payload),
            "deployment_record_id": deployment_record_id,
            "artifact": record,
            "github": github_result,
            "produced_by": self.name,
        }
        await self.publish_next(message)
        workflow_id = str(payload.get("workflow_id", "")) or None
        try:
            await self._task_store.add_agent_discussion(
                task_id=task_id,
                workflow_id=workflow_id,
                agent=self.name,
                role="devops",
                message_type="risk",
                content=(
                    f"devops-agent simulated a dev/test deployment for {task_id} "
                    f"(github status={github_result.get('status', 'unknown')}, "
                    "production_executed=false)."
                ),
                confidence=0.7,
                references={
                    "environment": "test",
                    "production_executed": False,
                    "github_status": github_result.get("status", "unknown"),
                },
            )
            AGENT_DISCUSSIONS_TOTAL.labels(agent=self.name, message_type="risk").inc()
        except Exception:
            pass

        # Stage 27 — mark the work item completed when development pipeline
        # finishes (mock). Failures are swallowed so the workflow keeps moving.
        try:
            await self._task_store.update_work_item_status(task_id, "completed")
        except Exception:
            pass

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
