from datetime import datetime, timezone
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class WorkflowState(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    task_id: UUID | None = None
    phase: str
    state: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)
