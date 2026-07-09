"""Step 66B.1 -- task API foundation tests.

Loads task_api.py in isolation (mounted alone on a bare FastAPI()), with the
module-level _store()/_audit() monkeypatched to an in-memory fake -- no real DB,
no Redis, no external call, matching the tests/test_operations_safety.py pattern.
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


def _load() -> ModuleType:
    sys.path.insert(0, str(_ORCH_SRC))
    try:
        spec = importlib.util.spec_from_file_location(
            "orchestrator_task_api", _ORCH_SRC / "task_api.py"
        )
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


def _hdr(role: str, actor: str = "u1") -> dict[str, str]:
    return {"X-Task-Actor": actor, "X-Task-Role": role}


def _payload(**overrides: Any) -> dict[str, Any]:
    body = {"title": "Build the thing", "task_type": "software_delivery"}
    body.update(overrides)
    return body


def test_create_task_success(wired) -> None:
    _, _, audit, client = wired
    resp = client.post("/tasks", json=_payload(), headers=_hdr("requester"))
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "draft"
    assert body["production_effect"] is False
    assert body["dispatch_enabled"] is False
    assert body["intake_planning_only"] is False
    assert audit.calls[0][0] == "task_created"


def test_create_task_auth_disabled(wired, monkeypatch) -> None:
    _, _, _, client = wired
    monkeypatch.setenv("TASK_API_TEST_AUTH_ENABLED", "false")
    resp = client.post("/tasks", json=_payload(), headers=_hdr("requester"))
    assert resp.status_code == 403
    assert resp.json()["detail"] == "task_api_test_auth_disabled"


def test_create_task_missing_actor(wired) -> None:
    _, _, _, client = wired
    resp = client.post("/tasks", json=_payload(), headers={"X-Task-Role": "requester"})
    assert resp.status_code == 401


def test_create_task_invalid_role(wired) -> None:
    _, _, _, client = wired
    resp = client.post("/tasks", json=_payload(), headers=_hdr("not_a_role"))
    assert resp.status_code == 401


def test_create_task_role_cannot_create(wired) -> None:
    _, _, _, client = wired
    resp = client.post("/tasks", json=_payload(), headers=_hdr("agent_operator"))
    assert resp.status_code == 403
    assert resp.json()["detail"] == "role_cannot_create_task"


def test_create_task_non_first_class_type_is_intake_planning_only(wired) -> None:
    _, _, _, client = wired
    resp = client.post("/tasks", json=_payload(task_type="research"), headers=_hdr("requester"))
    assert resp.status_code == 201
    assert resp.json()["intake_planning_only"] is True


def test_create_task_production_effect_true_submitted_is_blocked_not_dispatched(wired) -> None:
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
    assert "task_created" in decision_types
    assert "task_rejected_by_policy" in decision_types


def test_list_tasks_requester_scoped_to_own(wired) -> None:
    _, store, _, client = wired
    client.post("/tasks", json=_payload(), headers=_hdr("requester", actor="alice"))
    client.post("/tasks", json=_payload(), headers=_hdr("requester", actor="bob"))
    resp = client.get("/tasks", headers=_hdr("requester", actor="alice"))
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 1
    assert body["tasks"][0]["created_by"] == "alice"


def test_list_tasks_platform_admin_sees_all(wired) -> None:
    _, _, _, client = wired
    client.post("/tasks", json=_payload(), headers=_hdr("requester", actor="alice"))
    client.post("/tasks", json=_payload(), headers=_hdr("requester", actor="bob"))
    resp = client.get("/tasks", headers=_hdr("platform_admin", actor="admin1"))
    assert resp.status_code == 200
    assert resp.json()["count"] == 2


def test_get_task_not_found(wired) -> None:
    _, _, _, client = wired
    resp = client.get(f"/tasks/{uuid.uuid4()}", headers=_hdr("platform_admin"))
    assert resp.status_code == 404


def test_get_task_requester_forbidden_for_others_task(wired) -> None:
    _, _, _, client = wired
    created = client.post(
        "/tasks", json=_payload(), headers=_hdr("requester", actor="alice")
    ).json()
    resp = client.get(f"/tasks/{created['id']}", headers=_hdr("requester", actor="bob"))
    assert resp.status_code == 403
    assert resp.json()["detail"] == "not_own_task"


def test_submit_task_moves_to_intake_review(wired) -> None:
    _, _, audit, client = wired
    created = client.post("/tasks", json=_payload(), headers=_hdr("requester")).json()
    resp = client.post(f"/tasks/{created['id']}/submit", headers=_hdr("requester"))
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "intake_review"
    assert body["dispatch_enabled"] is False
    assert audit.calls[-1][0] == "task_submitted"


def test_submit_task_production_effect_blocks_not_dispatch(wired) -> None:
    _, _, audit, client = wired
    created = client.post(
        "/tasks", json=_payload(production_effect=True), headers=_hdr("platform_admin")
    ).json()
    assert (
        created["status"] == "draft"
    )  # not forced blocked at create (initial_status stayed draft)
    resp = client.post(f"/tasks/{created['id']}/submit", headers=_hdr("platform_admin"))
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "blocked"
    assert body["dispatch_enabled"] is False
    decision_types = [c[0] for c in audit.calls]
    assert "task_rejected_by_policy" in decision_types


def test_submit_task_invalid_state_conflict(wired) -> None:
    _, _, _, client = wired
    created = client.post("/tasks", json=_payload(), headers=_hdr("requester")).json()
    client.post(f"/tasks/{created['id']}/submit", headers=_hdr("requester"))
    resp = client.post(f"/tasks/{created['id']}/submit", headers=_hdr("requester"))
    assert resp.status_code == 409


def test_submit_role_cannot_submit(wired) -> None:
    _, _, _, client = wired
    created = client.post("/tasks", json=_payload(), headers=_hdr("requester")).json()
    resp = client.post(f"/tasks/{created['id']}/submit", headers=_hdr("agent_operator"))
    assert resp.status_code == 403
    assert resp.json()["detail"] == "role_cannot_submit_task"


def test_no_dispatch_field_always_false(wired) -> None:
    _, _, _, client = wired
    created = client.post("/tasks", json=_payload(), headers=_hdr("requester")).json()
    assert created["dispatch_enabled"] is False
    submitted = client.post(f"/tasks/{created['id']}/submit", headers=_hdr("requester")).json()
    assert submitted["dispatch_enabled"] is False
