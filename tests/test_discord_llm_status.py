"""Stage 30 — Discord-gateway LLM status fields.

The gateway proxies /operations/workflows/{task_id} and pulls the
``llm_assistance`` section into the per-task response. We mock the
HTTP call here so we don't need a running orchestrator.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

_ROOT = Path(__file__).resolve().parents[1]


def _load_discord_main() -> ModuleType:
    sys.path.insert(0, str(_ROOT / "apps" / "discord-gateway" / "src"))
    src = _ROOT / "apps" / "discord-gateway" / "src" / "main.py"
    spec = importlib.util.spec_from_file_location("discord_gateway_main", src)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_discord_lookup_includes_llm_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    main = _load_discord_main()
    from fastapi.testclient import TestClient
    import httpx

    # Stub the operations view payload so the discord proxy can resolve
    # without an orchestrator.
    class _StubResp:
        status_code = 200
        headers = {"content-type": "application/json"}

        def json(self) -> dict:
            return {
                "stage": "in_progress",
                "execution_status": "in_progress",
                "audit_timeline": [],
                "incidents": [],
                "progress": {"completed_agents": []},
                "github": {"pr_url": "", "dry_run": True, "status": "ok"},
                "production_executed": False,
                "code_generation": {},
                "qa_validation": {},
                "llm_assistance": {
                    "found": True,
                    "enabled": True,
                    "provider": "mock",
                    "latest_proposal": {"status": "policy_passed"},
                    "requires_human_review": True,
                    "blocked": False,
                    "policy_violations": [],
                    "usage_summary": {
                        "total_tokens": 0,
                        "estimated_cost": 0.0,
                        "records": 1,
                    },
                },
            }

    class _StubClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, _url):
            return _StubResp()

    monkeypatch.setattr(httpx, "AsyncClient", _StubClient)
    client = TestClient(main.app)
    response = client.get("/discord/tasks/t-llm")
    assert response.status_code == 200
    body = response.json()
    assert body["llm_provider"] == "mock"
    assert body["llm_proposal_status"] == "policy_passed"
    assert body["llm_policy_blocked"] is False
    assert body["llm_requires_human_review"] is True
    assert body["llm_usage_total_tokens"] == 0
    assert body["llm_policy_violations_count"] == 0
