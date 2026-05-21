from typing import TYPE_CHECKING

from shared.models.audit import AuditEvent

if TYPE_CHECKING:
    from shared.sdk.event_bus.redis_streams import RedisStreamEventBus


class AuditClient:
    """Builds audit events and publishes them to the audit stream."""

    AUDIT_STREAM = "stream.audit"

    def __init__(self, event_bus: "RedisStreamEventBus | None" = None) -> None:
        self.event_bus = event_bus

    def build_audit_event(
        self,
        agent: str,
        decision_type: str,
        summary: str,
        result: str,
        task_id: str | None = None,
        artifact_refs: dict | None = None,
    ) -> AuditEvent:
        return AuditEvent(
            task_id=task_id,
            agent=agent,
            decision_type=decision_type,
            summary=summary,
            result=result,
            artifact_refs=artifact_refs or {},
        )

    async def write_audit_event(self, event: AuditEvent) -> str | None:
        if self.event_bus is None:
            return None
        return await self.event_bus.publish_event(self.AUDIT_STREAM, event.model_dump(mode="json"))
