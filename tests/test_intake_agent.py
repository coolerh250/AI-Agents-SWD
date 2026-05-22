from fastapi.testclient import TestClient


def test_health(intake_agent):
    response = TestClient(intake_agent.app).get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_status(intake_agent):
    response = TestClient(intake_agent.app).get("/status")
    assert response.status_code == 200
    body = response.json()
    assert body["agent"] == "intake-agent"
    assert body["input_stream"] == "stream.tasks"
    assert body["output_stream"] == "stream.requirements"
    assert body["group"] == "intake-agent-group"
    assert body["processed_count"] == 0
    assert body["failed_count"] == 0


def test_build_message_normalizes(intake_agent):
    agent = intake_agent.IntakeAgent()
    message = agent.build_message(
        {"task_id": "t-1", "source": "test", "request": {"type": "dev.test"}}
    )
    assert message["event"] == "task.intake_completed"
    assert message["task_id"] == "t-1"
    assert message["request_type"] == "dev.test"
    assert message["normalized_by"] == "intake-agent"
