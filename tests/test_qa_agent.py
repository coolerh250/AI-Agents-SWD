from fastapi.testclient import TestClient


def test_health(qa_agent):
    response = TestClient(qa_agent.app).get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_status(qa_agent):
    response = TestClient(qa_agent.app).get("/status")
    assert response.status_code == 200
    body = response.json()
    assert body["agent"] == "qa-agent"
    assert body["input_stream"] == "stream.qa"
    assert body["output_stream"] == "stream.deployments"
    assert body["group"] == "qa-agent-group"
    assert body["processed_count"] == 0


def test_build_report_produces_test_report(qa_agent):
    agent = qa_agent.QAAgent()
    report = agent.build_report({"task_id": "t-4"})
    assert report["artifact_type"] == "test_report"
    assert report["task_id"] == "t-4"
    assert report["status"] == "passed"
    assert report["tests_run"] == 0
    assert report["mock"] is True
