"""Step 66C.3 -- Workroom Audit / Visibility / Edge-case Hardening tests.

Closes three 66C.1/66C.2 non-blocking gaps: G1 (server-side message
visibility filtering), G3 (task-scoped audit-evidence endpoint), G5
(answered-twice guard). Self-contained, in-memory (no real DB/Redis/external
call), mirroring the fixture pattern in
tests/test_step66c1_workroom_clarification_api.py.
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

    async def claim_clarification_answer(self, clarification_id: str) -> dict[str, Any] | None:
        row = self.clarifications[clarification_id]
        if row["status"] != "open":
            return None
        row["status"] = "answered"
        row["answered_at"] = datetime.now(timezone.utc).isoformat()
        row["updated_at"] = datetime.now(timezone.utc).isoformat()
        return dict(row)

    async def set_answer_message(
        self, clarification_id: str, *, answer_message_id: str
    ) -> dict[str, Any]:
        row = self.clarifications[clarification_id]
        row["answer_message_id"] = answer_message_id
        row["updated_at"] = datetime.now(timezone.utc).isoformat()
        return dict(row)


class InMemoryAuditStore:
    """Step 66C.3 -- stand-in for shared.sdk.audit.store.AuditStore.

    Seeded directly with audit_logs-shaped rows in tests (this is a unit test
    of the audit-evidence *endpoint's* filtering/RBAC, not of the real
    Redis-stream -> audit-worker -> audit_logs pipeline, which is exercised
    separately in live validation).
    """

    def __init__(self) -> None:
        self.rows: dict[str, list[dict[str, Any]]] = {}

    def seed(self, task_id: str, row: dict[str, Any]) -> None:
        self.rows.setdefault(task_id, []).append(row)

    async def get_audit_logs(self, task_id: str) -> list[dict[str, Any]]:
        return [dict(r) for r in self.rows.get(task_id, [])]


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
    audit_store = InMemoryAuditStore()
    audit = AuditRecorder()
    monkeypatch.setattr(task_api, "_store", lambda: task_store)
    monkeypatch.setattr(task_api, "_audit", audit)
    monkeypatch.setattr(workroom_api, "_workroom_store", lambda: workroom_store)
    monkeypatch.setattr(workroom_api, "_audit_store", lambda: audit_store)
    app = FastAPI()
    app.include_router(task_api.router)
    app.include_router(workroom_api.router)
    client = TestClient(app)
    return task_api, workroom_api, task_store, workroom_store, audit_store, audit, client


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


def _seed_all_visibilities(workroom_store: InMemoryWorkroomStore, task_id: str) -> None:
    for visibility in ("task_participants", "operators", "audit_only", "private_system"):
        workroom_store.messages[str(uuid.uuid4())] = {
            "id": str(uuid.uuid4()),
            "task_id": task_id,
            "correlation_id": str(uuid.uuid4()),
            "sender_type": "human",
            "sender_id": "seed",
            "sender_role": None,
            "message_type": "human_message",
            "body": f"{visibility} body",
            "visibility": visibility,
            "reply_to_message_id": None,
            "audit_ref": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }


def _visible_visibilities(client, task_id: str, role: str, actor: str) -> set[str]:
    resp = client.get(f"/tasks/{task_id}/workroom", headers=_hdr(role, actor=actor))
    assert resp.status_code == 200
    return {m["visibility"] for m in resp.json()["messages"]}


# -- G1: message visibility filtering ------------------------------------------------


def test_requester_sees_only_task_participants_messages(wired) -> None:
    _, _, _, workroom_store, _, _, client = wired
    task = _create_task(client, actor="alice")
    _seed_all_visibilities(workroom_store, task["id"])
    seen = _visible_visibilities(client, task["id"], "requester", "alice")
    assert seen == {"task_participants"}


def test_platform_admin_sees_participants_operators_and_private_system(wired) -> None:
    _, _, _, workroom_store, _, _, client = wired
    task = _create_task(client, actor="alice")
    _seed_all_visibilities(workroom_store, task["id"])
    seen = _visible_visibilities(client, task["id"], "platform_admin", "admin1")
    assert seen == {"task_participants", "operators", "private_system"}
    assert "audit_only" not in seen


def test_agent_operator_sees_participants_operators_and_private_system(wired) -> None:
    _, _, _, workroom_store, _, _, client = wired
    task = _create_task(client, actor="alice")
    _seed_all_visibilities(workroom_store, task["id"])
    seen = _visible_visibilities(client, task["id"], "agent_operator", "op1")
    assert seen == {"task_participants", "operators", "private_system"}


def test_pm_engineering_lead_sees_operators_but_not_audit_only_or_private_system(wired) -> None:
    _, _, _, workroom_store, _, _, client = wired
    task = _create_task(client, actor="alice")
    _seed_all_visibilities(workroom_store, task["id"])
    seen = _visible_visibilities(client, task["id"], "pm_engineering_lead", "pm1")
    assert seen == {"task_participants", "operators"}


def test_security_compliance_reviewer_sees_audit_only_but_not_operators_or_private_system(
    wired,
) -> None:
    _, _, _, workroom_store, _, _, client = wired
    task = _create_task(client, actor="alice")
    _seed_all_visibilities(workroom_store, task["id"])
    seen = _visible_visibilities(client, task["id"], "security_compliance_reviewer", "sec1")
    assert seen == {"task_participants", "audit_only"}


def test_reviewer_approver_sees_only_task_participants(wired) -> None:
    _, _, _, workroom_store, _, _, client = wired
    task = _create_task(client, actor="alice")
    _seed_all_visibilities(workroom_store, task["id"])
    seen = _visible_visibilities(client, task["id"], "reviewer_approver", "rev1")
    assert seen == {"task_participants"}


def test_unknown_visibility_value_is_fail_closed_even_for_platform_admin(wired) -> None:
    _, _, _, workroom_store, _, _, client = wired
    task = _create_task(client, actor="alice")
    workroom_store.messages[str(uuid.uuid4())] = {
        "id": str(uuid.uuid4()),
        "task_id": task["id"],
        "correlation_id": str(uuid.uuid4()),
        "sender_type": "system",
        "sender_id": "seed",
        "sender_role": None,
        "message_type": "system_event",
        "body": "unknown-visibility body",
        "visibility": "some_future_visibility_value",
        "reply_to_message_id": None,
        "audit_ref": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    seen = _visible_visibilities(client, task["id"], "platform_admin", "admin1")
    assert "some_future_visibility_value" not in seen


def test_filter_messages_by_visibility_is_server_side_not_frontend_only(wired) -> None:
    """G1 requires server-side filtering -- prove the raw store list is
    larger than what the API returns for a restricted role."""
    _, _, _, workroom_store, _, _, client = wired
    task = _create_task(client, actor="alice")
    _seed_all_visibilities(workroom_store, task["id"])
    raw = workroom_store.messages
    assert len([m for m in raw.values() if m["task_id"] == task["id"]]) == 4
    resp = client.get(f"/tasks/{task['id']}/workroom", headers=_hdr("requester", actor="alice"))
    assert len(resp.json()["messages"]) == 1


# -- G3: task-scoped audit evidence endpoint -----------------------------------------


def _seed_audit_row(
    audit_store: InMemoryAuditStore,
    task_id: str,
    *,
    decision_type: str = "task_message_created",
    extra_refs: dict[str, Any] | None = None,
) -> None:
    refs = {
        "task_id": task_id,
        "correlation_id": str(uuid.uuid4()),
        "actor": "alice",
        "role": "requester",
        "action": "post_message",
        "status": "completed",
        "message_id": str(uuid.uuid4()),
        "message_type": "human_message",
        "visibility": "task_participants",
        "body_length": 42,
        "body_hash": "deadbeef" * 8,
        "production_executed": False,
        "workflow_dispatched": False,
    }
    if extra_refs:
        refs.update(extra_refs)
    audit_store.seed(
        task_id,
        {
            "audit_id": str(uuid.uuid4()),
            "task_id": task_id,
            "agent": "task-api",
            "decision_type": decision_type,
            "summary": "workroom message created",
            "result": "completed",
            "artifact_refs": refs,
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
    )


def test_audit_evidence_platform_admin_allowed(wired) -> None:
    _, _, _, _, audit_store, _, client = wired
    task = _create_task(client, actor="alice")
    _seed_audit_row(audit_store, task["id"])
    resp = client.get(
        f"/tasks/{task['id']}/audit-evidence", headers=_hdr("platform_admin", actor="admin1")
    )
    assert resp.status_code == 200
    assert resp.json()["dispatch_enabled"] is False
    assert resp.json()["resume_dispatch_enabled"] is False
    assert len(resp.json()["events"]) == 1


def test_audit_evidence_agent_operator_allowed(wired) -> None:
    _, _, _, _, audit_store, _, client = wired
    task = _create_task(client, actor="alice")
    _seed_audit_row(audit_store, task["id"])
    resp = client.get(
        f"/tasks/{task['id']}/audit-evidence", headers=_hdr("agent_operator", actor="op1")
    )
    assert resp.status_code == 200


def test_audit_evidence_security_compliance_reviewer_allowed_read_only(wired) -> None:
    _, _, _, _, audit_store, _, client = wired
    task = _create_task(client, actor="alice")
    _seed_audit_row(audit_store, task["id"])
    resp = client.get(
        f"/tasks/{task['id']}/audit-evidence",
        headers=_hdr("security_compliance_reviewer", actor="sec1"),
    )
    assert resp.status_code == 200
    # Read-only: normal workroom mutation remains denied for this role.
    denied = client.post(
        f"/tasks/{task['id']}/workroom/messages",
        json={"body": "hi"},
        headers=_hdr("security_compliance_reviewer", actor="sec1"),
    )
    assert denied.status_code == 403


def test_audit_evidence_pm_engineering_lead_allowed(wired) -> None:
    _, _, _, _, audit_store, _, client = wired
    task = _create_task(client, actor="alice")
    _seed_audit_row(audit_store, task["id"])
    resp = client.get(
        f"/tasks/{task['id']}/audit-evidence", headers=_hdr("pm_engineering_lead", actor="pm1")
    )
    assert resp.status_code == 200


def test_audit_evidence_requester_denied(wired) -> None:
    _, _, _, _, audit_store, audit, client = wired
    task = _create_task(client, actor="alice")
    _seed_audit_row(audit_store, task["id"])
    resp = client.get(
        f"/tasks/{task['id']}/audit-evidence", headers=_hdr("requester", actor="alice")
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "role_cannot_view_audit_evidence"
    assert any(c[0] == "audit_evidence_rbac_denied" for c in audit.calls)


def test_audit_evidence_reviewer_approver_denied(wired) -> None:
    _, _, _, _, audit_store, _, client = wired
    task = _create_task(client, actor="alice")
    _seed_audit_row(audit_store, task["id"])
    resp = client.get(
        f"/tasks/{task['id']}/audit-evidence", headers=_hdr("reviewer_approver", actor="rev1")
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "role_cannot_view_audit_evidence"


def test_audit_evidence_task_not_found(wired) -> None:
    _, _, _, _, _, _, client = wired
    resp = client.get(
        f"/tasks/{uuid.uuid4()}/audit-evidence", headers=_hdr("platform_admin", actor="admin1")
    )
    assert resp.status_code == 404


def test_audit_evidence_returns_safe_metadata_only(wired) -> None:
    _, _, _, _, audit_store, _, client = wired
    task = _create_task(client, actor="alice")
    _seed_audit_row(audit_store, task["id"])
    resp = client.get(
        f"/tasks/{task['id']}/audit-evidence", headers=_hdr("platform_admin", actor="admin1")
    )
    event = resp.json()["events"][0]
    for expected in (
        "audit_event_id",
        "task_id",
        "event_type",
        "created_at",
        "actor",
        "role",
        "action",
        "status",
        "message_id",
        "message_type",
        "visibility",
        "body_length",
        "body_hash",
    ):
        assert expected in event, expected


def test_audit_evidence_does_not_expose_raw_message_body(wired) -> None:
    """Even if a future/rogue producer stuffed a raw body into artifact_refs,
    the endpoint's allowlist must strip it -- defense in depth beyond the
    invariant that safe_workroom_refs never includes one."""
    _, _, _, _, audit_store, _, client = wired
    task = _create_task(client, actor="alice")
    _seed_audit_row(audit_store, task["id"], extra_refs={"body": "SECRET RAW MESSAGE BODY"})
    resp = client.get(
        f"/tasks/{task['id']}/audit-evidence", headers=_hdr("platform_admin", actor="admin1")
    )
    event = resp.json()["events"][0]
    assert "body" not in event
    assert "SECRET RAW MESSAGE BODY" not in str(event)


def test_audit_evidence_does_not_expose_raw_clarification_answer(wired) -> None:
    _, _, _, _, audit_store, _, client = wired
    task = _create_task(client, actor="alice")
    _seed_audit_row(
        audit_store,
        task["id"],
        decision_type="clarification_answered",
        extra_refs={"answer": "SECRET RAW ANSWER TEXT"},
    )
    resp = client.get(
        f"/tasks/{task['id']}/audit-evidence", headers=_hdr("platform_admin", actor="admin1")
    )
    event = resp.json()["events"][0]
    assert "answer" not in event
    assert "SECRET RAW ANSWER TEXT" not in str(event)


def test_audit_evidence_does_not_expose_headers_cookies_tokens(wired) -> None:
    _, _, _, _, audit_store, _, client = wired
    task = _create_task(client, actor="alice")
    _seed_audit_row(
        audit_store,
        task["id"],
        extra_refs={
            "headers": {"Authorization": "Bearer secret"},
            "cookie": "session=abc123",
            "token": "ghp_fake_token_value",
        },
    )
    resp = client.get(
        f"/tasks/{task['id']}/audit-evidence", headers=_hdr("platform_admin", actor="admin1")
    )
    event = resp.json()["events"][0]
    for forbidden in ("headers", "cookie", "token"):
        assert forbidden not in event
    assert "secret" not in str(event).lower()
    assert "ghp_fake_token_value" not in str(event)


def test_audit_evidence_allowlist_excludes_forbidden_fields() -> None:
    _, workroom_api = _load()
    forbidden = {"body", "answer", "raw_body", "payload", "headers", "cookies", "token", "secret"}
    assert forbidden.isdisjoint(set(workroom_api._AUDIT_EVIDENCE_REF_FIELDS))


# -- G5: answered-twice guard ---------------------------------------------------------


def test_second_answer_returns_409_clarification_already_answered(wired) -> None:
    _, _, _, _, _, _, client = wired
    task = _create_task(client, actor="alice")
    created = client.post(
        f"/tasks/{task['id']}/clarifications",
        json={"question": "Which environment?"},
        headers=_hdr("pm_engineering_lead", actor="pm1"),
    ).json()
    first = client.post(
        f"/tasks/{task['id']}/clarifications/{created['id']}/answer",
        json={"answer": "Use the test environment."},
        headers=_hdr("requester", actor="alice"),
    )
    assert first.status_code == 200
    second = client.post(
        f"/tasks/{task['id']}/clarifications/{created['id']}/answer",
        json={"answer": "A different second answer."},
        headers=_hdr("requester", actor="alice"),
    )
    assert second.status_code == 409
    assert second.json()["detail"] == "clarification_already_answered"


def test_second_answer_creates_no_extra_message(wired) -> None:
    _, _, _, workroom_store, _, _, client = wired
    task = _create_task(client, actor="alice")
    created = client.post(
        f"/tasks/{task['id']}/clarifications",
        json={"question": "Which environment?"},
        headers=_hdr("pm_engineering_lead", actor="pm1"),
    ).json()
    client.post(
        f"/tasks/{task['id']}/clarifications/{created['id']}/answer",
        json={"answer": "Use the test environment."},
        headers=_hdr("requester", actor="alice"),
    )
    count_before = len(
        [m for m in workroom_store.messages.values() if m["message_type"] == "clarification_answer"]
    )
    client.post(
        f"/tasks/{task['id']}/clarifications/{created['id']}/answer",
        json={"answer": "A different second answer."},
        headers=_hdr("requester", actor="alice"),
    )
    count_after = len(
        [m for m in workroom_store.messages.values() if m["message_type"] == "clarification_answer"]
    )
    assert count_after == count_before == 1


def test_second_answer_creates_no_clarification_answered_audit_event(wired) -> None:
    _, _, _, _, _, audit, client = wired
    task = _create_task(client, actor="alice")
    created = client.post(
        f"/tasks/{task['id']}/clarifications",
        json={"question": "Which environment?"},
        headers=_hdr("pm_engineering_lead", actor="pm1"),
    ).json()
    client.post(
        f"/tasks/{task['id']}/clarifications/{created['id']}/answer",
        json={"answer": "Use the test environment."},
        headers=_hdr("requester", actor="alice"),
    )
    count_before = len([c for c in audit.calls if c[0] == "clarification_answered"])
    client.post(
        f"/tasks/{task['id']}/clarifications/{created['id']}/answer",
        json={"answer": "A different second answer."},
        headers=_hdr("requester", actor="alice"),
    )
    count_after = len([c for c in audit.calls if c[0] == "clarification_answered"])
    assert count_after == count_before == 1


def test_claim_clarification_answer_store_level_atomicity(wired) -> None:
    """Directly exercises the store contract that makes G5 race-safe: the
    second claim on an already-claimed clarification returns None, not a
    row -- this is what the real Postgres `WHERE status='open'` UPDATE
    guarantees under true concurrency (see workroom_store.py)."""
    _, _, _, workroom_store, _, _, client = wired
    task = _create_task(client, actor="alice")
    created = client.post(
        f"/tasks/{task['id']}/clarifications",
        json={"question": "Which environment?"},
        headers=_hdr("pm_engineering_lead", actor="pm1"),
    ).json()
    import asyncio

    first = asyncio.run(workroom_store.claim_clarification_answer(created["id"]))
    second = asyncio.run(workroom_store.claim_clarification_answer(created["id"]))
    assert first is not None
    assert first["status"] == "answered"
    assert second is None
