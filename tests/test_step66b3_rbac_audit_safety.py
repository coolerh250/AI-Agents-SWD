"""Step 66B.3 -- RBAC / audit / safety hardening tests.

Loads task_api.py in isolation (mounted alone on a bare FastAPI()), with the
module-level _store()/_audit() monkeypatched to an in-memory fake -- no real DB,
no Redis, no external call. Mirrors tests/test_step66b1_task_api_foundation.py's
harness and extends it with: missing_actor/missing_role/invalid_role as distinct
fail-closed codes, task_rbac_denied audit evidence on every 403, own-task scoping,
Platform Admin view-all, production_effect=true blocked/not-dispatched, and static
no-dispatch / no-external-integration source checks.
"""

from __future__ import annotations

import importlib.util
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

_ORCH_SRC = Path(__file__).resolve().parents[1] / "apps" / "orchestrator" / "src"
_TASK_API_SRC = _ORCH_SRC / "task_api.py"


def _load() -> ModuleType:
    sys.path.insert(0, str(_ORCH_SRC))
    try:
        spec = importlib.util.spec_from_file_location("orchestrator_task_api_b3", _TASK_API_SRC)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        if str(_ORCH_SRC) in sys.path:
            sys.path.remove(str(_ORCH_SRC))


class InMemoryTaskStore:
    def __init__(self) -> None:
        self.rows: dict[str, dict[str, Any]] = {}

    async def create_task(self, **kwargs: Any) -> dict[str, Any]:
        task_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        row = {
            "id": task_id,
            "correlation_id": str(uuid.uuid4()),
            "description": kwargs.get("description"),
            "clarification_status": "none",
            "delivery_status": "none",
            "created_at": now,
            "updated_at": now,
            **{k: v for k, v in kwargs.items() if k != "description"},
        }
        self.rows[task_id] = row
        return dict(row)

    async def get_task(self, task_id: str) -> dict[str, Any] | None:
        row = self.rows.get(task_id)
        return dict(row) if row else None

    async def list_tasks(self, **filters: Any) -> list[dict[str, Any]]:
        out = []
        for row in self.rows.values():
            if all(row.get(k) == v for k, v in filters.items() if v is not None):
                out.append(dict(row))
        return out

    async def update_status(self, task_id: str, new_status: str) -> dict[str, Any]:
        row = self.rows[task_id]
        row["status"] = new_status
        row["updated_at"] = datetime.now(timezone.utc).isoformat()
        return dict(row)


class AuditRecorder:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str, dict[str, Any]]] = []

    async def __call__(
        self, decision_type: str, summary: str, result: str, refs: dict[str, Any]
    ) -> None:
        self.calls.append((decision_type, summary, result, refs))


@pytest.fixture
def wired(monkeypatch):
    module = _load()
    monkeypatch.setenv("TASK_API_TEST_AUTH_ENABLED", "true")
    store = InMemoryTaskStore()
    audit = AuditRecorder()
    monkeypatch.setattr(module, "_store", lambda: store)
    monkeypatch.setattr(module, "_audit", audit)
    app = FastAPI()
    app.include_router(module.router)
    client = TestClient(app)
    return module, store, audit, client


def _hdr(role: str | None, actor: str | None = "u1") -> dict[str, str]:
    headers: dict[str, str] = {}
    if actor is not None:
        headers["X-Task-Actor"] = actor
    if role is not None:
        headers["X-Task-Role"] = role
    return headers


def _payload(**overrides: Any) -> dict[str, Any]:
    body = {"title": "Build the thing", "task_type": "software_delivery"}
    body.update(overrides)
    return body


# -- Fail-closed auth: missing actor / missing role / invalid role -----------------


def test_missing_actor_denied(wired) -> None:
    _, _, _, client = wired
    resp = client.post("/tasks", json=_payload(), headers=_hdr("requester", actor=None))
    assert resp.status_code == 401
    assert resp.json()["detail"] == "missing_actor"


