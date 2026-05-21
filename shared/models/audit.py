from datetime import datetime, timezone

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AuditEvent(BaseModel):
    task_id: str | None = None
    agent: str
    decision_type: str
    summary: str
    result: str
    artifact_refs: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=_utcnow)
