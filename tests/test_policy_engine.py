from fastapi.testclient import TestClient

RESTRICTED = [
    "production.deploy",
    "production.config.change",
    "email.send",
    "contract.action",
    "cost.commitment",
    "security.policy.change",
    "production.data.delete",
    "secret.rotation",
]


def test_health(policy_engine_app):
    client = TestClient(policy_engine_app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_restricted_action_requires_approval(policy_engine_app):
    client = TestClient(policy_engine_app)
    body = client.post("/policy/evaluate", json={"action": "production.deploy"}).json()
    assert body["allowed"] is False
    assert body["approval_required"] is True
    assert body["risk_level"] == "high"
    assert body["reason"] == "restricted action"


def test_non_restricted_action_allowed(policy_engine_app):
    client = TestClient(policy_engine_app)
    body = client.post("/policy/evaluate", json={"action": "code.read"}).json()
    assert body["allowed"] is True
    assert body["approval_required"] is False
    assert body["risk_level"] == "low"


def test_all_restricted_actions_blocked(policy_engine_app):
    client = TestClient(policy_engine_app)
    for action in RESTRICTED:
        body = client.post("/policy/evaluate", json={"action": action}).json()
        assert body["allowed"] is False, action
        assert body["approval_required"] is True, action
        assert body["risk_level"] == "high", action
