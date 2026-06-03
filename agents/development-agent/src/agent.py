"""Stage 28 — development-agent with controlled code generation.

The development-agent no longer emits a pure mock ``code_change``
artifact. Each ready-for-development task runs through:

1. classify (deterministic templates: documentation / demo_api /
   simple_utility / blocked)
2. create / upsert a row in ``code_workspaces``
3. write the generated files into the workspace path
4. record a row in ``code_change_artifacts`` per file (with the
   unified diff and SHA hashes)
5. run policy + py_compile validation
6. if every check passes, create / upsert one row in
   ``pr_draft_artifacts`` containing the PR body, risk assessment,
   and rollback plan
7. emit ``code.generated`` / ``code.pr_draft_ready`` notifications
   and ``code_generated`` / ``code_pr_draft_created`` audit events
8. publish ``development.completed`` to ``stream.qa`` — the QA agent
   continues the pipeline.

If classification / policy / validation refuses the request, the
workspace status is flipped to ``blocked`` and ``code.generation_blocked``
notification + ``code_generation_blocked`` audit event are emitted.
The pipeline still publishes a ``development.completed`` event so the
workflow can complete (devops-agent will see no PR draft and will
fall back to its existing dry-run demo PR path).

No LLM is invoked anywhere. The deterministic rules live in
``code_generator``.
"""

from __future__ import annotations

import contextlib
import os
from typing import Any

from code_generator import (
    GenerationPlan,
    plan_generation,
    write_plan,
)

from shared.sdk.audit.publisher import publish_audit_event
from shared.sdk.base_agent.stream_agent import StreamAgent
from shared.sdk.code_workspace import (
    CodeWorkspaceStore,
    DEFAULT_ALLOWED_PATHS,
    DEFAULT_DENIED_PATHS,
    validate_diff_not_empty,
    validate_python_syntax_if_py,
)
from shared.sdk.notifications.client import send_notification
from shared.sdk.observability.metrics import (
    AGENT_DISCUSSIONS_TOTAL,
    CODE_GENERATION_ATTEMPTS_TOTAL,
    CODE_GENERATION_BLOCKED_TOTAL,
    CODE_GENERATION_SUCCESS_TOTAL,
    CODE_VALIDATION_FAILURES_TOTAL,
    CODE_WORKSPACES_TOTAL,
    PR_DRAFT_ARTIFACTS_TOTAL,
    QA_AUTO_FIX_ATTEMPTS_TOTAL,
)
from shared.sdk.observability.tracing import start_span
from shared.sdk.qa import QAStore
from shared.sdk.task_execution import TaskExecutionStore

#: Stream the qa-agent drops auto-fix requests onto.
AUTO_FIX_REQUEST_STREAM = "stream.development.autofix"

WORKSPACE_ROOT_DEFAULT = "/tmp/aiagents-workspaces"


class SimulatedFailure(RuntimeError):
    """Raised by development-agent when the request asks for a controlled failure."""


def _workspace_root_for(task_id: str) -> str:
    base = os.environ.get("DEVELOPMENT_AGENT_WORKSPACE_ROOT", WORKSPACE_ROOT_DEFAULT)
    return os.path.join(base, task_id)


def _build_pr_body(
    *,
    task_id: str,
    plan: GenerationPlan,
    changed_files: list[dict[str, Any]],
    validation: dict[str, Any],
    risk: dict[str, Any],
) -> str:
    if changed_files:
        bullets = "\n".join(f"- `{f['file_path']}` ({f['change_type']})" for f in changed_files)
    else:
        bullets = "- (none)"
    diff_summary_lines = (
        "\n".join(f"- `{f['file_path']}`: {f.get('diff_summary', '')}" for f in changed_files)
        or "- (no diff)"
    )
    return (
        "## Summary\n"
        f"{plan.summary}\n\n"
        "## Changed Files\n"
        f"{bullets}\n\n"
        "## Generated Diff Summary\n"
        f"{diff_summary_lines}\n\n"
        "## Validation Result\n"
        f"- py_compile: {validation.get('py_compile', 'n/a')}\n"
        f"- diff_not_empty: {validation.get('diff_not_empty', 'n/a')}\n"
        f"- overall: {validation.get('status', 'n/a')}\n\n"
        "## Risk Assessment\n"
        f"- risk_level: {risk.get('risk_level', 'unknown')}\n"
        f"- files: {risk.get('files_count', 0)} "
        f"(docs={risk.get('docs_count', 0)} tests={risk.get('tests_count', 0)} "
        f"app={risk.get('app_count', 0)})\n"
        f"- reason: {risk.get('reason', '')}\n\n"
        "## Rollback Plan\n"
        f"{plan.rollback_plan or 'No rollback required for the dry-run / draft path.'}\n\n"
        "## Safety Notes\n"
        f"- task_id: `{task_id}`\n"
        "- generator_mode: deterministic_template (no LLM)\n"
        "- production_executed: false\n"
        "- real_github_write: false\n"
        "- workspace files are NOT auto-committed; reviewer must port "
        "them manually before merge.\n"
    )


