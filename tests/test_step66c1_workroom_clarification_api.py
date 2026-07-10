"""Step 66C.1 -- Agent Workroom & Clarification API foundation tests.

Loads task_api.py and workroom_api.py in isolation under their real module
names (workroom_api does `import task_api` and calls `task_api._authenticate`/
`task_api._audit`/`task_api._store`, so monkeypatching those attributes on the
`task_api` module object affects both routers consistently -- unlike a
`from task_api import _audit` copy, which would need patching twice). No real
DB, no Redis, no external call.
"""

from __future__ import annotations

import importlib
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

_ORCH_SRC = Path(__file__).resolve().parents[1] / "apps" / "orchestrator" / "src"
_WORKROOM_API_SRC = _ORCH_SRC / "workroom_api.py"


def _load():
    sys.path.insert(0, str(_ORCH_SRC))
    try:
        sys.modules.pop("task_api", None)
        sys.modules.pop("workroom_api", None)
        task_api = importlib.import_module("task_api")
        workroom_api = importlib.import_module("workroom_api")
        return task_api, workroom_api
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

    async def set_clarification_state(
        self, task_id: str, *, status: str, clarification_status: str
    ) -> dict[str, Any]:
        row = self.rows[task_id]
        row["status"] = status
        row["clarification_status"] = clarification_status
        row["updated_at"] = datetime.now(timezone.utc).isoformat()
        return dict(row)


class InMemoryWorkroomStore:
    def __init__(self) -> None:
        self.messages: dict[str, dict[str, Any]] = {}
        self.clarifications: dict[str, dict[str, Any]] = {}

    async def create_message(
        self,
        *,
        task_id: str,
        sender_type: str,
        sender_id: str,
        sender_role: str | None,
        message_type: str,
        body: str,
        visibility: str,
        reply_to_message_id: str | None = None,
    ) -> dict[str, Any]:
        message_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        row = {
            "id": message_id,
            "task_id": task_id,
            "correlation_id": str(uuid.uuid4()),
            "sender_type": sender_type,
            "sender_id": sender_id,
            "sender_role": sender_role,
            "message_type": message_type,
            "body": body,
            "visibility": visibility,
            "reply_to_message_id": reply_to_message_id,
            "audit_ref": None,
            "created_at": now,
            "updated_at": now,
        }
        self.messages[message_id] = row
        return dict(row)

    async def list_messages(self, task_id: str) -> list[dict[str, Any]]:
        return [dict(m) for m in self.messages.values() if m["task_id"] == task_id]

    async def create_clarification(
        self,
        *,
        task_id: str,
        question_message_id: str,
        question: str,
        requested_by_type: str,
        requested_by_id: str,
        assigned_to: str | None,
    ) -> dict[str, Any]:
        clarification_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        row = {
            "id": clarification_id,
            "task_id": task_id,
            "question_message_id": question_message_id,
            "status": "open",
            "question": question,
            "requested_by_type": requested_by_type,
            "requested_by_id": requested_by_id,
            "assigned_to": assigned_to,
            "due_at": now,
            "reminder_at": now,
            "answered_at": None,
            "answer_message_id": None,
            "created_at": now,
            "updated_at": now,
        }
        self.clarifications[clarification_id] = row
        return dict(row)

    async def list_clarifications(self, task_id: str) -> list[dict[str, Any]]:
        return [dict(c) for c in self.clarifications.values() if c["task_id"] == task_id]

    async def get_clarification(self, clarification_id: str) -> dict[str, Any] | None:
        row = self.clarifications.get(clarification_id)
        return dict(row) if row else None

    async def answer_clarification(
        self, clarification_id: str, *, answer_message_id: str
    ) -> dict[str, Any]:
        row = self.clarifications[clarification_id]
        row["status"] = "answered"
        row["answer_message_id"] = answer_message_id
        row["answered_at"] = datetime.now(timezone.utc).isoformat()
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
    task_api, workroom_api = _load()
    monkeypatch.setenv("TASK_API_TEST_AUTH_ENABLED", "true")
    task_store = InMemoryTaskStore()
    workroom_store = InMemoryWorkroomStore()
    audit = AuditRecorder()
    monkeypatch.setattr(task_api, "_store", lambda: task_store)
    monkeypatch.setattr(task_api, "_audit", audit)
    monkeypatch.setattr(workroom_api, "_workroom_store", lambda: workroom_store)
    app = FastAPI()
    app.include_router(task_api.router)
    app.include_router(workroom_api.router)
    client = TestClient(app)
    return task_api, workroom_api, task_store, workroom_store, audit, client


def _hdr(role: str | None, actor: str | None = "u1") -> dict[str, str]:
    headers: dict[str, str] = {}
    if actor is not None:
        headers["X-Task-Actor"] = actor
    if role is not None:
        headers["X-Task-Role"] = role
    return headers


