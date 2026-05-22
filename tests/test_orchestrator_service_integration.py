import uuid

import httpx
import pytest

from shared.sdk.event_bus.redis_streams import RedisStreamEventBus
from workflow import run_mock_workflow

APPROVAL_ENGINE = "http://localhost:8002"
AUDIT_SERVICE = "http://localhost:8003"


def _services_up() -> bool:
    for port in (8001, 8002, 8003):
        try:
            if httpx.get(f"http://localhost:{port}/health", timeout=3).status_code != 200:
                return False
        except Exception:
            return False
    return True


pytestmark = pytest.mark.skipif(
    not _services_up(),
    reason="governance services (policy/approval/audit) not reachable on localhost",
)


async def test_non_production_workflow_routes_through_services():
    task_id = f"int-dev-{uuid.uuid4().hex[:8]}"
    result = await run_mock_workflow(
        {
            "task_id": task_id,
            "source": "integration",
            "request": {"type": "dev.test", "description": "integration non-production"},
        }
    )
    # policy-engine answered: a non-restricted action runs to completion.
    assert result["approval_required"] is False
    assert result["stage"] == "completed"
    # audit-service recorded the event (real audit id, not the local fallback).
    assert len(result["audit_refs"]) >= 1
    assert not result["audit_refs"][0].startswith("audit-local:")

    audit = httpx.get(f"{AUDIT_SERVICE}/audit/events/{task_id}", timeout=5).json()
    assert audit["count"] >= 1


async def test_production_deploy_creates_approval_request():
    task_id = f"int-prod-{uuid.uuid4().hex[:8]}"
    result = await run_mock_workflow(
        {
            "task_id": task_id,
            "source": "integration",
            "request": {"type": "production.deploy", "description": "integration prod deploy"},
        }
    )
    # policy-engine flagged the restricted action; no production action runs.
    assert result["approval_required"] is True
    assert result["stage"] == "waiting_approval"
    assert result["execution_result"]["production_executed"] is False

    # approval-engine persisted the request (queryable from PostgreSQL).
    request_id = result["approval_request_id"]
    assert request_id and not request_id.startswith("approval-local:")
    approval = httpx.get(f"{APPROVAL_ENGINE}/approval/{request_id}", timeout=5)
    assert approval.status_code == 200
    body = approval.json()
    assert body["task_id"] == task_id
    assert body["status"] == "pending"
    assert body["action"] == "production.deploy"


async def test_workflow_publishes_to_redis_streams():
    bus = RedisStreamEventBus()
    try:
        try:
            audit_before = await bus.client.xlen("stream.audit")
            approvals_before = await bus.client.xlen("stream.approvals")
        except Exception:
            pytest.skip("no reachable Redis; skipping stream publish test")

        await run_mock_workflow(
            {
                "task_id": f"int-stream-{uuid.uuid4().hex[:8]}",
                "source": "integration",
                "request": {"type": "production.deploy", "description": "integration stream"},
            }
        )

        audit_after = await bus.client.xlen("stream.audit")
        approvals_after = await bus.client.xlen("stream.approvals")
    finally:
        await bus.close()

    assert audit_after > audit_before
    assert approvals_after > approvals_before
