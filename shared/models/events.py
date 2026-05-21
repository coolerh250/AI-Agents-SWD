from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return str(uuid4())


class AgentEvent(BaseModel):
    event_id: str = Field(default_factory=_new_id)
    event_type: str
    agent: str
    task_id: str | None = None
    payload: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=_utcnow)


class TaskCreatedEvent(BaseModel):
    event_id: str = Field(default_factory=_new_id)
    event_type: str = "task.created"
    task_id: str
    title: str
    description: str | None = None
    created_at: datetime = Field(default_factory=_utcnow)
