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


def test_build_artifact_produces_requirement_spec(requirement_agent):
    agent = requirement_agent.RequirementAgent()
    artifact = agent.build_artifact(
        {"task_id": "t-2", "request": {"type": "dev.test", "description": "build it"}}
    )
    assert artifact["type"] == "requirement_spec"
    assert artifact["task_id"] == "t-2"
    assert artifact["summary"] == "build it"
    assert artifact["mock"] is True
    assert len(artifact["acceptance_criteria"]) >= 1