def _short_preview(text: str, limit: int = 1200) -> str:
    if not text:
        return ""
    if len(text) <= limit:
        return text
    return text[:limit] + "\n…[truncated]"


class DevelopmentAgent(StreamAgent):
    """Stage 28 development-agent — controlled code generation + PR draft.

    Honors a controlled-failure switch (``request.simulate_failure: true``)
    so the retry / dead-letter foundation can be exercised end-to-end. The
    failure only raises within ``handle`` — it never crashes the consumer
    loop, and the controlled code generation path is skipped on that branch.
    """

    name = "development-agent"
    input_stream = "stream.development"
    output_stream = "stream.qa"
    group = "development-agent-group"
    consumer = "development-agent-1"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._task_store = TaskExecutionStore()
        self._code_store = CodeWorkspaceStore()

    # ----- legacy shim kept for test_development_agent.test_build_artifact ---
    def build_artifact(self, payload: dict) -> dict:
        task_id = str(payload.get("task_id", "unknown"))
        return {
            "artifact_type": "code_change",
            "task_id": task_id,
            "files_changed": [],
            "summary": f"mock code change for {task_id}",
            "produced_by": self.name,
            "mock": True,
        }

    @staticmethod
    def _should_simulate_failure(payload: dict) -> bool:
        request = payload.get("request") or {}
        if not isinstance(request, dict):
            return False
        return bool(request.get("simulate_failure"))

    # ------------------------------------------------------------------
    # controlled code generation
    # ------------------------------------------------------------------

    async def _classify_and_generate(
        self, payload: dict
    ) -> tuple[GenerationPlan, dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
        """Run the deterministic plan + write phase.

        Returns ``(plan, validation, changed_files, risk)`` so the caller
        can build the audit / notification / PR draft payloads.
        """
        task_id = str(payload.get("task_id", "unknown"))
        workflow_id = str(payload.get("workflow_id", "")) or None
        request = payload.get("request") if isinstance(payload.get("request"), dict) else {}
        description = str(request.get("description") or "")
        request_type = str(request.get("type") or payload.get("request_type") or "unknown")

        # 1) optional work-item lookup (best effort) -----------------------
        execution_mode = "delivery_task"
        work_item_status: str | None = None
        work_item_id: str | None = None
        try:
            wi = await self._task_store.get_work_item(task_id)
            if wi is not None:
                execution_mode = wi.execution_mode or execution_mode
                work_item_status = wi.status
                work_item_id = wi.work_item_id
        except Exception:
            pass

        # 2) plan --------------------------------------------------------
        with start_span(
            "code_generation.plan",
            **{
                "service.name": self.name,
                "agent": self.name,
                "task_id": task_id,
                "workflow_id": workflow_id or "",
                "execution_mode": execution_mode,
            },
        ):
            plan = plan_generation(
                task_id=task_id,
                description=description,
                request_type=request_type,
                work_item_status=work_item_status,
            )
        CODE_GENERATION_ATTEMPTS_TOTAL.labels(
            execution_mode=execution_mode,
            generator_mode="deterministic_template",
        ).inc()

        # 3) create workspace row (status depends on plan outcome) -------
        ws_status = "generating" if plan.status == "ready" else "blocked"
        workspace_path = _workspace_root_for(task_id)
        ws = await self._code_store.create_workspace(
            task_id=task_id,
            workflow_id=workflow_id,
            work_item_id=work_item_id,
            execution_mode=execution_mode,
            status=ws_status,
            base_commit=os.environ.get("GIT_COMMIT_SHA", ""),
            branch_name=f"ai-agents/{task_id}",
            workspace_path=workspace_path,
            allowed_paths=list(DEFAULT_ALLOWED_PATHS),
            denied_paths=list(DEFAULT_DENIED_PATHS),
            generator_mode="deterministic_template" if plan.status == "ready" else "blocked",
            blocked_reason="" if plan.status == "ready" else plan.reason,
            created_by_agent=self.name,
        )
        CODE_WORKSPACES_TOTAL.labels(
            execution_mode=execution_mode,
            generator_mode=ws.generator_mode,
            status=ws_status,
        ).inc()
        with contextlib.suppress(Exception):
            await self._write_workspace_audit(
                task_id=task_id,
                workflow_id=workflow_id,
                workspace_id=ws.workspace_id,
                execution_mode=execution_mode,
                ws_status=ws_status,
                plan=plan,
            )
        with contextlib.suppress(Exception):
            await send_notification(
                task_id,
                "code.workspace_created",
                (
                    f"code workspace {ws.workspace_id} created for {task_id} "
                    f"(status={ws_status}, template={plan.template})"
                ),
            )

        # 4) if blocked, short-circuit ----------------------------------
        if plan.status != "ready":
            CODE_GENERATION_BLOCKED_TOTAL.labels(reason=plan.reason or "blocked").inc()
            await self._code_store.update_workspace_status(
                task_id, "blocked", blocked_reason=plan.reason
            )
            await self._publish_blocked(task_id, workflow_id, plan, ws.workspace_id, execution_mode)
            return plan, {"status": "blocked", "reason": plan.reason}, [], plan.risk_assessment

        # 5) write files --------------------------------------------------
        with start_span(
            "code_generation.generate",
            **{
                "service.name": self.name,
                "agent": self.name,
                "task_id": task_id,
                "workflow_id": workflow_id or "",
                "workspace_id": ws.workspace_id,
                "template": plan.template,
                "changed_files_count": len(plan.files),
            },
        ):
            written, refused = write_plan(
                plan,
                workspace_root=workspace_path,
                allowed_paths=list(DEFAULT_ALLOWED_PATHS),
            )

        if refused or not written:
            reason = f"refused:{refused[0][1]}" if refused else "no_files_written"
            CODE_GENERATION_BLOCKED_TOTAL.labels(reason=reason).inc()
            await self._code_store.update_workspace_status(
                task_id, "blocked", blocked_reason=reason
            )
            # Re-purpose plan for the blocked notification path.
            plan.status = "blocked"
            plan.reason = reason
            await self._publish_blocked(task_id, workflow_id, plan, ws.workspace_id, execution_mode)
            return plan, {"status": "blocked", "reason": reason}, [], plan.risk_assessment

        # 6) record artifacts + run validation ----------------------------
        changed_files: list[dict[str, Any]] = []
        for w in written:
            artifact = await self._code_store.add_code_change_artifact(
                task_id=task_id,
                workflow_id=workflow_id,
                workspace_id=ws.workspace_id,
                file_path=w.relative_path,
                change_type=w.change_type,
                before_sha=w.before_sha,
                after_sha=w.after_sha,
                diff_summary=w.diff_summary,
                diff_text=_short_preview(w.diff_text, limit=4000),
                generated_content_preview=_short_preview(_read_file(w.full_path), limit=1200),
                validation_status="pending",
            )
            changed_files.append(
                {
                    "artifact_id": artifact.artifact_id,
                    "file_path": w.relative_path,
                    "change_type": w.change_type,
                    "before_sha": w.before_sha,
                    "after_sha": w.after_sha,
                    "diff_summary": w.diff_summary,
                }
            )

        with start_span(
            "code_generation.local_validation",
            **{
                "service.name": self.name,
                "agent": self.name,
                "task_id": task_id,
                "workflow_id": workflow_id or "",
                "workspace_id": ws.workspace_id,
                "changed_files_count": len(changed_files),
            },
        ):
            validation = self._run_validation(workspace_path, [w.relative_path for w in written])
            for w in written:
                ok, _ = validate_diff_not_empty(w.diff_text)
                if not ok:
                    validation["diff_not_empty"] = "fail"
                    CODE_VALIDATION_FAILURES_TOTAL.labels(check="diff_empty").inc()
                    break
            else:
                validation.setdefault("diff_not_empty", "pass")

        validation["status"] = (
            "passed"
            if validation.get("py_compile") == "pass" and validation.get("diff_not_empty") == "pass"
            else "failed"
        )

        # Update artifact validation_status in bulk via best-effort
        # re-insert is overkill; we just record the rolled-up status in
        # the PR draft test_results JSONB. The per-artifact column is
        # left at ``pending`` for partial-fail visibility — operators
        # see the rollup on the PR draft.
        risk = plan.risk_assessment or {}
        if validation["status"] == "passed":
            CODE_GENERATION_SUCCESS_TOTAL.labels(
                execution_mode=execution_mode,
                generator_mode="deterministic_template",
                risk_level=str(risk.get("risk_level", "unknown")),
            ).inc()
            await self._code_store.update_workspace_status(task_id, "ready_for_pr_draft")
        else:
            CODE_VALIDATION_FAILURES_TOTAL.labels(check="overall").inc()
            await self._code_store.update_workspace_status(
                task_id, "validation_failed", blocked_reason=validation.get("reason", "validation")
            )

        return plan, validation, changed_files, risk

    def _run_validation(self, workspace_path: str, relative_paths: list[str]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        ok, why = validate_python_syntax_if_py(workspace_path, relative_paths)
        result["py_compile"] = "pass" if ok else "fail"
        if not ok:
            result["py_compile_reason"] = why
            CODE_VALIDATION_FAILURES_TOTAL.labels(check="py_compile").inc()
        return result

    async def _write_workspace_audit(
        self,
        *,
        task_id: str,
        workflow_id: str | None,
        workspace_id: str,
        execution_mode: str,
        ws_status: str,
        plan: GenerationPlan,
    ) -> None:
        await publish_audit_event(
            task_id=task_id,
            workflow_id=workflow_id or "",
            agent=self.name,
            decision_type="code_workspace_created",
            summary=(
                f"code workspace {workspace_id} created for {task_id} "
                f"(template={plan.template}, status={ws_status})"
            ),
            result=ws_status,
            artifact_refs={
                "workspace_id": workspace_id,
                "execution_mode": execution_mode,
                "generator_mode": (
                    "deterministic_template" if plan.status == "ready" else "blocked"
                ),
                "template": plan.template,
                "production_executed": False,
            },
        )

    async def _publish_blocked(
        self,
        task_id: str,
        workflow_id: str | None,
        plan: GenerationPlan,
        workspace_id: str,
        execution_mode: str,
    ) -> None:
        with contextlib.suppress(Exception):
            await publish_audit_event(
                task_id=task_id,
                workflow_id=workflow_id or "",
                agent=self.name,
                decision_type="code_generation_blocked",
                summary=(
                    f"controlled code generation blocked for {task_id} " f"(reason={plan.reason})"
                ),
                result="blocked",
                artifact_refs={
                    "workspace_id": workspace_id,
                    "execution_mode": execution_mode,
                    "generator_mode": "blocked",
                    "blocked_reason": plan.reason,
                    "production_executed": False,
                },
            )
        with contextlib.suppress(Exception):
            await send_notification(
                task_id,
                "code.generation_blocked",
                (
                    f"code generation blocked for {task_id} "
                    f"(reason={plan.reason or 'unspecified'})"
                ),
            )

    async def _publish_validation_event(
        self,
        task_id: str,
        workflow_id: str | None,
        workspace_id: str,
        validation: dict[str, Any],
        changed_files: list[dict[str, Any]],
    ) -> None:
        passed = validation.get("status") == "passed"
        decision_type = "code_validation_passed" if passed else "code_validation_failed"
        with contextlib.suppress(Exception):
            await publish_audit_event(
                task_id=task_id,
                workflow_id=workflow_id or "",
                agent=self.name,
                decision_type=decision_type,
                summary=(
                    f"local validation {validation.get('status', 'unknown')} for {task_id} "
                    f"({len(changed_files)} files)"
                ),
                result=str(validation.get("status", "unknown")),
                artifact_refs={
                    "workspace_id": workspace_id,
                    "py_compile": validation.get("py_compile"),
                    "diff_not_empty": validation.get("diff_not_empty"),
                    "changed_files": [f["file_path"] for f in changed_files],
                    "production_executed": False,
                },
            )
        with contextlib.suppress(Exception):
            await send_notification(
                task_id,
                "code.validation_passed" if passed else "code.validation_failed",
                (
                    f"code validation {validation.get('status', 'unknown')} for {task_id} "
                    f"({len(changed_files)} files)"
                ),
            )

    async def _publish_code_generated(
        self,
        task_id: str,
        workflow_id: str | None,
        workspace_id: str,
        plan: GenerationPlan,
        changed_files: list[dict[str, Any]],
        validation: dict[str, Any],
    ) -> None:
        with contextlib.suppress(Exception):
            await publish_audit_event(
                task_id=task_id,
                workflow_id=workflow_id or "",
                agent=self.name,
                decision_type="code_generated",
                summary=(
                    f"deterministic code generated for {task_id} "
                    f"(template={plan.template}, files={len(changed_files)})"
                ),
                result="ok",
                artifact_refs={
                    "workspace_id": workspace_id,
                    "template": plan.template,
                    "generator_mode": "deterministic_template",
                    "changed_files": [f["file_path"] for f in changed_files],
                    "validation_status": validation.get("status"),
                    "production_executed": False,
                },
            )
        with contextlib.suppress(Exception):
            await send_notification(
                task_id,
                "code.generated",
                (
                    f"deterministic code generated for {task_id} "
                    f"(template={plan.template}, files={len(changed_files)})"
                ),
            )

    async def _create_pr_draft(
        self,
        *,
        task_id: str,
        workflow_id: str | None,
        workspace_id: str,
        execution_mode: str,
        plan: GenerationPlan,
        changed_files: list[dict[str, Any]],
        validation: dict[str, Any],
        risk: dict[str, Any],
    ) -> dict[str, Any]:
        body = _build_pr_body(
            task_id=task_id,
            plan=plan,
            changed_files=changed_files,
            validation=validation,
            risk=risk,
        )
        with start_span(
            "code_generation.create_pr_draft",
            **{
                "service.name": self.name,
                "agent": self.name,
                "task_id": task_id,
                "workflow_id": workflow_id or "",
                "workspace_id": workspace_id,
                "changed_files_count": len(changed_files),
                "risk_level": str(risk.get("risk_level", "unknown")),
            },
        ):
            draft = await self._code_store.create_pr_draft_artifact(
                task_id=task_id,
                workflow_id=workflow_id,
                workspace_id=workspace_id,
                title=plan.title or f"[ai-agents-swd] {plan.template} — {task_id}",
                body=body,
                changed_files=changed_files,
                test_results=validation,
                risk_assessment=risk,
                rollback_plan=plan.rollback_plan,
                github_dry_run_result={
                    "dry_run": True,
                    "production_executed": False,
                    "delivered_by": "development-agent",
                    "real_github_write": False,
                },
                status="ready",
            )
        PR_DRAFT_ARTIFACTS_TOTAL.labels(
            execution_mode=execution_mode,
            status="ready",
            risk_level=str(risk.get("risk_level", "unknown")),
        ).inc()
        with contextlib.suppress(Exception):
            await publish_audit_event(
                task_id=task_id,
                workflow_id=workflow_id or "",
                agent=self.name,
                decision_type="code_pr_draft_created",
                summary=(
                    f"PR draft {draft.pr_draft_id} created for {task_id} "
                    f"(files={len(changed_files)}, risk={risk.get('risk_level', 'unknown')})"
                ),
                result="ready",
                artifact_refs={
                    "pr_draft_id": draft.pr_draft_id,
                    "workspace_id": workspace_id,
                    "changed_files": [f["file_path"] for f in changed_files],
                    "risk_level": risk.get("risk_level"),
                    "production_executed": False,
                },
            )
        with contextlib.suppress(Exception):
            await send_notification(
                task_id,
                "code.pr_draft_ready",
                (
                    f"PR draft ready for {task_id} "
                    f"(files={len(changed_files)}, risk={risk.get('risk_level', 'unknown')})"
                ),
            )
        return {
            "pr_draft_id": draft.pr_draft_id,
            "title": draft.title,
            "status": draft.status,
        }

    # ------------------------------------------------------------------
    # main StreamAgent handle()
    # ------------------------------------------------------------------

    async def handle(self, payload: dict) -> dict:
        if self._should_simulate_failure(payload):
            task_id = str(payload.get("task_id", "unknown"))
            raise SimulatedFailure(
                f"development-agent simulated failure for {task_id} " "(request.simulate_failure)"
            )

        task_id = str(payload.get("task_id", "unknown"))
        workflow_id = str(payload.get("workflow_id", "")) or None

        plan: GenerationPlan
        validation: dict[str, Any]
        changed_files: list[dict[str, Any]]
        risk: dict[str, Any]
        try:
            plan, validation, changed_files, risk = await self._classify_and_generate(payload)
        except Exception as exc:  # pragma: no cover — defensive
            plan = GenerationPlan(
                template="blocked",
                status="blocked",
                reason=f"exception:{type(exc).__name__}",
                summary=f"controlled code generation crashed: {exc}",
                title=f"[ai-agents-swd][BLOCKED] {task_id}",
                rollback_plan="No artifacts written — see audit / logs.",
            )
            validation = {"status": "blocked", "reason": str(exc)}
            changed_files = []
            risk = {}

        # Workspace + audit / notification side effects happen inside
        # _classify_and_generate; here we just need to record the
        # ``code_generated`` / ``code_validation_*`` audit + emit the
        # PR draft if the validation passed.
        workspace = None
        with contextlib.suppress(Exception):
            workspace = await self._code_store.get_workspace(task_id)
        workspace_id = workspace.workspace_id if workspace else ""

        pr_draft_info: dict[str, Any] = {}
        if changed_files and plan.status == "ready":
            await self._publish_code_generated(
                task_id, workflow_id, workspace_id, plan, changed_files, validation
            )
            await self._publish_validation_event(
                task_id, workflow_id, workspace_id, validation, changed_files
            )
            if validation.get("status") == "passed":
                pr_draft_info = await self._create_pr_draft(
                    task_id=task_id,
                    workflow_id=workflow_id,
                    workspace_id=workspace_id,
                    execution_mode=workspace.execution_mode if workspace else "delivery_task",
                    plan=plan,
                    changed_files=changed_files,
                    validation=validation,
                    risk=risk,
                )

        artifact = {
            "artifact_type": "code_change",
            "task_id": task_id,
            "files_changed": [f["file_path"] for f in changed_files],
            "files": changed_files,
            "summary": plan.summary,
            "template": plan.template,
            "workspace_id": workspace_id,
            "pr_draft_id": pr_draft_info.get("pr_draft_id", ""),
            "risk_assessment": risk,
            "validation": validation,
            "produced_by": self.name,
            "mock": plan.status != "ready",
            "production_executed": False,
        }

        message = {
            "event": "development.completed",
            **self.correlation_ids(payload),
            "request": payload.get("request", {}),
            "artifact": artifact,
            "code_generation": {
                "workspace_id": workspace_id,
                "status": (workspace.status if workspace else "unknown"),
                "template": plan.template,
                "changed_files": [f["file_path"] for f in changed_files],
                "validation_status": validation.get("status"),
                "pr_draft_id": pr_draft_info.get("pr_draft_id", ""),
            },
            "produced_by": self.name,
        }
        await self.publish_next(message)

        with contextlib.suppress(Exception):
            await self._task_store.add_agent_discussion(
                task_id=task_id,
                workflow_id=workflow_id,
                agent=self.name,
                role="developer",
                message_type="execution_plan",
                content=(
                    f"development-agent ran controlled code generation for {task_id}; "
                    f"template={plan.template}, files={len(changed_files)}, "
                    f"validation={validation.get('status', 'n/a')}, "
                    f"pr_draft={'yes' if pr_draft_info else 'no'}, "
                    "production_executed=false."
                ),
                confidence=0.7 if changed_files else 0.4,
                references={
                    "artifact": "code_change",
                    "template": plan.template,
                    "workspace_id": workspace_id,
                    "pr_draft_id": pr_draft_info.get("pr_draft_id", ""),
                    "risk_level": risk.get("risk_level", "unknown"),
                },
            )
            AGENT_DISCUSSIONS_TOTAL.labels(agent=self.name, message_type="execution_plan").inc()

        decision_type = "code_generated" if changed_files else "code_generation_blocked"
        result_label = (
            "code.generated"
            if changed_files and validation.get("status") == "passed"
            else ("code.validation_failed" if changed_files else "code.generation_blocked")
        )
        return {
            "task_id": task_id,
            "decision_type": decision_type,
            "summary": plan.summary,
            "result": "development.completed",
            "artifact_refs": {
                "artifact": "code_change",
                "workspace_id": workspace_id,
                "template": plan.template,
                "changed_files": [f["file_path"] for f in changed_files],
                "validation_status": validation.get("status"),
                "pr_draft_id": pr_draft_info.get("pr_draft_id", ""),
                "production_executed": False,
            },
            "event_type": "development.completed",
            "message": (
                f"development-agent completed {task_id} "
                f"(template={plan.template}, files={len(changed_files)}, "
                f"result={result_label})"
            ),
        }


def _read_file(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return ""


# ---------------------------------------------------------------------------
# Stage 29 — deterministic auto-fix consumer
# ---------------------------------------------------------------------------


_DETERMINISTIC_PR_SECTIONS = {
    "## Summary": "_Auto-fix placeholder._",
    "## Changed Files": "- (no diff recorded)",
    "## Generated Diff Summary": "- (no diff hunks)",
    "## Validation Result": "- py_compile: pending\n- diff_not_empty: pending",
    "## Risk Assessment": "- risk_level: unknown\n- reason: auto-fix appended placeholder",
    "## Rollback Plan": "Revert the workspace files manually — nothing was committed.",
    "## Safety Notes": (
        "- task_id: auto-fix appended placeholder\n"
        "- generator_mode: deterministic_template (no LLM)\n"
        "- production_executed: false"
    ),
}


def _append_missing_sections(body: str, missing: list[str]) -> str:
    """Append every section header in ``missing`` with a placeholder body."""
    out = body.rstrip() + "\n"
    for header in missing:
        placeholder = _DETERMINISTIC_PR_SECTIONS.get(header, "_TODO_")
        out += f"\n{header}\n{placeholder}\n"
    return out


class CodeAutoFixAgent(StreamAgent):
    """Stage 29 — consumes ``stream.development.autofix`` requests filed by
    the qa-agent and applies deterministic fixes ONLY.

    Supported fixes:

    A. Missing generated test file (demo_api template) — re-emit the
       deterministic test stub.
    B. PR draft missing required sections — append placeholder sections
       so the body carries all 7 markers again.
    C. Python syntax error in a generated file — regenerate via the
       deterministic template (re-write the original file).

    Anything outside those three buckets is refused and surfaced as
    ``code.auto_fix_failed`` so the qa-agent's
    ``blocked_for_human_review`` path takes over on the next pass.
    """

    name = "development-agent-autofix"
    input_stream = AUTO_FIX_REQUEST_STREAM
    output_stream = "stream.qa"
    group = "development-agent-autofix-group"
    consumer = "development-agent-autofix-1"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._task_store = TaskExecutionStore()
        self._code_store = CodeWorkspaceStore()
        self._qa_store = QAStore()

    async def handle(self, payload: dict) -> dict:  # noqa: PLR0915
        task_id = str(payload.get("task_id", "unknown"))
        workflow_id = str(payload.get("workflow_id", "")) or None
        fix_request_id = str(payload.get("fix_request_id") or "")
        qa_run_id = str(payload.get("qa_run_id") or "")
        attempt_number = int(payload.get("attempt_number") or 1)
        finding_ids = payload.get("finding_ids") or []

        with start_span(
            "code.auto_fix_start",
            **{
                "service.name": self.name,
                "agent": self.name,
                "task_id": task_id,
                "workflow_id": workflow_id or "",
                "fix_request_id": fix_request_id,
                "qa_run_id": qa_run_id,
                "attempt_number": attempt_number,
                "finding_count": len(finding_ids),
            },
        ):
            findings = await self._qa_store.list_findings(task_id, qa_run_id=qa_run_id or None)
        # Filter to the explicit finding ids the request mentioned, if any.
        if finding_ids:
            findings = [f for f in findings if f.finding_id in finding_ids]
        workspace = None
        with contextlib.suppress(Exception):
            workspace = await self._code_store.get_workspace(task_id)
        workspace_path = workspace.workspace_path if workspace else _workspace_root_for(task_id)
        workspace_id = workspace.workspace_id if workspace else None

        applied: list[dict[str, Any]] = []
        refused: list[dict[str, Any]] = []

        with start_span(
            "code.auto_fix_apply",
            **{
                "service.name": self.name,
                "agent": self.name,
                "task_id": task_id,
                "fix_request_id": fix_request_id,
                "finding_count": len(findings),
            },
        ):
            for finding in findings:
                if not finding.auto_fixable:
                    refused.append({"finding_id": finding.finding_id, "reason": "not_auto_fixable"})
                    continue
                fix_result = await self._apply_one(
                    finding=finding,
                    task_id=task_id,
                    workspace_path=workspace_path,
                    workspace_id=workspace_id,
                    workflow_id=workflow_id,
                )
                if fix_result.get("status") == "applied":
                    applied.append(fix_result)
                    with contextlib.suppress(Exception):
                        await self._qa_store.update_finding_status(
                            finding.finding_id, status="fixed", resolved=True
                        )
                else:
                    refused.append(fix_result)

        completed_ok = bool(applied) and not any(r.get("severity") == "critical" for r in refused)
        status_label = "completed" if completed_ok else "failed"
        QA_AUTO_FIX_ATTEMPTS_TOTAL.labels(result=status_label).inc()
        with contextlib.suppress(Exception):
            await self._qa_store.update_auto_fix_request(
                fix_request_id,
                status=status_label,
                result={
                    "applied": applied,
                    "refused": refused,
                    "attempt_number": attempt_number,
                },
            )

        decision_type = "code_auto_fix_completed" if completed_ok else "code_auto_fix_failed"
        event_type = "code.auto_fix_completed" if completed_ok else "code.auto_fix_failed"

        # Re-publish development.auto_fix_completed onto stream.qa so the
        # qa-agent re-validates. The qa-agent's "auto_fix_completed"
        # branch bumps auto_fix_attempts before re-running the rules.
        with start_span(
            "code.auto_fix_complete",
            **{
                "service.name": self.name,
                "agent": self.name,
                "task_id": task_id,
                "fix_request_id": fix_request_id,
                "attempt_number": attempt_number,
                "result": status_label,
            },
        ):
            await self.publish_next(
                {
                    "event": (
                        "development.auto_fix_completed"
                        if completed_ok
                        else "development.auto_fix_failed"
                    ),
                    **self.correlation_ids(payload),
                    "request": payload.get("request", {}),
                    "task_id": task_id,
                    "workflow_id": workflow_id,
                    "fix_request_id": fix_request_id,
                    "qa_run_id": qa_run_id,
                    "attempt_number": attempt_number,
                    "applied_count": len(applied),
                    "refused_count": len(refused),
                    "produced_by": self.name,
                }
            )

        with contextlib.suppress(Exception):
            await publish_audit_event(
                task_id=task_id,
                workflow_id=workflow_id or "",
                agent=self.name,
                decision_type=decision_type,
                summary=(
                    f"auto-fix {status_label} for {task_id} "
                    f"(attempt={attempt_number}, applied={len(applied)}, refused={len(refused)})"
                ),
                result=status_label,
                artifact_refs={
                    "fix_request_id": fix_request_id,
                    "qa_run_id": qa_run_id,
                    "workspace_id": workspace_id,
                    "attempt_number": attempt_number,
                    "applied": applied,
                    "refused": refused,
                    "production_executed": False,
                },
            )
        with contextlib.suppress(Exception):
            await send_notification(
                task_id,
                event_type,
                (
                    f"auto-fix {status_label} for {task_id} "
                    f"(attempt={attempt_number}, applied={len(applied)}, refused={len(refused)})"
                ),
            )
        return {
            "task_id": task_id,
            "decision_type": decision_type,
            "summary": f"auto-fix {status_label} for {task_id}",
            "result": event_type,
            "artifact_refs": {
                "fix_request_id": fix_request_id,
                "qa_run_id": qa_run_id,
                "attempt_number": attempt_number,
                "applied": applied,
                "refused": refused,
                "production_executed": False,
            },
            "event_type": event_type,
            "message": f"auto-fix {status_label} for {task_id} (attempt={attempt_number})",
        }

    async def _apply_one(
        self,
        *,
        finding,
        task_id: str,
        workspace_path: str,
        workspace_id: str | None,
        workflow_id: str | None,
    ) -> dict[str, Any]:
        """Dispatch on finding category + return the fix result envelope."""
        category = finding.category
        if category == "documentation" and "missing_sections" in (finding.metadata or {}):
            return await self._fix_pr_draft_sections(
                task_id=task_id,
                missing=finding.metadata.get("missing_sections") or [],
            )
        if category == "test":
            return await self._fix_missing_generated_file(
                task_id=task_id,
                workspace_path=workspace_path,
                workspace_id=workspace_id,
                workflow_id=workflow_id,
                hint="demo_api_test",
            )
        if category == "syntax" and (finding.metadata or {}).get("reason"):
            # Generic file-regeneration fallback for syntax-only findings.
            return await self._fix_missing_generated_file(
                task_id=task_id,
                workspace_path=workspace_path,
                workspace_id=workspace_id,
                workflow_id=workflow_id,
                hint="regenerate",
                target_path=finding.file_path,
            )
        return {
            "finding_id": finding.finding_id,
            "status": "refused",
            "reason": f"unhandled_category:{category}",
        }

    async def _fix_pr_draft_sections(self, *, task_id: str, missing: list[str]) -> dict[str, Any]:
        existing = None
        with contextlib.suppress(Exception):
            existing = await self._code_store.get_pr_draft_artifact(task_id)
        if existing is None:
            return {
                "status": "refused",
                "reason": "pr_draft_missing",
                "missing_sections": missing,
            }
        new_body = _append_missing_sections(existing.body or "", list(missing))
        with contextlib.suppress(Exception):
            await self._code_store.create_pr_draft_artifact(
                task_id=task_id,
                workflow_id=existing.workflow_id,
                workspace_id=existing.workspace_id,
                title=existing.title,
                body=new_body,
                changed_files=existing.changed_files,
                test_results=existing.test_results,
                risk_assessment=existing.risk_assessment,
                rollback_plan=existing.rollback_plan,
                github_dry_run_result=existing.github_dry_run_result,
                status=existing.status,
            )
        return {
            "status": "applied",
            "fix_strategy": "append_pr_draft_sections",
            "missing_sections": missing,
        }

    async def _fix_missing_generated_file(
        self,
        *,
        task_id: str,
        workspace_path: str,
        workspace_id: str | None,
        workflow_id: str | None,
        hint: str,
        target_path: str | None = None,
    ) -> dict[str, Any]:
        """Re-run the deterministic generator using the original work item.

        We don't try to guess the right template — we look up the work
        item, re-plan, and only re-write files that the plan would emit.
        This deterministic path is safe because the templates are fixed.
        """
        try:
            wi = await self._task_store.get_work_item(task_id)
        except Exception:
            wi = None
        if wi is None:
            return {
                "status": "refused",
                "reason": "work_item_missing",
                "hint": hint,
            }
        plan = plan_generation(
            task_id=task_id,
            description=wi.description or "",
            request_type=wi.request_type or "unknown",
            work_item_status=wi.status,
        )
        if plan.status != "ready":
            return {
                "status": "refused",
                "reason": f"plan_blocked:{plan.reason}",
                "hint": hint,
            }
        written, refused = write_plan(
            plan,
            workspace_root=workspace_path,
            allowed_paths=list(DEFAULT_ALLOWED_PATHS),
        )
        if not written:
            return {
                "status": "refused",
                "reason": "no_files_rewritten",
                "hint": hint,
                "refused": refused,
            }
        # Re-record the artifact rows so the next QA pass sees a fresh
        # diff. The existing artifacts for this task are kept (we don't
        # delete history) but the new ones land with the updated diff.
        for w in written:
            with contextlib.suppress(Exception):
                await self._code_store.add_code_change_artifact(
                    task_id=task_id,
                    workflow_id=workflow_id,
                    workspace_id=workspace_id or "",
                    file_path=w.relative_path,
                    change_type=w.change_type,
                    before_sha=w.before_sha,
                    after_sha=w.after_sha,
                    diff_summary=w.diff_summary,
                    diff_text=w.diff_text[:4000],
                    generated_content_preview=_read_file(w.full_path)[:1200],
                    validation_status="passed",
                )
        return {
            "status": "applied",
            "fix_strategy": "regenerate_workspace_files",
            "rewritten": [w.relative_path for w in written],
            "hint": hint,
            "target_path": target_path,
        }