def _create_task(client, actor: str = "alice", role: str = "requester") -> dict[str, Any]:
    resp = client.post(
        "/tasks",
        json={"title": "Build the thing", "task_type": "software_delivery"},
        headers=_hdr(role, actor=actor),
    )
    assert resp.status_code == 201
    return resp.json()


# -- GET workroom -------------------------------------------------------------------


def test_get_workroom_empty_default(wired) -> None:
    _, _, _, _, _, client = wired
    task = _create_task(client)
    resp = client.get(f"/tasks/{task['id']}/workroom", headers=_hdr("requester", actor="alice"))
    assert resp.status_code == 200
    body = resp.json()
    assert body["messages"] == []
    assert body["clarification_requests"] == []
    assert body["dispatch_enabled"] is False
    assert body["resume_dispatch_enabled"] is False
    assert body["task_status"] == "draft"


def test_get_workroom_missing_actor_denied(wired) -> None:
    _, _, _, _, _, client = wired
    task = _create_task(client)
    resp = client.get(f"/tasks/{task['id']}/workroom", headers=_hdr("requester", actor=None))
    assert resp.status_code == 401
    assert resp.json()["detail"] == "missing_actor"


def test_get_workroom_invalid_role_denied(wired) -> None:
    _, _, _, _, _, client = wired
    task = _create_task(client)
    resp = client.get(f"/tasks/{task['id']}/workroom", headers=_hdr("bogus", actor="alice"))
    assert resp.status_code == 401
    assert resp.json()["detail"] == "invalid_role"


def test_requester_cannot_view_other_actor_workroom(wired) -> None:
    _, _, _, _, audit, client = wired
    task = _create_task(client, actor="alice")
    resp = client.get(f"/tasks/{task['id']}/workroom", headers=_hdr("requester", actor="bob"))
    assert resp.status_code == 403
    assert resp.json()["detail"] == "not_own_task"
    assert any(c[0] == "task_workroom_rbac_denied" for c in audit.calls)


def test_platform_admin_can_view_any_workroom(wired) -> None:
    _, _, _, _, _, client = wired
    task = _create_task(client, actor="alice")
    resp = client.get(
        f"/tasks/{task['id']}/workroom", headers=_hdr("platform_admin", actor="admin1")
    )
    assert resp.status_code == 200


# -- POST workroom message -----------------------------------------------------------


