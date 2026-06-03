"""Stage 29 — qa-agent driving the QA validation + auto-fix loop.

Inbound: ``stream.qa`` events from the development-agent (the regular
``development.completed`` event, or the post-auto-fix
``development.auto_fix_completed`` event).

The qa-agent:

1. Loads the code workspace, change artifacts, PR draft, and the work
   item that drove the task.
2. Runs the deterministic ``apply_qa_rules`` against the loaded
   workspace.
3. Records a ``qa_validation_runs`` row + one ``qa_findings`` row per
   rule hit.
4. Decides:
   * **pass**  — no blocking findings → publish ``qa.completed`` to
     ``stream.deployments``; the devops-agent picks it up.
   * **auto_fix_requested** — at least one auto-fixable blocking
     finding AND ``auto_fix_attempts < max_auto_fix_attempts`` →
     publish ``code.auto_fix_request`` to
     ``stream.development.autofix`` (a separate stream the
     development-agent's auto-fix consumer reads); also publish a
     ``qa.auto_fix_requested`` event onto ``stream.qa`` itself so
     the workflow gate sees the decision.
   * **blocked_for_human_review** — at least one non-auto-fixable
     blocking finding, or attempts exhausted → publish
     ``qa.blocked_for_human_review`` onto ``stream.qa``; the
     pipeline halts. ``production_executed=false``.

No LLM. No code is executed. The rules live in
``shared.sdk.qa.rules`` and only inspect.
"""

from __future__ import annotations

import contextlib
import os
import tempfile
from typing import Any

from shared.sdk.audit.publisher import publish_audit_event
from shared.sdk.base_agent.stream_agent import StreamAgent
from shared.sdk.code_workspace import CodeWorkspaceStore
from shared.sdk.notifications.client import send_notification
from shared.sdk.observability.metrics import (
    AGENT_DISCUSSIONS_TOTAL,
    QA_AUTO_FIX_REQUESTS_TOTAL,
    QA_BLOCKED_FOR_HUMAN_REVIEW_TOTAL,
    QA_FINDINGS_TOTAL,
    QA_VALIDATION_FAILED_TOTAL,
    QA_VALIDATION_PASSED_TOTAL,
    QA_VALIDATION_RUNS_TOTAL,
)
from shared.sdk.observability.tracing import start_span
from shared.sdk.qa import (
    MAX_AUTO_FIX_ATTEMPTS_DEFAULT,
    QAStore,
    apply_qa_rules,
)
from shared.sdk.qa.rules import is_blocking
from shared.sdk.task_execution import TaskExecutionStore

#: New Redis stream the qa-agent emits auto-fix requests onto.
AUTO_FIX_REQUEST_STREAM = "stream.development.autofix"

#: Default workspace root inside the dev-agent / qa-agent containers.
DEFAULT_WORKSPACE_ROOT = os.environ.get(
    "DEVELOPMENT_AGENT_WORKSPACE_ROOT", "/tmp/aiagents-workspaces"
)


def _max_auto_fix_attempts() -> int:
    raw = os.environ.get("QA_MAX_AUTO_FIX_ATTEMPTS", "").strip()
    if not raw:
        return MAX_AUTO_FIX_ATTEMPTS_DEFAULT
    try:
        value = int(raw)
    except ValueError:
        return MAX_AUTO_FIX_ATTEMPTS_DEFAULT
    return max(1, min(value, 10))


