from fastapi.testclient import TestClient


def test_health(devops_agent):
    response = TestClient(devops_agent.app).get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_status(devops_agent):
    response = TestClient(devops_agent.app).get("/status")
    assert response.status_code == 200
    body = response.json()
    assert body["agent"] == "devops-agent"
    assert body["input_stream"] == "stream.deployments"
    assert body["group"] == "devops-agent-group"
    assert body["processed_count"] == 0


def test_build_deployment_record_is_mock_safe(devops_agent):
    agent = devops_agent.DevOpsAgent()
    record = agent.build_deployment_record({"task_id": "t-5"})
    assert record["artifact_type"] == "deployment_record"
    assert record["task_id"] == "t-5"
    assert record["environment"] == "test"
    assert record["status"] == "simulated"
    assert record["production_executed"] is False
    assert record["mock"] is True
