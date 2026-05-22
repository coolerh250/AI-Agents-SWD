from fastapi.testclient import TestClient


def test_health(requirement_agent):
    response = TestClient(requirement_agent.app).get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_status(requirement_agent):
    response = TestClient(requirement_agent.app).get("/status")
    assert response.status_code == 200
    body = response.json()
    assert body["agent"] == "requirement-agent"
    assert body["input_stream"] == "stream.requirements"
    assert body["output_stream"] == "stream.development"
    assert body["group"] == "requirement-agent-group"
    assert body["processed_count"] == 0


async def test_receive_task_extracts_request_type(requirement_agent):
    agent = requirement_agent.RequirementAgent()
    received = await agent.receive_task(
        {"task_id": "t-2", "request_type": "dev.test", "request": {"type": "dev.test"}}
    )
    assert received["task_id"] == "t-2"
    assert received["request_type"] == "dev.test"


async def test_analyze_produces_summary(requirement_agent):
    agent = requirement_agent.RequirementAgent()
    analysis = await agent.analyze(
        {"task_id": "t-2", "request_type": "dev.test", "request": {"description": "build it"}}
    )
    assert analysis["task_id"] == "t-2"
    assert analysis["summary"] == "build it"
