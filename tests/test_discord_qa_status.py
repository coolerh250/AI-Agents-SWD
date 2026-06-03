"""Stage 29 — /discord/tasks/{task_id} surfaces QA fields."""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient


# Discord-gateway main.py uses ``from client import …`` and
# ``from parser import …`` so the fixture preloads the sibling
# modules under their bare names before loading main.py — same
# pattern as tests/test_discord_operations_lookup.py.
@pytest.fixture
def discord_gateway():
    import importlib.util
    import sys
    from pathlib import Path

    src = Path(__file__).resolve().parents[1] / "apps" / "discord-gateway" / "src"
    sys.path.insert(0, str(src))
    try:
        for name in ("parser", "client"):
            spec = importlib.util.spec_from_file_location(name, src / f"{name}.py")
            assert spec is not None and spec.loader is not None
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            spec.loader.exec_module(module)
        main_spec = importlib.util.spec_from_file_location("discord_gateway_main", src / "main.py")
        assert main_spec is not None and main_spec.loader is not None
        main_module = importlib.util.module_from_spec(main_spec)
        sys.modules["discord_gateway_main"] = main_module
        main_spec.loader.exec_module(main_module)
        return main_module
    finally:
        if str(src) in sys.path:
            sys.path.remove(str(src))


@pytest.fixture
def discord_gateway_app(discord_gateway):
    return discord_gateway.app


def _orchestrator_payload() -> dict[str, Any]:
    """Mimic /operations/workflows/{task_id} response with a qa_validation block."""
    return {
        "task_id": "t1",
        "stage": "qa_auto_fix",
        "execution_status": "qa_auto_fix",
        "production_executed": False,
        "progress": {"completed_agents": ["intake-agent"]},
        "github": {"pr_url": "", "dry_run": True, "status": "pending"},
        "audit_timeline": [],
        "incidents": [],
        "code_generation": {
            "found": True,
            "workspace": {"workspace_id": "ws-1", "generator_mode": "deterministic_template"},
            "status": "ready_for_pr_draft",
            "changed_files": ["apps/demo-generated/x.py"],
            "pr_draft": {"status": "ready"},
            "validation_result": {"status": "passed"},
            "blocked_reason": "",
        },
        "qa_validation": {
            "found": True,
            "latest_run": {
                "qa_run_id": "run-1",
                "status": "auto_fix_requested",
                "final_result": "not_applicable",
                "blocking_findings": 1,
                "auto_fix_attempts": 0,
                "max_auto_fix_attempts": 2,
            },
            "status": "auto_fix_requested",
            "final_result": "not_applicable",
            "findings": [{"finding_id": "f-1", "severity": "error"}],
            "blocking_findings_count": 1,
            "auto_fix_requests": [],
            "auto_fix_attempts": 0,
            "max_auto_fix_attempts": 2,
            "blocked_for_human_review": False,
            "qa_passed": False,
        },
    }


def test_discord_task_lookup_exposes_qa_status(monkeypatch, discord_gateway_app, discord_gateway):
    """Patch httpx so the discord-gateway thinks the orchestrator returned the qa payload."""

    class _StubResponse:
        status_code = 200
        headers = {"content-type": "application/json"}

        def json(self):
            return _orchestrator_payload()

    class _StubClient:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, _url):
            return _StubResponse()

    monkeypatch.setattr(httpx, "AsyncClient", _StubClient)

    # Patch NotificationDeliveryStore to return no deliveries.
    import sys

    discord_module = sys.modules["discord_gateway_main"]

    class _NDStub:
        async def list_deliveries(self, **kw):
            return []

    monkeypatch.setattr(discord_module, "NotificationDeliveryStore", lambda *a, **kw: _NDStub())

    response = TestClient(discord_gateway_app).get("/discord/tasks/t1")
    assert response.status_code == 200
    body = response.json()
    assert body["qa_status"] == "auto_fix_requested"
    assert body["qa_final_result"] == "not_applicable"
    assert body["qa_findings_count"] == 1
    assert body["blocking_findings_count"] == 1
    assert body["auto_fix_attempts"] == 0
    assert body["blocked_for_human_review"] is False
    assert body["sandbox"] is True
