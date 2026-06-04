"""Stage 31 -- discord-gateway approval-policy proxies.

The gateway proxies the orchestrator's approval endpoints. We mock
httpx so no orchestrator is needed.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

_ROOT = Path(__file__).resolve().parents[1]


def _load_discord_main() -> ModuleType:
    sys.path.insert(0, str(_ROOT / "apps" / "discord-gateway" / "src"))
    src = _ROOT / "apps" / "discord-gateway" / "src" / "main.py"
    spec = importlib.util.spec_from_file_location("discord_gateway_main_stage31", src)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _stub_httpx(monkeypatch, *, expected_url=None, post_response=None, get_response=None):
    import httpx

    class _Resp:
        def __init__(self, payload, status=200) -> None:
            self.status_code = status
            self.headers = {"content-type": "application/json"}
            self._payload = payload

        def json(self):
            return self._payload

        @property
        def text(self):
            import json

            return json.dumps(self._payload)

    captured: dict = {}

    class _StubClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, json=None):
            captured["url"] = url
            captured["json"] = json
            payload, status = post_response or ({"ok": True}, 200)
            return _Resp(payload, status)

        async def get(self, url):
            captured["url"] = url
            payload, status = get_response or ({"ok": True}, 200)
            return _Resp(payload, status)

    monkeypatch.setattr(httpx, "AsyncClient", _StubClient)
    return captured


def test_discord_create_approval_policy_forwards_to_orchestrator(monkeypatch):
    main = _load_discord_main()
    from fastapi.testclient import TestClient

    captured = _stub_httpx(monkeypatch, post_response=({"policy": {"policy_id": "p1"}}, 200))
    client = TestClient(main.app)
    response = client.post(
        "/discord/approval-policies",
        json={
            "task_id": "t1",
            "approval_mode": "per_action",
            "granted_by": "discord-operator",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["sandbox"] is True
    assert body["policy"]["policy_id"] == "p1"
    assert "/approval-policies" in captured["url"]


def test_discord_list_approval_policies_uses_operations_view(monkeypatch):
    main = _load_discord_main()
    from fastapi.testclient import TestClient

    captured = _stub_httpx(
        monkeypatch,
        get_response=(
            {"task_id": "t1", "count": 0, "policies": [], "promotions": []},
            200,
        ),
    )
    client = TestClient(main.app)
    response = client.get("/discord/approval-policies/t1")
    assert response.status_code == 200
    body = response.json()
    assert body["sandbox"] is True
    assert body["task_id"] == "t1"
    assert "/operations/approval-policies/t1" in captured["url"]


def test_discord_revoke_proxies_to_orchestrator(monkeypatch):
    main = _load_discord_main()
    from fastapi.testclient import TestClient

    captured = _stub_httpx(monkeypatch, post_response=({"policy": {"status": "revoked"}}, 200))
    client = TestClient(main.app)
    response = client.post(
        "/discord/approval-policies/pol-1/revoke",
        json={"revoked_by": "discord-operator", "reason": "test"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["sandbox"] is True
    assert "/revoke" in captured["url"]


def test_discord_approve_llm_proposal_proxies_correctly(monkeypatch):
    main = _load_discord_main()
    from fastapi.testclient import TestClient

    captured = _stub_httpx(monkeypatch, post_response=({"approval": {"status": "approved"}}, 200))
    client = TestClient(main.app)
    response = client.post(
        "/discord/llm/proposals/p-1/approve",
        json={"approved_by": "discord-operator"},
    )
    assert response.status_code == 200
    assert "/approval/approve" in captured["url"]


def test_discord_promote_llm_proposal_proxies_with_promoted_by(monkeypatch):
    main = _load_discord_main()
    from fastapi.testclient import TestClient

    captured = _stub_httpx(monkeypatch, post_response=({"promotion": {"status": "promoted"}}, 200))
    client = TestClient(main.app)
    response = client.post(
        "/discord/llm/proposals/p-1/promote",
        json={"task_id": "t1", "promoted_by": "discord-operator"},
    )
    assert response.status_code == 200
    assert "/promote" in captured["url"]
    assert captured["json"]["promoted_by"] == "discord-operator"


def test_discord_tasks_lookup_surfaces_approval_fields(monkeypatch):
    """The /discord/tasks/{task_id} response carries approval_mode,
    delegated_actions_used, latest_approval_decision, llm_promotion_status."""
    main = _load_discord_main()
    from fastapi.testclient import TestClient

    _stub_httpx(
        monkeypatch,
        get_response=(
            {
                "stage": "in_progress",
                "execution_status": "in_progress",
                "audit_timeline": [],
                "incidents": [],
                "progress": {"completed_agents": []},
                "github": {"pr_url": "", "dry_run": True, "status": "ok"},
                "production_executed": False,
                "code_generation": {},
                "qa_validation": {},
                "llm_assistance": {},
                "approval_policy": {
                    "active_policies": [{"policy_id": "pol-1"}],
                    "approval_mode": "delegated",
                    "decisions": [{"decision_id": "d-1", "decision": "delegated"}],
                    "delegated_actions_used": 1,
                    "delegated_actions_remaining": 4,
                    "promotions": [{"promotion_id": "pr-1", "status": "promoted"}],
                },
            },
            200,
        ),
    )
    client = TestClient(main.app)
    response = client.get("/discord/tasks/t1")
    assert response.status_code == 200
    body = response.json()
    assert body["approval_mode"] == "delegated"
    assert body["active_approval_policy"]["policy_id"] == "pol-1"
    assert body["delegated_actions_used"] == 1
    assert body["delegated_actions_remaining"] == 4
    assert body["latest_approval_decision"]["decision"] == "delegated"
    assert body["llm_promotion_status"] == "promoted"