def test_post_human_message_succeeds(wired) -> None:
    _, _, _, _, audit, client = wired
    task = _create_task(client, actor="alice")
    resp = client.post(
        f"/tasks/{task['id']}/workroom/messages",
        json={"body": "Please clarify the deadline."},
        headers=_hdr("requester", actor="alice"),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["message_type"] == "human_message"
    assert body["sender_type"] == "human"
    assert body["dispatch_enabled"] is False
    assert audit.calls[-1][0] == "task_message_created"


def test_requester_cannot_post_to_other_actor_task(wired) -> None:
    _, _, _, _, audit, client = wired
    task = _create_task(client, actor="alice")
    resp = client.post(
        f"/tasks/{task['id']}/workroom/messages",
        json={"body": "hi"},
        headers=_hdr("requester", actor="bob"),
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "not_own_task"
    assert any(c[0] == "task_workroom_rbac_denied" for c in audit.calls)


def test_message_body_length_limit(wired) -> None:
    _, _, _, _, _, client = wired
    task = _create_task(client, actor="alice")
    resp = client.post(
        f"/tasks/{task['id']}/workroom/messages",
        json={"body": "x" * 8001},
        headers=_hdr("requester", actor="alice"),
    )
    assert resp.status_code == 422


def test_message_audit_never_includes_raw_body(wired) -> None:
    _, _, _, _, audit, client = wired
    task = _create_task(client, actor="alice")
    secret_body = "the deadline is confidential-project-x"
    client.post(
        f"/tasks/{task['id']}/workroom/messages",
        json={"body": secret_body},
        headers=_hdr("requester", actor="alice"),
    )
    created = [c for c in audit.calls if c[0] == "task_message_created"][-1]
    refs = created[3]
    assert "body" not in refs
    assert refs.get("body_length") == len(secret_body)
    for value in refs.values():
        assert secret_body not in str(value)


# -- Clarification create / answer ----------------------------------------------------


def test_create_clarification_sets_task_clarification_needed(wired) -> None:
    _, _, _, _, audit, client = wired
    task = _create_task(client, actor="alice")
    resp = client.post(
        f"/tasks/{task['id']}/clarifications",
        json={"question": "Which environment should this target?"},
        headers=_hdr("pm_engineering_lead", actor="pm1"),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "open"
    assert body["task_status"] == "clarification_needed"
    assert body["dispatch_enabled"] is False
    assert body["resume_dispatch_enabled"] is False
    assert audit.calls[-1][0] == "clarification_requested"


def test_get_workroom_shows_clarification_question(wired) -> None:
    _, _, _, _, _, client = wired
    task = _create_task(client, actor="alice")
    client.post(
        f"/tasks/{task['id']}/clarifications",
        json={"question": "Which environment?"},
        headers=_hdr("pm_engineering_lead", actor="pm1"),
    )
    resp = client.get(f"/tasks/{task['id']}/workroom", headers=_hdr("requester", actor="alice"))
    body = resp.json()
    assert body["task_status"] == "clarification_needed"
    assert len(body["clarification_requests"]) == 1
    message_types = [m["message_type"] for m in body["messages"]]
    assert "clarification_question" in message_types


def test_requester_cannot_create_clarification(wired) -> None:
    _, _, _, _, audit, client = wired
    task = _create_task(client, actor="alice")
    resp = client.post(
        f"/tasks/{task['id']}/clarifications",
        json={"question": "Why?"},
        headers=_hdr("requester", actor="alice"),
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "role_cannot_create_clarification"
    assert any(c[0] == "clarification_rbac_denied" for c in audit.calls)


def test_unauthorized_role_cannot_create_clarification(wired) -> None:
    _, _, _, _, _, client = wired
    task = _create_task(client, actor="alice")
    resp = client.post(
        f"/tasks/{task['id']}/clarifications",
        json={"question": "Why?"},
        headers=_hdr("security_compliance_reviewer", actor="sec1"),
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "role_cannot_create_clarification"


def test_clarification_question_length_limit(wired) -> None:
    _, _, _, _, _, client = wired
    task = _create_task(client, actor="alice")
    resp = client.post(
        f"/tasks/{task['id']}/clarifications",
        json={"question": "x" * 4001},
        headers=_hdr("pm_engineering_lead", actor="pm1"),
    )
    assert resp.status_code == 422


def test_answer_clarification_succeeds_and_task_becomes_intake_review(wired) -> None:
    _, _, _, _, audit, client = wired
    task = _create_task(client, actor="alice")
    created = client.post(
        f"/tasks/{task['id']}/clarifications",
        json={"question": "Which environment?"},
        headers=_hdr("pm_engineering_lead", actor="pm1"),
    ).json()
    resp = client.post(
        f"/tasks/{task['id']}/clarifications/{created['id']}/answer",
        json={"answer": "Use the test environment."},
        headers=_hdr("requester", actor="alice"),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "answered"
    assert body["task_status"] == "intake_review"
    assert body["dispatch_enabled"] is False
    assert body["resume_dispatch_enabled"] is False
    assert audit.calls[-1][0] == "clarification_answered"


def test_requester_cannot_answer_other_actor_clarification(wired) -> None:
    _, _, _, _, audit, client = wired
    task = _create_task(client, actor="alice")
    created = client.post(
        f"/tasks/{task['id']}/clarifications",
        json={"question": "Which environment?"},
        headers=_hdr("pm_engineering_lead", actor="pm1"),
    ).json()
    resp = client.post(
        f"/tasks/{task['id']}/clarifications/{created['id']}/answer",
        json={"answer": "test"},
        headers=_hdr("requester", actor="bob"),
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "not_own_task"
    assert any(c[0] == "clarification_rbac_denied" for c in audit.calls)


def test_clarification_answer_length_limit(wired) -> None:
    _, _, _, _, _, client = wired
    task = _create_task(client, actor="alice")
    created = client.post(
        f"/tasks/{task['id']}/clarifications",
        json={"question": "Which environment?"},
        headers=_hdr("pm_engineering_lead", actor="pm1"),
    ).json()
    resp = client.post(
        f"/tasks/{task['id']}/clarifications/{created['id']}/answer",
        json={"answer": "x" * 8001},
        headers=_hdr("requester", actor="alice"),
    )
    assert resp.status_code == 422


def test_unauthorized_role_cannot_answer_clarification(wired) -> None:
    _, _, _, _, _, client = wired
    task = _create_task(client, actor="alice")
    created = client.post(
        f"/tasks/{task['id']}/clarifications",
        json={"question": "Which environment?"},
        headers=_hdr("pm_engineering_lead", actor="pm1"),
    ).json()
    resp = client.post(
        f"/tasks/{task['id']}/clarifications/{created['id']}/answer",
        json={"answer": "test"},
        headers=_hdr("agent_operator", actor="op1"),
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "role_cannot_answer_clarification"


# -- Static no-dispatch / no-resume / no-external-integration source checks -----------


def test_source_has_no_workflow_dispatch_or_resume_call() -> None:
    src = _WORKROOM_API_SRC.read_text(encoding="utf-8").lower()
    for forbidden in (
        "dispatch_workflow(",
        "trigger_workflow(",
        "run_workflow(",
        "resume_workflow(",
        "resume_engine",
        ".dispatch(",
        ".resume(",
    ):
        assert forbidden not in src, forbidden


def test_source_has_no_external_integration_reference() -> None:
    src = _WORKROOM_API_SRC.read_text(encoding="utf-8").lower()
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
