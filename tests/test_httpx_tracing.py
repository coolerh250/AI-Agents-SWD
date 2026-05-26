import httpx
import pytest

from shared.sdk.http_clients.approval_http_client import ApprovalHttpClient
from shared.sdk.http_clients.audit_http_client import AuditHttpClient
from shared.sdk.http_clients.policy_http_client import PolicyHttpClient


def test_policy_http_client_accepts_trace_attributes():
    # The instrumentation extension widened the signature with task_id / workflow_id
    # — older callers must still work, new keyword args must be accepted.
    client = PolicyHttpClient(base_url="http://policy-engine:8001")
    assert client.base_url == "http://policy-engine:8001"
    import inspect

    sig = inspect.signature(client.evaluate)
    assert "task_id" in sig.parameters
    assert "workflow_id" in sig.parameters


def test_approval_http_client_accepts_trace_attributes():
    client = ApprovalHttpClient(base_url="http://approval-engine:8002")
    import inspect

    sig = inspect.signature(client.request_approval)
    assert "workflow_id" in sig.parameters


def test_audit_http_client_accepts_trace_attributes():
    client = AuditHttpClient(base_url="http://audit-service:8003")
    import inspect

    sig = inspect.signature(client.record_event)
    assert "workflow_id" in sig.parameters


def _services_up() -> bool:
    for url in (
        "http://localhost:8001/health",
        "http://localhost:8002/health",
        "http://localhost:8003/health",
    ):
        try:
            if httpx.get(url, timeout=3).status_code != 200:
                return False
        except Exception:
            return False
    return True


requires_services = pytest.mark.skipif(
    not _services_up(), reason="policy/approval/audit services not reachable on localhost"
)


@requires_services
async def test_policy_evaluate_still_works_under_tracing():
    """Custom span wrapping must not break the actual HTTP call."""
    result = await PolicyHttpClient().evaluate(
        "dev.test", task_id="trace-httpx-smoke", workflow_id="wf-trace-httpx"
    )
    assert "allowed" in result
    assert "approval_required" in result


@requires_services
async def test_audit_record_event_still_works_under_tracing():
    result = await AuditHttpClient().record_event(
        task_id="trace-httpx-audit",
        agent="trace-tests",
        decision_type="trace",
        summary="httpx tracing smoke",
        result="ok",
        artifact_refs={"smoke": "true"},
        workflow_id="wf-trace-httpx-audit",
    )
    assert result.get("audit_id")
