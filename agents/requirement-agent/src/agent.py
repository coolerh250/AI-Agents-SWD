"""Stage 27 — flexible task execution loop entry point.

The requirement-agent now does three things in addition to producing
the original ``requirement_spec`` artifact:

1. Creates / upserts a row in ``task_work_items`` (one per Discord
   intake) carrying the deterministic execution-mode classification
   result + the optional Scrum metadata.
2. Writes an ``agent_discussions`` row capturing the requirement-
   agent's analysis.
3. If the description signals "needs_clarification" (short / TBD /
   `?` / 請再確認 / 看不懂 …), the agent creates a
   ``clarification_requests`` row, publishes a notification + audit
   event, and DOES NOT publish to ``stream.development``. The
   orchestrator workflow consumer therefore never receives the
   requirement.completed event for this task; the workflow stays in
   the pre-development stage until ``/workflow/resume-after-
   clarification/{task_id}`` is called.
4. If the description is sufficient, the agent marks the work item
   ``ready_for_development``, publishes a ``task.ready_for_development``
   notification, writes the matching audit row, and publishes the
   ``requirement.completed`` event so the rest of the agent pipeline
   runs.

No LLM call is made anywhere. The classification rules live in
``shared.sdk.task_execution.mode_classifier`` and are deterministic.
"""

from __future__ import annotations

from shared.sdk.base_agent.stream_agent import StreamAgent
from shared.sdk.observability.metrics import (
    AGENT_DISCUSSIONS_TOTAL,
    CLARIFICATION_REQUESTS_TOTAL,
    TASK_EXECUTION_MODE_TOTAL,
    TASK_READY_FOR_DEVELOPMENT_TOTAL,
    TASK_WORK_ITEMS_TOTAL,
)
from shared.sdk.observability.tracing import start_span
from shared.sdk.task_execution import (
    TaskExecutionStore,
    classify_execution_mode,
)