def test_missing_role_denied(wired) -> None:
    _, _, _, client = wired
    resp = client.post("/tasks", json=_payload(), headers=_hdr(None))
    assert resp.status_code == 401
    assert resp.json()["detail"] == "missing_role"


def test_invalid_role_denied(wired) -> None:
    _, _, _, client = wired
    resp = client.post("/tasks", json=_payload(), headers=_hdr("not_a_role"))
    assert resp.status_code == 401
    assert resp.json()["detail"] == "invalid_role"


def test_missing_role_distinct_from_invalid_role(wired) -> None:
    """Step 66B.3 hardening: these were previously both 'invalid_role'."""
    _, _, _, client = wired
    missing = client.post("/tasks", json=_payload(), headers=_hdr(None)).json()["detail"]
    invalid = client.post("/tasks", json=_payload(), headers=_hdr("bogus")).json()["detail"]
    assert missing == "missing_role"
    assert invalid == "invalid_role"
    assert missing != invalid


# -- RBAC scoping: Requester own-task, Platform Admin view-all ---------------------


def test_requester_creates_own_task(wired) -> None:
    _, _, _, client = wired
    resp = client.post("/tasks", json=_payload(), headers=_hdr("requester", actor="alice"))
    assert resp.status_code == 201
    assert resp.json()["created_by"] == "alice"


def test_requester_views_own_task(wired) -> None:
    _, _, _, client = wired
    created = client.post(
        "/tasks", json=_payload(), headers=_hdr("requester", actor="alice")
    ).json()
    resp = client.get(f"/tasks/{created['id']}", headers=_hdr("requester", actor="alice"))
    assert resp.status_code == 200
    assert resp.json()["dispatch_enabled"] is False


def test_requester_cannot_view_other_actor_task(wired) -> None:
    _, _, audit, client = wired
    created = client.post(
        "/tasks", json=_payload(), headers=_hdr("requester", actor="alice")
    ).json()
    resp = client.get(f"/tasks/{created['id']}", headers=_hdr("requester", actor="bob"))
    assert resp.status_code == 403
    assert resp.json()["detail"] == "not_own_task"
    denied = [c for c in audit.calls if c[0] == "task_rbac_denied"]
    assert denied, "task_rbac_denied audit event not emitted"
    assert denied[-1][3]["status"] == "not_own_task"
    assert denied[-1][3]["actor"] == "bob"


def test_requester_submits_own_draft(wired) -> None:
    _, _, _, client = wired
    created = client.post(
        "/tasks", json=_payload(), headers=_hdr("requester", actor="alice")
    ).json()
    resp = client.post(f"/tasks/{created['id']}/submit", headers=_hdr("requester", actor="alice"))
    assert resp.status_code == 200
    assert resp.json()["status"] == "intake_review"


def test_requester_cannot_submit_other_actor_draft(wired) -> None:
    _, _, audit, client = wired
    created = client.post(
        "/tasks", json=_payload(), headers=_hdr("requester", actor="alice")
    ).json()
    resp = client.post(f"/tasks/{created['id']}/submit", headers=_hdr("requester", actor="bob"))
    assert resp.status_code == 403
    assert resp.json()["detail"] == "not_own_task"
    assert any(c[0] == "task_rbac_denied" for c in audit.calls)


def test_platform_admin_views_all_tasks(wired) -> None:
    _, _, _, client = wired
    client.post("/tasks", json=_payload(), headers=_hdr("requester", actor="alice"))
    client.post("/tasks", json=_payload(), headers=_hdr("requester", actor="bob"))
    resp = client.get("/tasks", headers=_hdr("platform_admin", actor="admin1"))
    assert resp.status_code == 200
    assert resp.json()["count"] == 2


def test_reviewer_approver_cannot_create_task(wired) -> None:
    """Documented RBAC boundary: reviewer_approver is not in the create-roles set."""
    _, _, audit, client = wired
    resp = client.post("/tasks", json=_payload(), headers=_hdr("reviewer_approver"))
    assert resp.status_code == 403
    assert resp.json()["detail"] == "role_cannot_create_task"
    assert any(c[0] == "task_rbac_denied" for c in audit.calls)