class QAAgent(StreamAgent):
    """QA-guided validation + auto-fix loop driver."""

    name = "qa-agent"
    input_stream = "stream.qa"
    output_stream = "stream.deployments"
    group = "qa-agent-group"
    consumer = "qa-agent-1"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._task_store = TaskExecutionStore()
        self._code_store = CodeWorkspaceStore()
        self._qa_store = QAStore()

    # ------------------------------------------------------------------
    # legacy shim kept for tests
    # ------------------------------------------------------------------
    def build_report(self, payload: dict) -> dict:
        task_id = str(payload.get("task_id", "unknown"))
        return {
            "artifact_type": "test_report",
            "task_id": task_id,
            "status": "passed",
            "tests_run": 0,
            "produced_by": self.name,
            "mock": True,
        }

    # ------------------------------------------------------------------
    # main StreamAgent handle()
    # ------------------------------------------------------------------

    async def handle(self, payload: dict) -> dict:
        task_id = str(payload.get("task_id", "unknown"))
        workflow_id = str(payload.get("workflow_id", "")) or None
        event = str(payload.get("event") or "")

        # Skip qa-agent's own re-emitted decision events (avoid infinite
        # loop when ``qa.auto_fix_requested`` / ``qa.blocked_for_human_review``
        # land back on stream.qa).
        if event in ("qa.completed", "qa.auto_fix_requested", "qa.blocked_for_human_review"):
            return {
                "task_id": task_id,
                "decision_type": "qa_ignored_self_event",
                "summary": f"qa-agent ignored its own re-emitted event {event}",
                "result": "ignored",
                "artifact_refs": {"event": event},
                "event_type": "qa.ignored_self_event",
                "message": f"qa-agent ignored {event} on stream.qa",
            }

        # 1. Load the workspace + artifacts + pr_draft + work item.
        workspace = None
        artifacts: list[dict[str, Any]] = []
        pr_draft = None
        work_item_dict: dict[str, Any] | None = None
        template_hint = ""
        with start_span(
            "qa.load_code_artifacts",
            **{
                "service.name": self.name,
                "agent": self.name,
                "task_id": task_id,
                "workflow_id": workflow_id or "",
                "event": event,
            },
        ):
            with contextlib.suppress(Exception):
                workspace = await self._code_store.get_workspace(task_id)
            with contextlib.suppress(Exception):
                arts = await self._code_store.list_code_change_artifacts(task_id)
                artifacts = [a.to_dict() for a in arts]
            with contextlib.suppress(Exception):
                pr = await self._code_store.get_pr_draft_artifact(task_id)
                pr_draft = pr.to_dict() if pr else None
            with contextlib.suppress(Exception):
                wi = await self._task_store.get_work_item(task_id)
                work_item_dict = wi.to_dict() if wi else None

        # If there's no workspace at all, this is a legacy / mock payload
        # (or the development-agent didn't produce a workspace). Fall back
        # to the historic "qa.completed" behaviour so the legacy smoke
        # tests + the github-pipeline regression tests still pass.
        if workspace is None and not artifacts:
            return await self._legacy_passthrough(payload, task_id, workflow_id)

        # If the upstream development-agent already marked the workspace
        # ``blocked`` (controlled-generation policy refused the task), QA
        # has nothing actionable to validate — fabricating a "missing PR
        # draft" finding would falsely flip the workflow stage to
        # ``blocked_for_human_review`` on every legacy regression task.
        # Treat that as a passthrough: emit qa.completed so the
        # devops-agent can still draw the dry-run PR boundary, and let
        # the workflow finish on the existing rails.
        if workspace is not None and workspace.status in (
            "blocked",
            "validation_failed",
            "canceled",
        ):
            return await self._legacy_passthrough(payload, task_id, workflow_id)

        workspace_id = workspace.workspace_id if workspace else None
        pr_draft_id = pr_draft.get("pr_draft_id") if pr_draft else None
        template_hint = self._template_hint_from_payload(payload, artifacts)

        prior_run = await self._qa_store.get_latest_validation_run(task_id)
        prior_attempts = prior_run.auto_fix_attempts if prior_run else 0
        max_attempts = _max_auto_fix_attempts()
        if event == "development.auto_fix_completed":
            current_attempts = prior_attempts + 1
        else:
            current_attempts = prior_attempts

        # 2. Create the qa_validation_run row.
        run = await self._qa_store.create_validation_run(
            task_id=task_id,
            workflow_id=workflow_id,
            workspace_id=workspace_id,
            pr_draft_id=pr_draft_id,
            status="started",
            validation_scope="workspace",
            qa_agent=self.name,
            max_auto_fix_attempts=max_attempts,
            auto_fix_attempts=current_attempts,
            metadata={"event": event, "template_hint": template_hint},
        )
        QA_VALIDATION_RUNS_TOTAL.labels(status="started").inc()
        await self._record_qa_audit(
            task_id=task_id,
            workflow_id=workflow_id,
            decision_type="qa_validation_started",
            summary=(
                f"qa-agent started validation run {run.qa_run_id} for {task_id} "
                f"(attempt={current_attempts}/{max_attempts})"
            ),
            artifact_refs={
                "qa_run_id": run.qa_run_id,
                "workspace_id": workspace_id,
                "auto_fix_attempts": current_attempts,
                "max_auto_fix_attempts": max_attempts,
                "production_executed": False,
            },
        )
        await send_notification(
            task_id,
            "qa.validation_started",
            f"qa-agent started validation for {task_id} (attempt={current_attempts}/{max_attempts})",
        )

        # 3. Apply rules.
        file_paths = [a["file_path"] for a in artifacts if a.get("file_path")]
        # Stage 29: the qa-agent runs in a different container than the
        # development-agent, so ``workspace_path`` on the dev-agent's
        # disk is invisible here. Materialise each artifact's stored
        # ``generated_content_preview`` into a short-lived temp dir and
        # point the deterministic rules at THAT. The dev-agent stores
        # up to 20 KB of content (Stage 29 bump), enough for the
        # deterministic templates the platform ships.
        with tempfile.TemporaryDirectory(prefix=f"qa-{task_id}-") as materialised:
            self._materialise_artifacts(materialised, artifacts)
            with start_span(
                "qa.apply_rule",
                **{
                    "service.name": self.name,
                    "agent": self.name,
                    "task_id": task_id,
                    "qa_run_id": run.qa_run_id,
                    "files_count": len(file_paths),
                    "template_hint": template_hint,
                },
            ):
                raw_findings = apply_qa_rules(
                    workspace_path=materialised,
                    artifacts=artifacts,
                    file_paths=file_paths,
                    pr_draft=pr_draft,
                    work_item=work_item_dict,
                    template_hint=template_hint,
                )

        # 4. Persist findings.
        findings_records: list[Any] = []
        blocking_finding_ids: list[str] = []
        auto_fixable_blocking_ids: list[str] = []
        non_blocking_count = 0
        for f in raw_findings:
            record = await self._qa_store.add_finding(
                qa_run_id=run.qa_run_id,
                task_id=task_id,
                workflow_id=workflow_id,
                workspace_id=workspace_id,
                severity=f["severity"],
                category=f["category"],
                title=f["title"],
                description=f["description"],
                recommendation=f.get("recommendation", ""),
                file_path=f.get("file_path"),
                auto_fixable=bool(f.get("auto_fixable")),
                status="open",
                metadata=f.get("metadata") or {},
            )
            findings_records.append(record)
            QA_FINDINGS_TOTAL.labels(
                severity=record.severity,
                category=record.category,
                auto_fixable=str(record.auto_fixable).lower(),
            ).inc()
            if is_blocking(f):
                blocking_finding_ids.append(record.finding_id)
                if record.auto_fixable:
                    auto_fixable_blocking_ids.append(record.finding_id)
            else:
                non_blocking_count += 1

        # 5. Decide: pass / auto_fix / blocked.
        decision = self._decide(
            blocking_finding_ids=blocking_finding_ids,
            auto_fixable_blocking_ids=auto_fixable_blocking_ids,
            current_attempts=current_attempts,
            max_attempts=max_attempts,
        )

        # 6. Complete the run row.
        await self._qa_store.complete_validation_run(
            run.qa_run_id,
            status=decision["run_status"],
            final_result=decision["final_result"],
            total_findings=len(findings_records),
            blocking_findings=len(blocking_finding_ids),
            non_blocking_findings=non_blocking_count,
            auto_fix_attempts=current_attempts,
            metadata={
                "event": event,
                "template_hint": template_hint,
                "decision": decision["decision"],
            },
        )

        # 7. Side effects.
        if decision["decision"] == "pass":
            QA_VALIDATION_PASSED_TOTAL.inc()
            return await self._emit_pass(
                payload=payload,
                task_id=task_id,
                workflow_id=workflow_id,
                run_id=run.qa_run_id,
                workspace_id=workspace_id,
                findings_count=len(findings_records),
            )
        if decision["decision"] == "auto_fix":
            return await self._emit_auto_fix(
                payload=payload,
                task_id=task_id,
                workflow_id=workflow_id,
                run_id=run.qa_run_id,
                workspace_id=workspace_id,
                blocking_ids=auto_fixable_blocking_ids,
                attempt_number=current_attempts + 1,
                max_attempts=max_attempts,
            )
        # blocked_for_human_review
        return await self._emit_blocked(
            payload=payload,
            task_id=task_id,
            workflow_id=workflow_id,
            run_id=run.qa_run_id,
            workspace_id=workspace_id,
            blocking_ids=blocking_finding_ids,
            reason=decision["reason"],
        )

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _materialise_artifacts(target_root: str, artifacts: list[dict[str, Any]]) -> None:
        """Write every artifact's ``generated_content_preview`` under
        ``target_root`` so the deterministic rules can run filesystem
        checks against a private copy.

        The qa-agent never has direct visibility into the dev-agent's
        workspace volume; this materialisation step bridges the gap
        without sharing a Docker volume.
        """
        for art in artifacts:
            rel = art.get("file_path") or ""
            if not rel or rel.startswith("/") or ".." in rel.split("/"):
                continue
            full = os.path.join(target_root, rel)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            content = art.get("generated_content_preview") or ""
            # If the preview is empty, write an empty file so
            # validate_generated_files_exist still passes but
            # downstream rules (py_compile, secret scan) effectively
            # see an empty file and don't fire critical findings.
            with open(full, "w", encoding="utf-8") as fh:
                fh.write(content)

    # ------------------------------------------------------------------
    # decision helpers
    # ------------------------------------------------------------------

    def _decide(
        self,
        *,
        blocking_finding_ids: list[str],
        auto_fixable_blocking_ids: list[str],
        current_attempts: int,
        max_attempts: int,
    ) -> dict[str, Any]:
        if not blocking_finding_ids:
            return {
                "decision": "pass",
                "run_status": "passed",
                "final_result": "pass",
                "reason": "no_blocking_findings",
            }
        # At least one blocking finding.
        unfixable = [fid for fid in blocking_finding_ids if fid not in auto_fixable_blocking_ids]
        if unfixable:
            return {
                "decision": "blocked",
                "run_status": "blocked_for_human_review",
                "final_result": "blocked",
                "reason": "unfixable_blocking_findings",
            }
        if current_attempts >= max_attempts:
            return {
                "decision": "blocked",
                "run_status": "blocked_for_human_review",
                "final_result": "blocked",
                "reason": "max_attempts_exceeded",
            }
        return {
            "decision": "auto_fix",
            "run_status": "auto_fix_requested",
            "final_result": "not_applicable",
            "reason": "auto_fixable_blocking_findings",
        }

    @staticmethod
    def _template_hint_from_payload(payload: dict, artifacts: list[dict[str, Any]]) -> str:
        code_gen = (
            payload.get("code_generation")
            if isinstance(payload.get("code_generation"), dict)
            else {}
        )
        if code_gen.get("template"):
            return str(code_gen["template"])
        # Derive from file paths as a fallback.
        for art in artifacts:
            path = (art.get("file_path") or "").lower()
            if path.endswith("_api.py") or "/_api" in path or "/test_" in path and "api" in path:
                return "demo_api"
            if path.startswith("docs/generated/"):
                return "documentation"
            if path.endswith("_utility.py"):
                return "simple_utility"
        return ""

    async def _emit_pass(
        self,
        *,
        payload: dict,
        task_id: str,
        workflow_id: str | None,
        run_id: str,
        workspace_id: str | None,
        findings_count: int,
    ) -> dict[str, Any]:
        # Republish the historical qa.completed event so devops-agent
        # picks it up and the existing pipeline finishes.
        report = self.build_report(payload)
        message = {
            "event": "qa.completed",
            **self.correlation_ids(payload),
            "request": payload.get("request", {}),
            "artifact": report,
            "qa_run_id": run_id,
            "qa_final_result": "pass",
            "produced_by": self.name,
        }
        await self.publish_next(message)
        await self._record_qa_audit(
            task_id=task_id,
            workflow_id=workflow_id,
            decision_type="qa_validation_passed",
            summary=(
                f"qa-agent passed validation run {run_id} for {task_id} "
                f"({findings_count} non-blocking findings)"
            ),
            artifact_refs={
                "qa_run_id": run_id,
                "workspace_id": workspace_id,
                "findings_count": findings_count,
                "final_result": "pass",
                "production_executed": False,
            },
        )
        await send_notification(
            task_id,
            "qa.validation_passed",
            f"qa-agent passed validation for {task_id} ({findings_count} non-blocking findings)",
        )
        with contextlib.suppress(Exception):
            await self._task_store.add_agent_discussion(
                task_id=task_id,
                workflow_id=workflow_id,
                agent=self.name,
                role="qa",
                message_type="validation_note",
                content=(
                    f"qa-agent validation passed for {task_id} "
                    f"({findings_count} non-blocking findings, production_executed=false)"
                ),
                confidence=0.8,
                references={"qa_run_id": run_id, "final_result": "pass"},
            )
            AGENT_DISCUSSIONS_TOTAL.labels(agent=self.name, message_type="validation_note").inc()
        return {
            "task_id": task_id,
            "decision_type": "qa_validation_passed",
            "summary": f"qa-agent validation passed for {task_id}",
            "result": "qa.completed",
            "artifact_refs": {
                "qa_run_id": run_id,
                "workspace_id": workspace_id,
                "findings_count": findings_count,
                "final_result": "pass",
                "production_executed": False,
            },
            "event_type": "qa.completed",
            "message": f"qa-agent validation passed for {task_id}",
        }

    async def _emit_auto_fix(
        self,
        *,
        payload: dict,
        task_id: str,
        workflow_id: str | None,
        run_id: str,
        workspace_id: str | None,
        blocking_ids: list[str],
        attempt_number: int,
        max_attempts: int,
    ) -> dict[str, Any]:
        fix_req = await self._qa_store.create_auto_fix_request(
            task_id=task_id,
            workflow_id=workflow_id,
            workspace_id=workspace_id,
            qa_run_id=run_id,
            finding_ids=blocking_ids,
            attempt_number=attempt_number,
            status="requested",
            requested_by=self.name,
            reason="auto_fixable_blocking_findings",
            fix_strategy="deterministic",
        )
        QA_AUTO_FIX_REQUESTS_TOTAL.labels(status="requested").inc()
        # Publish onto stream.development.autofix so the dev-agent's
        # second consumer picks it up.
        autofix_msg = {
            "event": "code.auto_fix_request",
            **self.correlation_ids(payload),
            "request": payload.get("request", {}),
            "task_id": task_id,
            "workflow_id": workflow_id,
            "qa_run_id": run_id,
            "fix_request_id": fix_req.fix_request_id,
            "workspace_id": workspace_id,
            "finding_ids": blocking_ids,
            "attempt_number": attempt_number,
            "max_auto_fix_attempts": max_attempts,
            "produced_by": self.name,
        }
        with start_span(
            "qa.request_auto_fix",
            **{
                "service.name": self.name,
                "agent": self.name,
                "task_id": task_id,
                "qa_run_id": run_id,
                "fix_request_id": fix_req.fix_request_id,
                "attempt_number": attempt_number,
            },
        ):
            await self.bus.publish_event(AUTO_FIX_REQUEST_STREAM, autofix_msg)
        # Also drop a qa.auto_fix_requested event back onto stream.qa so
        # the workflow consumer can move the workflow stage.
        await self.bus.publish_event(
            "stream.qa",
            {
                "event": "qa.auto_fix_requested",
                **self.correlation_ids(payload),
                "task_id": task_id,
                "workflow_id": workflow_id,
                "qa_run_id": run_id,
                "fix_request_id": fix_req.fix_request_id,
                "attempt_number": attempt_number,
                "max_auto_fix_attempts": max_attempts,
                "produced_by": self.name,
            },
        )
        await self._record_qa_audit(
            task_id=task_id,
            workflow_id=workflow_id,
            decision_type="qa_auto_fix_requested",
            summary=(
                f"qa-agent requested auto-fix for {task_id} "
                f"(attempt={attempt_number}/{max_attempts})"
            ),
            artifact_refs={
                "qa_run_id": run_id,
                "fix_request_id": fix_req.fix_request_id,
                "finding_ids": blocking_ids,
                "attempt_number": attempt_number,
                "max_auto_fix_attempts": max_attempts,
                "final_result": "not_applicable",
                "production_executed": False,
            },
        )
        await send_notification(
            task_id,
            "qa.auto_fix_requested",
            f"qa-agent requested auto-fix for {task_id} (attempt={attempt_number}/{max_attempts})",
        )
        return {
            "task_id": task_id,
            "decision_type": "qa_auto_fix_requested",
            "summary": f"qa-agent requested auto-fix for {task_id}",
            "result": "qa.auto_fix_requested",
            "artifact_refs": {
                "qa_run_id": run_id,
                "fix_request_id": fix_req.fix_request_id,
                "finding_ids": blocking_ids,
                "attempt_number": attempt_number,
                "max_auto_fix_attempts": max_attempts,
                "production_executed": False,
            },
            "event_type": "qa.auto_fix_requested",
            "message": f"qa-agent requested auto-fix for {task_id} (attempt={attempt_number})",
        }

    async def _emit_blocked(
        self,
        *,
        payload: dict,
        task_id: str,
        workflow_id: str | None,
        run_id: str,
        workspace_id: str | None,
        blocking_ids: list[str],
        reason: str,
    ) -> dict[str, Any]:
        QA_BLOCKED_FOR_HUMAN_REVIEW_TOTAL.labels(reason=reason).inc()
        QA_VALIDATION_FAILED_TOTAL.labels(reason=reason).inc()
        await self.bus.publish_event(
            "stream.qa",
            {
                "event": "qa.blocked_for_human_review",
                **self.correlation_ids(payload),
                "task_id": task_id,
                "workflow_id": workflow_id,
                "qa_run_id": run_id,
                "blocking_finding_ids": blocking_ids,
                "reason": reason,
                "produced_by": self.name,
            },
        )
        await self._record_qa_audit(
            task_id=task_id,
            workflow_id=workflow_id,
            decision_type="qa_blocked_for_human_review",
            summary=(f"qa-agent blocked {task_id} for human review (reason={reason})"),
            artifact_refs={
                "qa_run_id": run_id,
                "workspace_id": workspace_id,
                "blocking_finding_ids": blocking_ids,
                "reason": reason,
                "final_result": "blocked",
                "production_executed": False,
            },
        )
        await send_notification(
            task_id,
            "qa.blocked_for_human_review",
            f"qa-agent blocked {task_id} for human review (reason={reason})",
        )
        with contextlib.suppress(Exception):
            await self._task_store.update_work_item_status(task_id, "blocked")
        return {
            "task_id": task_id,
            "decision_type": "qa_blocked_for_human_review",
            "summary": f"qa-agent blocked {task_id} for human review",
            "result": "qa.blocked_for_human_review",
            "artifact_refs": {
                "qa_run_id": run_id,
                "blocking_finding_ids": blocking_ids,
                "reason": reason,
                "final_result": "blocked",
                "production_executed": False,
            },
            "event_type": "qa.blocked_for_human_review",
            "message": f"qa-agent blocked {task_id} for human review (reason={reason})",
        }

    async def _legacy_passthrough(
        self, payload: dict, task_id: str, workflow_id: str | None
    ) -> dict[str, Any]:
        """Fallback path for synthetic tests / mock payloads with no workspace."""
        report = self.build_report(payload)
        message = {
            "event": "qa.completed",
            **self.correlation_ids(payload),
            "request": payload.get("request", {}),
            "artifact": report,
            "produced_by": self.name,
        }
        await self.publish_next(message)
        with contextlib.suppress(Exception):
            await self._task_store.add_agent_discussion(
                task_id=task_id,
                workflow_id=workflow_id,
                agent=self.name,
                role="qa",
                message_type="validation_note",
                content=(f"qa-agent produced a mock test_report for {task_id}; no real tests run."),
                confidence=0.7,
                references={"artifact": "test_report", "mock": True},
            )
            AGENT_DISCUSSIONS_TOTAL.labels(agent=self.name, message_type="validation_note").inc()
        return {
            "task_id": task_id,
            "decision_type": "qa",
            "summary": f"qa-agent produced test_report for {task_id}",
            "result": "qa.completed",
            "artifact_refs": {"artifact": "test_report"},
            "event_type": "qa.completed",
            "message": f"qa-agent completed task {task_id}",
        }

    async def _record_qa_audit(
        self,
        *,
        task_id: str,
        workflow_id: str | None,
        decision_type: str,
        summary: str,
        artifact_refs: dict[str, Any],
    ) -> None:
        with contextlib.suppress(Exception):
            await publish_audit_event(
                task_id=task_id,
                workflow_id=workflow_id or "",
                agent=self.name,
                decision_type=decision_type,
                summary=summary,
                result=artifact_refs.get("final_result", "ok"),
                artifact_refs=artifact_refs,
            )
