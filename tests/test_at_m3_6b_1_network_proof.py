"""Step AT-M3.6B.1 -- evidence that this slice makes zero external calls, official or diagnostic.

Step 65F ended as PASS_WITH_GAPS because two "safe-looking" diagnostic probes went round the
platform's own rail, and the 65F-C guardrail that followed is explicit: every external network call
counts, diagnostic ones included, and none may be made without its own authorization. AT-M3.6B.1
authorizes zero. This module is where that claim stops being an assertion in a report and becomes
something the suite can fail on.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import httpx
import pytest

from shared.sdk.agent_reasoning.anthropic_provider import AnthropicReasoningProvider
from shared.sdk.agent_reasoning.live_config import (
    ANTHROPIC_API_BASE,
    ENV_LIVE_NETWORK_ENABLED,
    ENV_REASONING_PROVIDER,
)
from shared.sdk.agent_reasoning.models import ReasoningRequest
from shared.sdk.agent_reasoning.provider import LiveProviderError, get_reasoning_provider
from tests.at_m3_6b_1_fakes import (
    ExplodingSecretProvider,
    FakeBudgetEvaluator,
    UnauthorizedExternalCall,
)

ROOT = Path(__file__).resolve().parents[1]
SLICE_MODULES = [
    ROOT / "shared" / "sdk" / "agent_reasoning" / "anthropic_provider.py",
    ROOT / "shared" / "sdk" / "agent_reasoning" / "live_config.py",
    ROOT / "shared" / "sdk" / "agent_reasoning" / "egress.py",
    ROOT / "shared" / "sdk" / "agent_reasoning" / "provider.py",
    ROOT / "shared" / "sdk" / "agent_reasoning" / "service.py",
    ROOT / "shared" / "sdk" / "agent_reasoning" / "store.py",
    ROOT / "shared" / "sdk" / "agent_reasoning" / "models.py",
]


@pytest.mark.asyncio
class TestTheGuardItself:
    """A guard that cannot fail proves nothing, so the first thing to establish is that it trips."""

    async def test_a_non_local_dns_lookup_fails_the_test(self) -> None:
        import socket

        with pytest.raises(UnauthorizedExternalCall):
            socket.getaddrinfo("api.anthropic.com", 443)

    async def test_a_non_local_socket_connection_fails_the_test(self) -> None:
        import socket

        sock = socket.socket()
        try:
            with pytest.raises(UnauthorizedExternalCall):
                sock.connect(("93.184.216.34", 80))
        finally:
            sock.close()

    async def test_loopback_is_untouched(self) -> None:
        """PostgreSQL and Redis are local. Blocking them would break the real-database suites."""
        import socket

        assert socket.getaddrinfo("127.0.0.1", 5432)


@pytest.mark.asyncio
class TestTheRuntimeDefaultCannotCallAnybody:
    async def test_the_configured_live_runtime_refuses_before_any_socket(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The real factory, the real config, the real adapter -- and a closed gate.

        No transport is injected here: if the gate did not stop the call, this test would attempt a
        genuine connection to Anthropic and the guard above would fail it. That is the point.
        """
        monkeypatch.setenv(ENV_REASONING_PROVIDER, "anthropic")
        monkeypatch.delenv(ENV_LIVE_NETWORK_ENABLED, raising=False)
        provider = get_reasoning_provider()
        assert isinstance(provider, AnthropicReasoningProvider)
        assert provider.mode == "live"

        provider._secret_provider = ExplodingSecretProvider()
        provider._budget_evaluator = FakeBudgetEvaluator()
        request = ReasoningRequest(verb="propose", context={"goal_statement": "x"})
        with pytest.raises(LiveProviderError) as caught:
            await provider.propose(request)
        assert caught.value.failure_category == "provider_disabled"

    async def test_no_credential_is_validated_against_the_provider(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Section 49: secret correctness is never checked by calling Anthropic.

        Even with the gate open and a credential present, nothing in the adapter contacts the
        provider except the one reasoning request itself -- no model-list call, no health check, no
        auth probe. With a fake transport in place, the call count is the whole proof.
        """
        from tests.at_m3_6b_1_fakes import FakeSecretProvider, live_config, returning_artifact

        transport = returning_artifact("propose")
        provider = AnthropicReasoningProvider(
            config=live_config(enabled=True),
            secret_provider=FakeSecretProvider(value="wrong-key-entirely"),
            budget_evaluator=FakeBudgetEvaluator(),
            transport=transport,
        )
        await provider.preflight(ReasoningRequest(verb="propose", context={"goal_statement": "x"}))
        assert transport.call_count == 0
        await provider.propose(ReasoningRequest(verb="propose", context={"goal_statement": "x"}))
        assert transport.call_count == 1


class TestStaticNetworkPosture:
    def test_tls_verification_is_never_disabled(self) -> None:
        for path in SLICE_MODULES:
            source = path.read_text(encoding="utf-8")
            assert "verify=False" not in source, path
            assert "verify = False" not in source, path

    def test_the_only_external_endpoint_is_the_fixed_https_constant(self) -> None:
        assert ANTHROPIC_API_BASE == "https://api.anthropic.com"
        assert ANTHROPIC_API_BASE.startswith("https://")

    def test_no_slice_module_contains_another_external_url(self) -> None:
        """A second endpoint literal is how a configurable base URL sneaks back in."""
        pattern = re.compile(r"https?://[A-Za-z0-9.\-]+")
        for path in SLICE_MODULES:
            for found in pattern.findall(path.read_text(encoding="utf-8")):
                assert found in {
                    ANTHROPIC_API_BASE,
                    "https://errors.pydantic.dev",
                }, f"{path}: {found}"

    def test_the_endpoint_is_not_read_from_the_environment(self) -> None:
        """A caller-or-config-supplied base URL is an adapter that can be pointed anywhere."""
        source = (ROOT / "shared" / "sdk" / "agent_reasoning" / "live_config.py").read_text(
            encoding="utf-8"
        )
        tree = ast.parse(source)
        env_reads = {
            node.args[0].value
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "get"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        }
        assert not {name for name in env_reads if "URL" in name or "BASE" in name}, env_reads

    def test_no_vendor_sdk_was_added_as_a_dependency(self) -> None:
        """AT-M3.6B.1 uses httpx, which the project already depends on."""
        requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8").lower()
        assert "httpx" in requirements
        for forbidden in ("anthropic", "openai"):
            assert not re.search(rf"(?m)^{forbidden}\b", requirements), forbidden


class TestNoM4Capability:
    def test_the_slice_cannot_execute_anything(self) -> None:
        """A reasoning adapter that can start a process is not a reasoning adapter."""
        forbidden = ("subprocess", "os.system", "popen", "shutil.rmtree", "eval(", "exec(")
        for path in SLICE_MODULES:
            source = path.read_text(encoding="utf-8").lower()
            for marker in forbidden:
                assert marker not in source, f"{path}: {marker}"

    def test_no_slice_module_imports_a_git_deployment_or_workspace_surface(self) -> None:
        for path in SLICE_MODULES:
            tree = ast.parse(path.read_text(encoding="utf-8"))
            imported = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    imported.add(node.module)
                elif isinstance(node, ast.Import):
                    imported.update(alias.name for alias in node.names)
            for module in imported:
                assert "code_workspace" not in module, f"{path}: {module}"
                assert "github" not in module, f"{path}: {module}"
                assert "deployment" not in module, f"{path}: {module}"
                assert "approval" not in module, f"{path}: {module}"


@pytest.mark.asyncio
class TestNoRealClientEscapes:
    async def test_a_missing_transport_still_cannot_reach_the_network(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Belt and braces: with the gate OPEN and no mock transport, the guard is the last line.

        This is the only test in the slice that would attempt a genuine connection if every other
        control failed, and it asserts that the attempt is refused rather than completed.
        """
        from tests.at_m3_6b_1_fakes import FakeSecretProvider, live_config

        provider = AnthropicReasoningProvider(
            config=live_config(enabled=True),
            secret_provider=FakeSecretProvider(),
            budget_evaluator=FakeBudgetEvaluator(),
            transport=None,
        )
        with pytest.raises((LiveProviderError, httpx.HTTPError, AssertionError)) as caught:
            await provider.propose(
                ReasoningRequest(verb="propose", context={"goal_statement": "x"})
            )
        # Whatever surfaced, no response came back from Anthropic.
        assert "claude" not in str(caught.value).lower()