# -- production_effect=true: blocked / approval-required, never dispatched ---------


def test_production_effect_true_blocked_and_not_dispatched(wired) -> None:
    _, _, audit, client = wired
    resp = client.post(
        "/tasks",
        json=_payload(production_effect=True, initial_status="submitted"),
        headers=_hdr("platform_admin"),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "blocked"
    assert body["requires_approval"] is True
    assert body["dispatch_enabled"] is False
    decision_types = [c[0] for c in audit.calls]
    assert "task_rejected_by_policy" in decision_types
    for _, _, _, refs in audit.calls:
        assert refs.get("workflow_dispatched") is False
        assert refs.get("production_executed") is False


def test_get_task_dispatch_enabled_always_false(wired) -> None:
    _, _, _, client = wired
    created = client.post("/tasks", json=_payload(), headers=_hdr("requester")).json()
    resp = client.get(f"/tasks/{created['id']}", headers=_hdr("requester"))
    assert resp.json()["dispatch_enabled"] is False


# -- Audit evidence -----------------------------------------------------------------


def test_task_created_audit_event(wired) -> None:
    _, _, audit, client = wired
    client.post("/tasks", json=_payload(), headers=_hdr("requester"))
    assert audit.calls[0][0] == "task_created"


def test_task_submitted_audit_event(wired) -> None:
    _, _, audit, client = wired
    created = client.post("/tasks", json=_payload(), headers=_hdr("requester")).json()
    client.post(f"/tasks/{created['id']}/submit", headers=_hdr("requester"))
    assert any(c[0] == "task_submitted" for c in audit.calls)


def test_task_rejected_by_policy_audit_event(wired) -> None:
    _, _, audit, client = wired
    client.post(
        "/tasks",
        json=_payload(production_effect=True, initial_status="submitted"),
        headers=_hdr("platform_admin"),
    )
    assert any(c[0] == "task_rejected_by_policy" for c in audit.calls)


def test_task_rbac_denied_audit_event(wired) -> None:
    _, _, audit, client = wired
    client.post("/tasks", json=_payload(), headers=_hdr("agent_operator"))
    assert any(c[0] == "task_rbac_denied" for c in audit.calls)


def test_audit_refs_never_carry_secret_shaped_content(wired) -> None:
    _, _, audit, client = wired
    client.post("/tasks", json=_payload(), headers=_hdr("agent_operator"))
    for _, _, _, refs in audit.calls:
        for value in refs.values():
            assert "token" not in str(value).lower()
            assert "secret" not in str(value).lower()


# -- Static no-dispatch / no-external-integration source checks --------------------


def test_source_has_no_workflow_dispatch_call() -> None:
    src = _TASK_API_SRC.read_text(encoding="utf-8").lower()
    for forbidden in ("dispatch_workflow(", "trigger_workflow(", "run_workflow(", ".dispatch("):
        assert forbidden not in src, forbidden


def test_source_has_no_external_integration_reference() -> None:
    src = _TASK_API_SRC.read_text(encoding="utf-8").lower()
    for forbidden in (
        "discord",
        "slack",
        "telegram",
        "github.com",
        "githubclient",
        "openai",
        "anthropic.com",
        "requests.post(",
        "requests.get(",
        "httpx.post(",
        "httpx.get(",
    ):
        assert forbidden not in src, forbidden


def test_dispatch_enabled_false_in_every_response(wired) -> None:
    _, _, _, client = wired
    created = client.post("/tasks", json=_payload(), headers=_hdr("requester")).json()
    assert created["dispatch_enabled"] is False
    got = client.get(f"/tasks/{created['id']}", headers=_hdr("requester")).json()
    assert got["dispatch_enabled"] is False
    submitted = client.post(f"/tasks/{created['id']}/submit", headers=_hdr("requester")).json()
    assert submitted["dispatch_enabled"] is False
