from fastapi.testclient import TestClient


def test_health(development_agent):
    response = TestClient(development_agent.app).get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_status(development_agent):
    response = TestClient(development_agent.app).get("/status")
    assert response.status_code == 200
    body = response.json()
    assert body["agent"] == "development-agent"
    assert body["input_stream"] == "stream.development"
    assert body["output_stream"] == "stream.qa"
    assert body["group"] == "development-agent-group"
    assert body["processed_count"] == 0


def test_build_artifact_produces_code_change(development_agent):
    agent = development_agent.DevelopmentAgent()
    artifact = agent.build_artifact({"task_id": "t-3"})
    assert artifact["artifact_type"] == "code_change"
    assert artifact["task_id"] == "t-3"
    assert artifact["files_changed"] == []
    assert artifact["mock"] is True
