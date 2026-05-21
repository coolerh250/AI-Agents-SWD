import json

from shared.models.audit import AuditEvent
from shared.models.events import AgentEvent, TaskCreatedEvent
from shared.models.workflow import WorkflowState


def test_workflow_state():
    ws = WorkflowState(phase="intake", state={"step": 1})
    assert ws.phase == "intake"
    assert ws.state == {"step": 1}
    assert ws.id is not None
    dumped = ws.model_dump(mode="json")
    assert dumped["phase"] == "intake"
    assert json.loads(ws.model_dump_json())["phase"] == "intake"


def test_agent_event():
    ev = AgentEvent(event_type="agent.started", agent="dummy-agent")
    assert ev.event_type == "agent.started"
    assert ev.agent == "dummy-agent"
    assert ev.event_id
    assert ev.model_dump(mode="json")["agent"] == "dummy-agent"


def test_task_created_event():
    ev = TaskCreatedEvent(task_id="t-123", title="Build feature")
    assert ev.event_type == "task.created"
    assert ev.title == "Build feature"
    parsed = TaskCreatedEvent.model_validate(json.loads(ev.model_dump_json()))
    assert parsed.task_id == "t-123"


def test_audit_event():
    ev = AuditEvent(
        agent="dummy-agent",
        decision_type="analysis",
        summary="s",
        result="ok",
        artifact_refs={"x": "y"},
    )
    assert ev.agent == "dummy-agent"
    assert ev.artifact_refs == {"x": "y"}
    assert ev.created_at is not None
    assert json.loads(ev.model_dump_json())["result"] == "ok"
