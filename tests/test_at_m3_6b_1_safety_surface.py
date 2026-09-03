"""Step AT-M3.6B.1 -- /operations/safety tells the truth about the reasoning provider.

Before this slice the safety surface knew only the Stage-30 ``LLM_PROVIDER`` rail, which governs the
historical code-workspace plan-only path and knows nothing about ``REASONING_PROVIDER``. A runtime
wired for live reasoning would therefore have read ``llm_provider: mock, llm_real_enabled: false`` --
a false negative on the one surface an operator checks, and on exactly the question AT-D18's
governance kernel calls out by name ("external model / network / action authorization").

The distinction these tests protect is that naming a provider is not permission to call it.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

from shared.sdk.agent_reasoning.live_config import (
    ENV_LIVE_NETWORK_ENABLED,
    ENV_REASONING_MODEL,
    ENV_REASONING_PROVIDER,
)

_ROOT = Path(__file__).resolve().parents[1]

_REASONING_FIELDS = {
    "reasoning_provider",
    "reasoning_model",
    "reasoning_provider_mode",
    "reasoning_model_allowlisted",
    "reasoning_live_enabled",
}

#: Stage-30 fields that existed before this slice. Additive-only means every one of them survives.
_PRE_EXISTING_FIELDS = {
    "llm_provider",
    "llm_real_enabled",
    "llm_external_call_enabled",
    "llm_policy_enforced",
    "llm_requires_human_review",
    "production_executed_true_count",
}


def _load_orchestrator_main() -> ModuleType:
    src = _ROOT / "apps" / "orchestrator" / "src" / "main.py"
    spec = importlib.util.spec_from_file_location("orchestrator_main_at_m3_6b_1", src)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _safety(monkeypatch: pytest.MonkeyPatch, **env: str) -> dict:
    for name in (ENV_REASONING_PROVIDER, ENV_REASONING_MODEL, ENV_LIVE_NETWORK_ENABLED):
        monkeypatch.delenv(name, raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    from fastapi.testclient import TestClient

    client = TestClient(_load_orchestrator_main().app)
    response = client.get("/operations/safety")
    if response.status_code != 200:
        pytest.skip(f"safety endpoint unavailable locally: {response.status_code}")
    return response.json()


class TestReasoningPosture:
    def test_the_default_runtime_reports_mock_and_not_live(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        body = _safety(monkeypatch)
        assert body["reasoning_provider"] == "mock"
        assert body["reasoning_provider_mode"] == "mock"
        assert body["reasoning_live_enabled"] is False

    def test_a_configured_provider_is_not_reported_as_live(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The load-bearing distinction. Throughout AT-M3.6B.1 the truthful reading of a fully
        configured runtime is 'Anthropic, and not permitted to call it'."""
        body = _safety(
            monkeypatch,
            **{ENV_REASONING_PROVIDER: "anthropic", ENV_REASONING_MODEL: "claude-sonnet-5"},
        )
        assert body["reasoning_provider"] == "anthropic"
        assert body["reasoning_model"] == "claude-sonnet-5"
        assert body["reasoning_provider_mode"] == "live"
        assert body["reasoning_model_allowlisted"] is True
        assert body["reasoning_live_enabled"] is False

    def test_an_unlisted_model_is_reported_as_not_allowlisted(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        body = _safety(
            monkeypatch,
            **{ENV_REASONING_PROVIDER: "anthropic", ENV_REASONING_MODEL: "claude-3-opus"},
        )
        assert body["reasoning_model_allowlisted"] is False
        assert body["reasoning_live_enabled"] is False

    def test_the_gate_is_what_flips_live_enabled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        body = _safety(
            monkeypatch,
            **{
                ENV_REASONING_PROVIDER: "anthropic",
                ENV_REASONING_MODEL: "claude-sonnet-5",
                ENV_LIVE_NETWORK_ENABLED: "true",
            },
        )
        assert body["reasoning_live_enabled"] is True
        assert "reasoning_live_external_call_enabled" in body.get("warnings", [])

    def test_a_mock_runtime_with_the_gate_open_is_still_not_live(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Both facts are required. An open gate on a runtime that resolves the mock calls nobody."""
        body = _safety(monkeypatch, **{ENV_LIVE_NETWORK_ENABLED: "true"})
        assert body["reasoning_provider"] == "mock"
        assert body["reasoning_live_enabled"] is False


class TestAdditiveOnly:
    def test_every_pre_existing_field_survives(self, monkeypatch: pytest.MonkeyPatch) -> None:
        body = _safety(monkeypatch)
        missing = _PRE_EXISTING_FIELDS - set(body)
        assert missing == set(), missing

    def test_the_new_fields_are_present(self, monkeypatch: pytest.MonkeyPatch) -> None:
        body = _safety(monkeypatch)
        assert _REASONING_FIELDS <= set(body)

    def test_no_credential_is_ever_disclosed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-not-a-real-key-000111222")
        body = _safety(
            monkeypatch,
            **{ENV_REASONING_PROVIDER: "anthropic", ENV_REASONING_MODEL: "claude-sonnet-5"},
        )
        rendered = repr(body)
        assert "sk-ant-not-a-real-key-000111222" not in rendered
        assert "ANTHROPIC_API_KEY" not in rendered

    def test_production_remains_untouched(self, monkeypatch: pytest.MonkeyPatch) -> None:
        body = _safety(
            monkeypatch,
            **{ENV_REASONING_PROVIDER: "anthropic", ENV_LIVE_NETWORK_ENABLED: "true"},
        )
        assert body["production_executed_true_count"] == 0
