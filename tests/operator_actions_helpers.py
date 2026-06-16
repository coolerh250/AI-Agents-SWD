"""Stage 52 -- in-memory fakes + a logged-in fake Request for operator-action
API-flow tests (no DB, no network)."""

from __future__ import annotations

import uuid

from shared.sdk.operator_actions.csrf import issue_csrf
from shared.sdk.operator_actions.session import issue_session, session_hash

AUTH_ENV = {
    "ADMIN_CONSOLE_AUTH_MODE": "test_local_signed_session",
    "ADMIN_CONSOLE_TEST_AUTH_ENABLED": "true",
    "ENABLE_ADMIN_CONSOLE_OPERATOR_ACTIONS": "true",
}


def enable_auth(monkeypatch) -> None:
    for k, v in AUTH_ENV.items():
        monkeypatch.setenv(k, v)


class FakeRequest:
    def __init__(self, cookies: dict, headers: dict, body: dict | None = None) -> None:
        self.cookies = cookies
        self.headers = headers
        self._body = body or {}

    async def json(self) -> dict:
        return self._body


def logged_in_request(
    identity_key: str,
    *,
    body: dict | None = None,
    idempotency_key: str | None = None,
    with_csrf: bool = True,
) -> FakeRequest:
    token, _i, _e = issue_session(identity_key, env={})
    sh = session_hash(token)
    headers: dict[str, str] = {}
    if with_csrf:
        headers["X-CSRF-Token"] = issue_csrf(sh, env={})
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key
    return FakeRequest({"admin_console_session": token}, headers, body)


class FakeResponse:
    def __init__(self) -> None:
        self.cookies: dict = {}

    def set_cookie(self, name, value, **kw) -> None:
        self.cookies[name] = {"value": value, **kw}

    def delete_cookie(self, name, **kw) -> None:
        self.cookies.pop(name, None)


class InMemoryOperatorStore:
    def __init__(self, roles: dict[str, list[str]] | None = None) -> None:
        self.roles = roles or {"operator-test": ["operator"]}
        self.actions: dict[str, dict] = {}
        self.by_idem: dict[str, str] = {}
        self.confirmations: dict[str, dict] = {}
        self.notes: list[dict] = []
        self.executions: list[dict] = []
        self.decisions: list[dict] = []
        self.reruns: list[dict] = []

    async def get_session_by_hash(self, sh):
        return {
            "id": "s1",
            "status": "active",
            "expires_at": None,
            "identity_key": self._current,
            "identity_status": "active",
        }

    async def get_identity(self, identity_key):
        return {
            "id": "i-" + identity_key,
            "identity_key": identity_key,
            "roles": self.roles.get(identity_key, []),
        }

    _current = "operator-test"

    async def find_action_by_idempotency(self, key):
        aid = self.by_idem.get(key)
        return self.actions.get(aid) if aid else None

    async def create_action_request(self, req, *, identity_id):
        aid = str(uuid.uuid4())
        self.actions[aid] = {
            "id": aid,
            "action_key": req.action_key,
            "action_type": req.action_type,
            "status": req.status,
            "policy_status": req.policy_status,
            "confirmation_status": req.confirmation_status,
            "target_id": req.target_id,
            "reason": req.reason,
            "identity_key": req.identity_key,
        }
        self.by_idem[req.idempotency_key] = aid
        return aid

    async def update_action_status(
        self, action_id, *, status, policy_status=None, confirmation_status=None, completed=False
    ):
        a = self.actions.get(action_id)
        if a:
            a["status"] = status
            if confirmation_status:
                a["confirmation_status"] = confirmation_status

    async def get_action(self, action_id):
        return self.actions.get(action_id)

    async def list_actions(self, *, limit=50):
        return list(self.actions.values())[:limit]

    async def create_execution(self, action_id, ex):
        self.executions.append({"action_id": action_id, "status": ex.status})
        return "e1"

    async def create_confirmation(self, action_id, identity_id, nh, exp, confirmation_type="x"):
        self.confirmations[action_id] = {
            "id": "c-" + action_id,
            "nonce_hash": nh,
            "used": False,
            "expires_at": exp,
            "identity_key": self._current,
        }
        return "c-" + action_id

    async def get_latest_confirmation(self, action_id):
        return self.confirmations.get(action_id)

    async def mark_confirmation_used(self, cid):
        for c in self.confirmations.values():
            if c["id"] == cid:
                c["used"] = True

    async def add_review_note(self, note, *, identity_id):
        self.notes.append({"summary": note.summary, "note_type": note.note_type})
        return "n1"

    async def list_review_notes(self, package_id):
        return self.notes

    async def link_audit(self, action_id, decision_type, audit_log_id=None):
        return None

    async def apply_delivery_decision(
        self,
        package_id,
        *,
        review_status,
        human_acceptance_status,
        package_status,
        summary,
        requested_changes=None,
    ):
        self.decisions.append(
            {
                "package_id": package_id,
                "review_status": review_status,
                "human_acceptance_status": human_acceptance_status,
                "package_status": package_status,
            }
        )

    async def create_rerun(self, action_id, rerun):
        self.reruns.append({"script_key": rerun.script_key, "status": rerun.status})
        return "r1"

    async def list_reruns(self, *, limit=50):
        return self.reruns


class InMemoryPackageStore:
    def __init__(
        self,
        *,
        status="ready_for_review",
        gate_decision="ready_for_operator_review",
        blocking=0,
        failed=0,
    ) -> None:
        self._status = status
        self._gate = {
            "decision": gate_decision,
            "blocking_findings_count": blocking,
            "failed_checks": failed,
        }

    async def get_delivery_package(self, pid):
        return {
            "id": pid,
            "status": self._status,
            "project_id": None,
            "human_acceptance_status": "pending",
        }

    async def get_acceptance_gate(self, pid):
        return self._gate


def wire(
    monkeypatch,
    *,
    roles=None,
    package_status="ready_for_review",
    gate_decision="ready_for_operator_review",
    blocking=0,
    failed=0,
):
    import operator_actions_api as api

    enable_auth(monkeypatch)
    store = InMemoryOperatorStore(roles=roles)
    pkg = InMemoryPackageStore(
        status=package_status, gate_decision=gate_decision, blocking=blocking, failed=failed
    )
    monkeypatch.setattr(api, "_store", lambda: store)
    monkeypatch.setattr(api, "_package_store", lambda: pkg)
    monkeypatch.setattr(api, "_policy_client", lambda: None)

    async def _noop(*a, **k):
        return None

    monkeypatch.setattr(api, "_audit", _noop)
    monkeypatch.setattr(api, "_notify", _noop)

    def _set_current(ik):
        store._current = ik

    return api, store, pkg, _set_current


def body_to_request(identity_key, store, body, idem="idem-" + "a" * 10):
    store._current = identity_key
    return logged_in_request(identity_key, body=body, idempotency_key=idem)
