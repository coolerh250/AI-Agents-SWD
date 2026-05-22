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


async def test_receive_task_normalizes(intake_agent):
    agent = intake_agent.IntakeAgent()
    normalized = await agent.receive_task(
        {"task_id": "t-1", "source": "test", "request": {"type": "dev.test"}}
    )
    assert normalized["task_id"] == "t-1"
    assert normalized["normalized"] is True
    assert normalized["received_by"] == "intake-agent"


async def test_analyze_extracts_request_type(intake_agent):
    agent = intake_agent.IntakeAgent()
    analysis = await agent.analyze(
        {"task_id": "t-1", "request": {"type": "production.deploy", "description": "d"}}
    )
    assert analysis["request_type"] == "production.deploy"
    assert analysis["description"] == "d"
