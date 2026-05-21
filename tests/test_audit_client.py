from shared.models.audit import AuditEvent
from shared.sdk.audit.client import AuditClient


def test_build_audit_event():
    client = AuditClient()
    event = client.build_audit_event(
        agent="dummy-agent",
        decision_type="analysis",
        summary="analyzed task",
        result="ok",
        task_id="11111111-1111-1111-1111-111111111111",
        artifact_refs={"pr": "none"},
    )
    assert isinstance(event, AuditEvent)
    assert event.agent == "dummy-agent"
    assert event.decision_type == "analysis"
    assert event.summary == "analyzed task"
    assert event.result == "ok"
    assert event.artifact_refs == {"pr": "none"}
    assert event.task_id == "11111111-1111-1111-1111-111111111111"
    assert event.created_at is not None


def test_build_audit_event_defaults():
    client = AuditClient()
    event = client.build_audit_event(agent="a", decision_type="d", summary="s", result="r")
    assert event.task_id is None
    assert event.artifact_refs == {}


async def test_write_audit_event_without_bus_returns_none():
    client = AuditClient()
    event = client.build_audit_event(agent="a", decision_type="d", summary="s", result="r")
    assert await client.write_audit_event(event) is None
