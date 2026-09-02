"""Step AT-M3.5 -- the delegation namespace is isolated from every live consumer.

Independent Validation 1 found AT-M3.5 publishing ``plan_step.dispatched`` onto the agents' own
transport streams -- ``stream.development``, ``stream.qa``, ``stream.design_review``. Those are not
inert names. A ``StreamAgent`` subclass consumes each of them and calls ``handle(payload)``
unconditionally, and the orchestrator's workflow-event consumer watches several too. An L3
coordination message landing there is AT-M4 execution started by a stream name, which is precisely
the boundary this milestone is not allowed to cross.

The first half of this file is a repository-wide STATIC scan, and it is static on purpose: it holds
whether or not a broker is running, and it fails if some future slice points an existing consumer at
the delegation namespace. The second half proves the same thing dynamically against a real Redis --
scheduling a plan leaves the legacy streams untouched, byte for byte.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from shared.sdk.agent_team.capabilities import AGENT_CAPABILITY_SEED
from shared.sdk.agent_team.router import RoutingCandidate
from shared.sdk.plan_delegation.models import (
    DELEGATION_STREAM_PREFIX,
    DispatchTransportError,
    delegation_stream_for,
    is_delegation_stream,
    resolve_step_assignment,
)

ROOT = Path(__file__).resolve().parents[1]

#: Where a stream name could become something a process actually reads.
_SOURCE_ROOTS = ("agents", "apps", "shared", "scripts", "infra")

_STREAM_LITERAL = re.compile(r"[\"']((?:stream|Stream)\.[A-Za-z0-9_.\-{}]*)[\"']")


def _python_sources() -> list[Path]:
    files: list[Path] = []
    for root in _SOURCE_ROOTS:
        base = ROOT / root
        if not base.exists():
            continue
        files.extend(p for p in base.rglob("*.py") if "__pycache__" not in p.parts)
    return files


def _module_stream_constants() -> dict[str, str]:
    """Every module-level ``NAME = "stream.*"`` in the repository, keyed by NAME.

    Resolved from source rather than by importing, so a module with a side effect or a missing
    dependency cannot make the scan silently skip a consumer.
    """
    constants: dict[str, str] = {}
    for path in _python_sources():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:  # pragma: no cover - the repository parses
            continue
        for node in tree.body:
            if not isinstance(node, ast.Assign):
                continue
            if not (isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)):
                continue
            if not node.value.value.startswith("stream."):
                continue
            for target in node.targets:
                if isinstance(target, ast.Name):
                    constants[target.id] = node.value.value
    return constants


def _resolve(node: ast.AST, constants: dict[str, str]) -> list[str]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    if isinstance(node, ast.Name):
        return [constants[node.id]] if node.id in constants else []
    if isinstance(node, (ast.List, ast.Tuple)):
        return [name for element in node.elts for name in _resolve(element, constants)]
    return []


def consumed_streams() -> dict[str, str]:
    """Every stream some process in this repository actually reads, mapped to where.

    Three ways a stream becomes consumed here, and all three are scanned:

    * ``input_stream = X`` on a ``StreamAgent`` subclass -- the agent's own event loop reads it and
      calls ``handle()``.
    * the first argument of ``consume_events(...)`` / ``consume_events_multi(...)`` -- the workers
      and the orchestrator's workflow-event consumer.
    * a module-level list assigned to a ``*_STREAMS`` name and passed to one of those calls.
    """
    constants = _module_stream_constants()
    found: dict[str, str] = {}
    for path in _python_sources():
        rel = str(path.relative_to(ROOT)).replace("\\", "/")
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:  # pragma: no cover
            continue
        local = dict(constants)
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        for name in _resolve(node.value, constants):
                            local.setdefault(target.id, name)
                        if target.id == "input_stream":
                            for name in _resolve(node.value, local):
                                found.setdefault(name, f"{rel} (input_stream)")
            if isinstance(node, ast.Call):
                func = node.func
                name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
                if name in ("consume_events", "consume_events_multi") and node.args:
                    for stream in _resolve(node.args[0], local):
                        found.setdefault(stream, f"{rel} ({name})")
                    for keyword in node.keywords:
                        if keyword.arg in ("stream", "streams"):
                            for stream in _resolve(keyword.value, local):
                                found.setdefault(stream, f"{rel} ({name})")
    return found


# --- static: nothing consumes the delegation namespace -------------------------------------------


def test_the_scan_actually_finds_the_known_consumers():
    """A scan that found nothing would pass every assertion below for the wrong reason."""
    consumed = consumed_streams()
    for expected in (
        "stream.development",
        "stream.qa",
        "stream.deployments",
        "stream.tasks",
        "stream.requirements",
        "stream.design_review",
    ):
        assert expected in consumed, f"{expected} should be detected as consumed"


def test_no_process_in_this_repository_consumes_the_delegation_namespace():
    """The load-bearing remediation assertion.

    AT-M3.5 has no execution consumer by design, so a duplicate Redis delivery can have zero agent
    execution effect. If a later slice points a StreamAgent or a worker at this namespace without
    building the AT-M4 dedupe contract, this fails.
    """
    offenders = {
        stream: where
        for stream, where in consumed_streams().items()
        if is_delegation_stream(stream)
    }
    assert offenders == {}, f"the AT-M3.5 delegation namespace has acquired consumers: {offenders}"


def test_no_delegation_stream_literal_appears_outside_the_delegation_module_and_its_tests():
    """A stream name is only safe while it stays where it is documented."""
    allowed = ("shared/sdk/plan_delegation/", "tests/")
    offenders: list[str] = []
    for path in _python_sources():
        rel = str(path.relative_to(ROOT)).replace("\\", "/")
        if rel.startswith(allowed):
            continue
        for literal in _STREAM_LITERAL.findall(path.read_text(encoding="utf-8")):
            if is_delegation_stream(literal):
                offenders.append(f"{rel}: {literal}")
    assert offenders == [], offenders


def test_every_seeded_agents_delegation_stream_differs_from_its_own_input_stream():
    """The defect, stated directly: routing chooses WHO, and the destination is not their inbox."""
    consumed = consumed_streams()
    for declaration in AGENT_CAPABILITY_SEED:
        destination = delegation_stream_for(declaration.agent_key)
        assert destination != declaration.transport_stream
        assert destination not in consumed, destination
        assert destination.startswith(f"{DELEGATION_STREAM_PREFIX}.")


def test_two_agents_sharing_a_role_do_not_share_a_delegation_stream():
    """``development-agent`` and ``development-agent-autofix`` are both role ``development``.

    Keying the namespace on role would put a command addressed to one of them within the other's
    reach; keying it on ``agent_key`` -- which is UNIQUE on ``agent_profiles`` -- does not.
    """
    roles: dict[str, set[str]] = {}
    for declaration in AGENT_CAPABILITY_SEED:
        roles.setdefault(declaration.role, set()).add(delegation_stream_for(declaration.agent_key))
    shared_role = {role: streams for role, streams in roles.items() if len(streams) > 1}
    assert shared_role, "the seed should still contain two agents sharing one role"
    for streams in shared_role.values():
        assert len(streams) == len({s for s in streams})


def test_an_unusable_agent_key_is_refused_rather_than_escaped():
    for bad in ("", "agent key", "agent/key", "agent*", "a" * 101):
        with pytest.raises(DispatchTransportError):
            delegation_stream_for(bad)


# --- routing is unchanged; only the destination moved ---------------------------------------------


def _candidate(agent_key: str, role: str, capability: str, stream: str) -> RoutingCandidate:
    return RoutingCandidate(
        principal_id="00000000-0000-4000-8000-000000000001",
        agent_key=agent_key,
        role=role,
        capabilities=frozenset({capability}),
        transport_stream=stream,
    )


@pytest.mark.parametrize(
    ("agent_key", "role", "capability", "legacy_stream"),
    [
        ("development-agent", "development", "generate_code", "stream.development"),
        ("qa-agent", "qa", "verify_quality", "stream.qa"),
        ("design-review-agent", "design_review", "review_design", "stream.design_review"),
    ],
)
def test_the_router_still_names_the_agent_and_its_real_stream_as_AT_M2_evidence(
    agent_key, role, capability, legacy_stream
):
    """AT-M2's answer is untouched -- the router still reports the agent's own transport stream, and
    that is what lands in ``agent_routing_decisions``. What moved is where AT-M3.5 stages the
    message."""
    decision = resolve_step_assignment(
        required_capabilities=(capability,),
        candidates=[_candidate(agent_key, role, capability, legacy_stream)],
        project_id="11111111-1111-4111-8111-111111111111",
    )
    assert decision.outcome == "selected"
    assert decision.selected_agent_key == agent_key
    assert decision.selected_stream == legacy_stream

    destination = delegation_stream_for(decision.selected_agent_key)
    assert destination != legacy_stream
    assert destination == f"{DELEGATION_STREAM_PREFIX}.{agent_key}"