class RequirementAgent(StreamAgent):
    """Stage 27 requirement-agent — deterministic, no LLM."""

    name = "requirement-agent"
    input_stream = "stream.requirements"
    output_stream = "stream.development"
    group = "requirement-agent-group"
    consumer = "requirement-agent-1"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._store = TaskExecutionStore()

    def build_artifact(self, payload: dict) -> dict:
        task_id = str(payload.get("task_id", "unknown"))
        request = payload.get("request", {})
        summary = request.get("description") or f"requirement analysis for {task_id}"
        return {
            "type": "requirement_spec",
            "task_id": task_id,
            "request_type": payload.get("request_type") or request.get("type", "unknown"),
            "summary": summary,
            "acceptance_criteria": [
                "input is validated",
                "the happy path is covered",
                "errors are handled gracefully",
            ],
            "produced_by": self.name,
            "mock": True,
        }

    async def handle(self, payload: dict) -> dict:
        task_id = str(payload.get("task_id", "unknown"))
        workflow_id = str(payload.get("workflow_id", "")) or None
        request = payload.get("request", {}) if isinstance(payload.get("request"), dict) else {}
        description = str(request.get("description") or "")
        request_type = str(request.get("type") or payload.get("request_type") or "unknown")
        discord_block = request.get("discord") if isinstance(request.get("discord"), dict) else {}
        github_block = request.get("github") if isinstance(request.get("github"), dict) else None

        # 1) deterministic classification ---------------------------------
        with start_span(
            "task_execution.classify_mode",
            **{
                "service.name": self.name,
                "task_id": task_id,
                "workflow_id": workflow_id or "",
            },
        ):
            classification = classify_execution_mode(
                request_type=request_type,
                description=description,
                github_options=github_block,
                explicit_mode=str(request.get("execution_mode") or "") or None,
                message_content=str(request.get("raw_content") or ""),
            )
        TASK_EXECUTION_MODE_TOTAL.labels(
            execution_mode=classification.execution_mode,
            request_type=request_type or "unknown",
        ).inc()

        status = (
            "needs_clarification"
            if classification.clarification_required
            else "ready_for_development"
        )

        title = description.strip()[:80] or f"Discord task {task_id}"
        assumptions: list[str] = []
        open_questions: list[str] = []
        risks: list[str] = []
        execution_plan: dict = {
            "stages": ["intake", "requirement", "development", "qa", "devops"],
            "production_executed": False,
            "mock": True,
            "reason": classification.reason,
        }
        acceptance_criteria = None
        definition_of_done = None
        scrum_metadata = None
        if classification.execution_mode == "scrum_project":
            acceptance_criteria = [
                "Scrum project kickoff acknowledged",
                "Initial backlog placeholder created",
                "Acceptance criteria authored by the team",
            ]
            definition_of_done = [
                "All sprint items meet the team's DoD",
                "Stakeholder demo scheduled",
                "Retrospective notes captured",
            ]
            scrum_metadata = {
                "project_kickoff": True,
                "sprint": "TBD",
                "backlog": "placeholder",
            }
            risks.append("Scrum vocabulary detected — confirm team adopts the cadence")

        if classification.clarification_required:
            open_questions.append(
                "Description is too short / unclear — please provide more detail "
                "about the goal, the inputs, and the expected outputs."
            )

        # 2) upsert work item --------------------------------------------
        work_item = await self._store.create_work_item(
            task_id=task_id,
            workflow_id=workflow_id,
            title=title,
            description=description,
            request_type=request_type,
            execution_mode=classification.execution_mode,
            status=status,
            source=str(payload.get("source") or "discord"),
            requester_id=str(discord_block.get("user_id") or "") or None,
            channel_id=str(discord_block.get("channel_id") or "") or None,
            task_category="scrum" if classification.scrum_enabled else "general",
            development_required=classification.development_required,
            github_required=classification.github_required,
            clarification_required=classification.clarification_required,
            acceptance_criteria=acceptance_criteria,
            definition_of_done=definition_of_done,
            execution_plan=execution_plan,
            assumptions=assumptions,
            open_questions=open_questions,
            risks=risks,
            scrum_enabled=classification.scrum_enabled,
            scrum_metadata=scrum_metadata,
        )
        TASK_WORK_ITEMS_TOTAL.labels(
            execution_mode=classification.execution_mode, status=status
        ).inc()

        # 3) record the requirement-agent discussion ----------------------
        discussion_content = (
            f"requirement-agent classified task {task_id} as "
            f"{classification.execution_mode}. development_required="
            f"{classification.development_required} "
            f"clarification_required={classification.clarification_required}."
        )
        await self._store.add_agent_discussion(
            task_id=task_id,
            workflow_id=workflow_id,
            agent=self.name,
            role="analyst",
            message_type="analysis",
            content=discussion_content,
            confidence=0.8 if not classification.clarification_required else 0.4,
            references={
                "execution_mode": classification.execution_mode,
                "reason": classification.reason,
                "work_item_id": work_item.work_item_id,
            },
        )
        AGENT_DISCUSSIONS_TOTAL.labels(agent=self.name, message_type="analysis").inc()

        # 4) branch on clarification --------------------------------------
        if classification.clarification_required:
            with start_span(
                "task_execution.create_clarification",
                **{
                    "service.name": self.name,
                    "task_id": task_id,
                    "workflow_id": workflow_id or "",
                },
            ):
                clar = await self._store.create_clarification_request(
                    task_id=task_id,
                    workflow_id=workflow_id,
                    question=open_questions[0],
                    requested_by_agent=self.name,
                    channel_id=str(discord_block.get("channel_id") or "") or None,
                    message_id=str(discord_block.get("message_id") or "") or None,
                )
            CLARIFICATION_REQUESTS_TOTAL.labels(status="requested").inc()
            # IMPORTANT: do NOT publish to stream.development. The workflow
            # event consumer will not receive a requirement.completed event
            # and the orchestrator's workflow_states.stage stays
            # in_progress (StreamAgent.process already wrote audit +
            # notification for the agent run itself; we add a second
            # audit row tagged ``clarification_requested`` below).
            return {
                "task_id": task_id,
                "decision_type": "clarification_requested",
                "summary": (
                    f"requirement-agent requested clarification for {task_id} "
                    f"(reason: {classification.reason})"
                ),
                "result": "needs_clarification",
                "artifact_refs": {
                    "execution_mode": classification.execution_mode,
                    "clarification_id": clar.clarification_id,
                    "work_item_id": work_item.work_item_id,
                    "production_executed": False,
                },
                "event_type": "task.needs_clarification",
                "message": (f"task {task_id} needs clarification: {open_questions[0]}"),
            }

        # 5) ready_for_development path ----------------------------------
        TASK_READY_FOR_DEVELOPMENT_TOTAL.labels(execution_mode=classification.execution_mode).inc()
        artifact = self.build_artifact(payload)
        message = {
            "event": "requirement.completed",
            **self.correlation_ids(payload),
            "request": payload.get("request", {}),
            "artifact": artifact,
            "produced_by": self.name,
            "task_execution": {
                "execution_mode": classification.execution_mode,
                "scrum_enabled": classification.scrum_enabled,
                "work_item_id": work_item.work_item_id,
                "status": status,
            },
        }
        await self.publish_next(message)
        return {
            "task_id": task_id,
            "decision_type": "task_ready_for_development",
            "summary": (
                f"requirement-agent marked {task_id} ready_for_development "
                f"(mode={classification.execution_mode})"
            ),
            "result": "ready_for_development",
            "artifact_refs": {
                "execution_mode": classification.execution_mode,
                "work_item_id": work_item.work_item_id,
                "production_executed": False,
            },
            "event_type": "task.ready_for_development",
            "message": (
                f"task {task_id} ready for development " f"(mode={classification.execution_mode})"
            ),
        }
