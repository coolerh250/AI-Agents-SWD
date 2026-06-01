"""Dataclasses mirroring the Stage 27 tables.

These are plain dataclasses (not pydantic) — they're serialized via
``to_dict`` so /operations/* and tests can compare deeply.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TaskWorkItem:
    """One row from ``task_work_items``.

    The Stage 27 platform creates exactly one work item per Discord
    intake; the row is upserted on subsequent agent passes.
    """

    work_item_id: str
    task_id: str
    workflow_id: str | None = None
    title: str = ""
    description: str = ""
    request_type: str = "unknown"
    execution_mode: str = "simple_task"
    status: str = "intake_received"
    priority: str = "normal"
    source: str = "discord"
    requester_id: str | None = None
    channel_id: str | None = None
    task_category: str = "general"
    development_required: bool = False
    github_required: bool = False
    clarification_required: bool = False
    acceptance_criteria: list[Any] | None = None
    definition_of_done: list[Any] | None = None
    execution_plan: dict[str, Any] = field(default_factory=dict)
    assumptions: list[Any] = field(default_factory=list)
    open_questions: list[Any] = field(default_factory=list)
    risks: list[Any] = field(default_factory=list)
    scrum_enabled: bool = False
    scrum_metadata: dict[str, Any] | None = None
    created_at: str | None = None
    updated_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "work_item_id": self.work_item_id,
            "task_id": self.task_id,
            "workflow_id": self.workflow_id,
            "title": self.title,
            "description": self.description,
            "request_type": self.request_type,
            "execution_mode": self.execution_mode,
            "status": self.status,
            "priority": self.priority,
            "source": self.source,
            "requester_id": self.requester_id,
            "channel_id": self.channel_id,
            "task_category": self.task_category,
            "development_required": self.development_required,
            "github_required": self.github_required,
            "clarification_required": self.clarification_required,
            "acceptance_criteria": self.acceptance_criteria,
            "definition_of_done": self.definition_of_done,
            "execution_plan": dict(self.execution_plan),
            "assumptions": list(self.assumptions),
            "open_questions": list(self.open_questions),
            "risks": list(self.risks),
            "scrum_enabled": self.scrum_enabled,
            "scrum_metadata": self.scrum_metadata,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class AgentDiscussion:
    """One row from ``agent_discussions`` — append-only discussion log."""

    discussion_id: str
    task_id: str
    workflow_id: str | None
    agent: str
    role: str
    message_type: str
    content: str
    confidence: float = 0.5
    references: dict[str, Any] = field(default_factory=dict)
    created_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "discussion_id": self.discussion_id,
            "task_id": self.task_id,
            "workflow_id": self.workflow_id,
            "agent": self.agent,
            "role": self.role,
            "message_type": self.message_type,
            "content": self.content,
            "confidence": float(self.confidence),
            "references": dict(self.references),
            "created_at": self.created_at,
        }


@dataclass
class ClarificationRequest:
    """One row from ``clarification_requests``."""

    clarification_id: str
    task_id: str
    workflow_id: str | None
    question: str
    requested_by_agent: str = "requirement-agent"
    status: str = "open"
    user_response: str | None = None
    channel_id: str | None = None
    message_id: str | None = None
    created_at: str | None = None
    answered_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "clarification_id": self.clarification_id,
            "task_id": self.task_id,
            "workflow_id": self.workflow_id,
            "question": self.question,
            "requested_by_agent": self.requested_by_agent,
            "status": self.status,
            "user_response": self.user_response,
            "channel_id": self.channel_id,
            "message_id": self.message_id,
            "created_at": self.created_at,
            "answered_at": self.answered_at,
        }
