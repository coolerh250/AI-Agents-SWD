"""Step 57 -- work-item / dispatch domain models."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

WorkType = Literal[
    "requirement",
    "planning",
    "architecture",
    "design_review",
    "implementation",
    "backend",
    "frontend",
    "qa",
    "verification",
    "deployment_simulation",
    "devops",
    "delivery_package",
    "notification",
]


class WorkItemCreate(BaseModel):
    project_id: UUID
    title: str
    description: str | None = None
    work_type: str = "task"
    priority: Literal["low", "medium", "high", "critical"] = "medium"
    item_source: str | None = None
    requested_by: str | None = None
    requires_human_approval: bool = False
    production_effect: bool = False


class WorkItem(BaseModel):
    id: UUID
    project_id: UUID
    work_item_key: str | None = None
    title: str
    description: str | None = None
    work_type: str | None = None
    priority: str = "medium"
    lifecycle_state: str = "created"
    assigned_agent: str | None = None
    assigned_role: str | None = None
    requires_human_approval: bool = False
    production_effect: bool = False
    delivery_package_id: UUID | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    completed_at: datetime | None = None


class Dispatch(BaseModel):
    id: UUID
    project_id: UUID
    work_item_id: UUID
    dispatch_key: str
    target_agent: str
    target_stream: str
    status: str = "pending"
    attempt: int = 1
    correlation_id: str | None = None
    production_effect: bool = False
    created_at: datetime | None = None
    completed_at: datetime | None = None
    failure_reason: str | None = None


class WorkItemEvent(BaseModel):
    id: UUID
    project_id: UUID
    work_item_id: UUID
    event_type: str
    from_state: str | None = None
    to_state: str | None = None
    actor: str | None = None
    role: str | None = None
    reason: str | None = None
    correlation_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None
