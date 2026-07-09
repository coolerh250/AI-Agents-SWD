"""Step 66B.1 -- task API request/response models.

Full lifecycle enum defined per the Step 66A.3 task-lifecycle-model blueprint; only
draft/submitted/intake_review/blocked/canceled are reachable via the 66B.1 API surface.
"""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

TaskType = Literal[
    "software_delivery",
    "documentation",
    "platform_improvement",
    "research",
    "it_operations",
    "security_review",
    "incident_analysis",
    "data_knowledge_analysis",
    "business_process_automation",
    "other",
]

# MVP first-class task types (Step 66A.2 D2 / D6). Anything else is accepted but
# forced intake_planning_only=true -- no specialized pipeline runs on it yet.
FIRST_CLASS_TASK_TYPES: frozenset[str] = frozenset(
    {"software_delivery", "documentation", "platform_improvement"}
)

TaskPriority = Literal["low", "medium", "high", "critical"]

TaskStatus = Literal[
    "draft",
    "submitted",
    "intake_review",
    "clarification_needed",
    "clarification_expired",
    "approved_for_execution",
    "running",
    "waiting_approval",
    "blocked",
    "failed",
    "delivery_ready",
    "changes_requested",
    "qa_rerun_requested",
    "accepted",
    "rejected",
    "archived",
    "canceled",
]

# States reachable through the 66B.1 API (create / submit). The full TaskStatus
# enum above is defined now for later stages (66C+).
TASK_ENVIRONMENTS: frozenset[str] = frozenset({"test", "staging"})


class TaskCreate(BaseModel):
    title: str = Field(min_length=1)
    description: str | None = None
    task_type: TaskType
    priority: TaskPriority = "medium"
    owner: str | None = None
    project_id: UUID | None = None
    environment: Literal["test", "staging"] = "test"
    # Accepted but never executed -- see task_api.py create_task(): forces
    # requires_approval=true and a non-dispatchable status. Never rejected outright
    # so the policy decision itself is recorded (task.rejected_by_policy).
    production_effect: bool = False
    requires_approval: bool = False
    initial_status: Literal["draft", "submitted"] = "draft"
    metadata: dict[str, Any] = Field(default_factory=dict)


class Task(BaseModel):
    id: UUID
    title: str
    description: str | None = None
    task_type: TaskType
    priority: TaskPriority
    status: TaskStatus
    created_by: str
    owner: str | None = None
    project_id: UUID | None = None
    environment: str
    production_effect: bool
    requires_approval: bool
    clarification_status: str
    delivery_status: str
    intake_planning_only: bool
    correlation_id: UUID
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str | None = None
    updated_at: str | None = None


__all__ = [
    "TaskType",
    "FIRST_CLASS_TASK_TYPES",
    "TaskPriority",
    "TaskStatus",
    "TASK_ENVIRONMENTS",
    "TaskCreate",
    "Task",
]
