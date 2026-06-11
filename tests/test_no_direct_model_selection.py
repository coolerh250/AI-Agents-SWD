"""Stage 38 -- agents never hardcode a real model name.

The platform contract:

* agents MUST submit an ``LLMCapabilityRequest`` via ``ModelRouter``.
* agents MUST NOT call a provider with a hard-coded real model name.
* agents MUST NOT bypass the Stage 35 budget gate.

This test grep-scans the agent sources and the development-agent
LLM planner to assert the contract holds. New code that violates
it fails CI before deployment.
"""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]

# Strings that, if present in agent source as a real provider call,
# would indicate the agent picked a model directly.
_FORBIDDEN_MODEL_LITERALS = (
    "gpt-4o",
    "gpt-4-turbo",
    "claude-3-opus",
    "claude-3-5-sonnet",
)


def _read_agent_sources() -> list[tuple[Path, str]]:
    out: list[tuple[Path, str]] = []
    agents_dir = _REPO_ROOT / "agents"
    for src in agents_dir.glob("*/src/*.py"):
        out.append((src, src.read_text(encoding="utf-8")))
    return out


def test_agents_do_not_hardcode_real_model_names():
    offenders: list[str] = []
    for path, body in _read_agent_sources():
        for literal in _FORBIDDEN_MODEL_LITERALS:
            if literal in body:
                offenders.append(f"{path.name}::{literal}")
    assert offenders == [], f"agent code hard-codes real model name(s): {offenders}"


def test_development_agent_routes_before_provider_call():
    path = (_REPO_ROOT / "agents" / "development-agent" / "src" / "llm_planner.py").read_text(
        encoding="utf-8"
    )
    # Routing helper called from _call_plan_provider + _call_proposal_provider.
    assert "_route_capability" in path
    assert "build_capability_request" in path
    assert "ModelRouter" in path
    # The router instance is stored on the pipeline.
    assert "self._router" in path


def test_development_agent_imports_routing_sdk():
    path = (_REPO_ROOT / "agents" / "development-agent" / "src" / "llm_planner.py").read_text(
        encoding="utf-8"
    )
    assert "from shared.sdk.llm_routing import" in path


def test_routing_sdk_never_imports_secret_helper():
    path = (_REPO_ROOT / "shared" / "sdk" / "llm_routing" / "router.py").read_text(encoding="utf-8")
    # The router itself never reads ENV for API keys.
    for forbidden in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "LLM_API_KEY"):
        assert forbidden not in path
