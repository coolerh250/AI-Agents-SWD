from fastapi.testclient import TestClient

from main import app
from workflow import REQUIRED_STATE_FIELDS, build_workflow, run_mock_workflow, workflow_state_schema

client = TestClient(app)


async def test_non_production_workflow_completes():
    result = await run_mock_workflow(
        {
            "task_id": "wf-dev-1",
            "source": "test",
            "request": {"type": "dev.test", "description": "non-production"},
        }
    )
    assert result["stage"] == "completed"
    assert result["approval_required"] is False
    assert result["execution_result"]["production_executed"] is False


async def test_production_deploy_waits_for_approval():
    result = await run_mock_workflow(
        {
            "task_id": "wf-prod-1",
            "source": "test",
            "request": {"type": "production.deploy", "description": "production deploy"},
        }
    )
    assert result["approval_required"] is True
    assert result["stage"] == "waiting_approval"
    assert result["stage"] != "completed"
    assert result["execution_result"]["production_executed"] is False


async def test_policy_node_flags_restricted_action():
    result = await run_mock_workflow(
        {"task_id": "wf-sec", "source": "test", "request": {"type": "secret.rotation"}}
    )
    assert result["approval_required"] is True
    assert result["risk_level"] == "high"


async def test_audit_node_produces_audit_refs():
    result = await run_mock_workflow(
        {"task_id": "wf-audit", "source": "test", "request": {"type": "dev.test"}}
    )
    assert len(result["audit_refs"]) >= 1


def test_build_workflow_compiles():
    assert build_workflow() is not None


def test_workflow_schema_has_required_fields():
    schema = workflow_state_schema()
    for field in REQUIRED_STATE_FIELDS:
        assert field in schema


def test_health_returns_ok():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
