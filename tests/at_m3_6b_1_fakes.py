"""Step AT-M3.6B.1 -- deterministic fakes for the live reasoning adapter.

AT-M3.6B.1 authorizes ZERO live external calls, so every provider behaviour this slice claims has
to be established without a socket. That is what this module is: an in-process ``httpx`` transport
that answers the adapter, a secret provider that hands out a value that is not a credential, and a
budget evaluator that uses the REAL cost estimator so the pricing entry is genuinely exercised.

The transports are built on ``httpx.MockTransport``, which intercepts at the transport layer -- the
adapter builds a real ``httpx.AsyncClient``, a real request object and a real URL, and only the
socket is replaced. That matters: a fake that replaced the adapter's ``_call`` would prove nothing
about the headers, the timeout configuration or the retry posture, which are exactly the things a
live adapter gets wrong.

Nothing here is a credential. ``FAKE_API_KEY`` is a literal test string, and the tests assert that
it never reaches the database, an audit row, an API response or an exception -- which is a claim
about the adapter, and needs a value distinctive enough to search for.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Callable

import httpx

from shared.sdk.agent_reasoning.live_config import (
    ANTHROPIC_SECRET_NAME,
    LIVE_PROVIDER_NAME,
    LiveReasoningConfig,
)
from shared.sdk.llm_budget.estimator import LLMCostEstimator
from shared.sdk.llm_budget.models import (
    DECISION_ALLOWED,
    DECISION_BLOCKED,
    ENFORCEMENT_BLOCK,
    BudgetDecision,
)
from shared.sdk.secrets.models import SecretRef


class UnauthorizedExternalCall(AssertionError):
    """A test tried to reach a host outside the local machine.

    Defined here rather than in ``conftest.py`` on purpose: pytest imports a root conftest under the
    bare name ``conftest``, so a test doing ``from tests.conftest import ...`` would get a SECOND
    module object with a DIFFERENT class of the same name, and ``pytest.raises`` would not match it.
    One definition, imported by both, removes the trap.
    """


#: Not a credential. A recognisable literal the leakage tests can search the whole world for.
FAKE_API_KEY = "test-not-a-real-anthropic-key-0123456789"


def live_config(*, enabled: bool = True, model: str | None = None) -> LiveReasoningConfig:
    """A config object for a test. ``enabled=True`` is the ONLY way any test opens the gate.

    The runtime default is closed and stays closed; a test opens it on a config object it
    constructed itself, which never touches ``os.environ`` and therefore cannot leak into another
    test or into a runtime.
    """
    return LiveReasoningConfig(
        provider_name=LIVE_PROVIDER_NAME,
        model_name=model or "claude-sonnet-5",
        live_network_enabled=enabled,
    )


# --- secrets ------------------------------------------------------------------------------------


class FakeSecretProvider:
    """Hands back a present-but-fake secret. Records every lookup so ORDER can be asserted."""

    def __init__(self, *, value: str = FAKE_API_KEY, present: bool = True) -> None:
        self._value = value
        self._present = present
        self.lookups: list[str] = []

    def get_secret(self, name: str) -> SecretRef:
        self.lookups.append(name)
        if not self._present:
            return SecretRef(name=name, present=False)
        return SecretRef(name=name, _value=self._value, present=True)

    def has_secret(self, name: str) -> bool:
        return bool(self.get_secret(name))


class ExplodingSecretProvider:
    """Fails if anybody reads a secret at all.

    Used to prove the ordering claim in AT-M3.6B.1 section 9: a refusal that is knowable from
    configuration must be reached WITHOUT resolving a credential.
    """

    def __init__(self) -> None:
        self.lookups: list[str] = []

    def get_secret(self, name: str) -> SecretRef:  # pragma: no cover - must never run
        self.lookups.append(name)
        raise AssertionError(
            f"a secret ({name}) was read on a path that must refuse before secret resolution"
        )


# --- budget -------------------------------------------------------------------------------------


class FakePolicy:
    """The shape ``get_active_policy`` returns, reduced to what the adapter reads."""

    def __init__(
        self,
        *,
        policy_id: str = "policy-test",
        max_cost_per_day_usd: float | None = 5.0,
        max_cost_per_month_usd: float | None = 25.0,
    ) -> None:
        self.policy_id = policy_id
        self.policy_name = "at-m3.6b.1-test-policy"
        self.max_cost_per_day_usd = max_cost_per_day_usd
        self.max_cost_per_month_usd = max_cost_per_month_usd
        self.enforcement_mode = ENFORCEMENT_BLOCK


#: Distinguishes "the test did not say" from "the test said there is no policy". A plain None
#: default would silently substitute a working policy for the no-policy case, which is the exact
#: branch the fail-closed test needs to reach.
_UNSET = object()


class FakeBudgetStore:
    def __init__(self, policy: Any = None) -> None:
        self.policy = policy
        self.calls = 0

    async def get_active_policy(self, *, provider: str, **_: Any) -> Any:
        self.calls += 1
        return self.policy


class FakeBudgetEvaluator:
    """Uses the REAL estimator, so the AT-M3.6B.1 pricing entry is exercised rather than mocked.

    ``force_decision`` lets a test drive the refusal branch without inventing a pricing table that
    would breach a cap -- the branch under test is the adapter's response to a refusal, not the
    evaluator's arithmetic, which has its own tests.
    """

    def __init__(
        self,
        *,
        policy: Any = _UNSET,
        force_decision: str | None = None,
        estimator: LLMCostEstimator | None = None,
    ) -> None:
        self.store = FakeBudgetStore(FakePolicy() if policy is _UNSET else policy)
        self.estimator = estimator or LLMCostEstimator()
        self.force_decision = force_decision
        self.preflights: list[dict[str, Any]] = []
        self.usages: list[dict[str, Any]] = []

    async def preflight(
        self,
        *,
        provider: str,
        model_name: str,
        estimated_prompt_tokens: int | None = None,
        estimated_completion_tokens: int | None = None,
        metadata: dict[str, Any] | None = None,
        **_: Any,
    ) -> BudgetDecision:
        prompt = int(estimated_prompt_tokens or 0)
        completion = int(estimated_completion_tokens or 0)
        cost = self.estimator.estimate_cost(
            provider=provider,
            model_name=model_name,
            prompt_tokens=prompt,
            completion_tokens=completion,
        )
        self.preflights.append(
            {
                "provider": provider,
                "model_name": model_name,
                "prompt_tokens": prompt,
                "completion_tokens": completion,
                "estimated_cost_usd": float(cost["cost_usd"]),
                "metadata": dict(metadata or {}),
            }
        )
        decision = self.force_decision or DECISION_ALLOWED
        return BudgetDecision(
            decision=decision,
            reason=None if decision == DECISION_ALLOWED else "forced_by_test",
            enforcement_mode=ENFORCEMENT_BLOCK,
            policy_id=getattr(self.store.policy, "policy_id", None),
            policy_name=getattr(self.store.policy, "policy_name", None),
            provider=provider,
            model_name=model_name,
            estimated_prompt_tokens=prompt,
            estimated_completion_tokens=completion,
            estimated_total_tokens=prompt + completion,
            estimated_cost_usd=float(cost["cost_usd"]),
            budget_remaining_usd=None,
            cap_breached=None if decision == DECISION_ALLOWED else "cost_per_task",
        )

    async def record_usage(
        self,
        *,
        provider: str,
        model_name: str,
        prompt_tokens: int,
        completion_tokens: int,
        policy_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        **_: Any,
    ) -> dict[str, Any]:
        entry = {
            "provider": provider,
            "model_name": model_name,
            "prompt_tokens": int(prompt_tokens),
            "completion_tokens": int(completion_tokens),
            "policy_id": policy_id,
            "metadata": dict(metadata or {}),
        }
        self.usages.append(entry)
        return entry


def blocked_evaluator(**kwargs: Any) -> FakeBudgetEvaluator:
    return FakeBudgetEvaluator(force_decision=DECISION_BLOCKED, **kwargs)


# --- artifacts a valid provider would return ------------------------------------------------------


def valid_artifact_json(verb: str, *, steps: int = 2) -> dict[str, Any]:
    """A minimal payload that satisfies the closed schema for ``verb``."""
    base = {
        "summary": f"{verb} summary",
        "rationale_summary": f"{verb} rationale",
        "confidence": 0.6,
    }
    if verb == "propose":
        return {**base, "recommendation": "proceed with option A", "assumptions": ["a"]}
    if verb == "critique":
        return {**base, "recommendation": "proceed with changes", "concerns": ["c"]}
    if verb == "summarize_decision":
        return {
            **base,
            "options_considered": ["option A", "option B"],
            "selected_option": "option A",
        }
    if verb == "decompose_plan":
        return {
            **base,
            "plan": {
                "objective": "deliver the goal",
                "steps": [
                    {
                        "step_key": f"step-{index}",
                        "title": f"step {index}",
                        "depends_on": [f"step-{index - 1}"] if index else [],
                    }
                    for index in range(steps)
                ],
            },
        }
    raise AssertionError(f"no fixture for verb {verb!r}")


def anthropic_body(
    payload: Any,
    *,
    input_tokens: int = 400,
    output_tokens: int = 300,
    message_id: str = "msg_test_0001",
) -> dict[str, Any]:
    """One Anthropic Messages response carrying ``payload`` as its text block."""
    text = payload if isinstance(payload, str) else json.dumps(payload)
    return {
        "id": message_id,
        "type": "message",
        "role": "assistant",
        "model": "claude-sonnet-5",
        "content": [{"type": "text", "text": text}],
        "stop_reason": "end_turn",
        "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens},
    }


# --- transports -----------------------------------------------------------------------------------


class RecordingTransport(httpx.MockTransport):
    """A MockTransport that counts and keeps every request it served.

    The call COUNT is the load-bearing part. "Replay performs zero provider calls" and "eight racers
    produce one provider call" are claims about how many times somebody was asked, and the only
    honest way to check them is to count.
    """

    def __init__(self, handler: Callable[[httpx.Request], httpx.Response]) -> None:
        self.requests: list[httpx.Request] = []

        def _wrapped(request: httpx.Request) -> httpx.Response:
            request.read()
            self.requests.append(request)
            return handler(request)

        super().__init__(_wrapped)

    @property
    def call_count(self) -> int:
        return len(self.requests)

    def payload(self, index: int = 0) -> dict[str, Any]:
        return json.loads(self.requests[index].content.decode("utf-8"))


def responding(
    body: Any, *, status_code: int = 200, headers: dict[str, str] | None = None
) -> RecordingTransport:
    """A transport that answers every request with one fixed response."""

    def handler(_: httpx.Request) -> httpx.Response:
        if isinstance(body, str):
            return httpx.Response(status_code, text=body, headers=headers)
        return httpx.Response(status_code, json=body, headers=headers)

    return RecordingTransport(handler)


def returning_artifact(verb: str, **kwargs: Any) -> RecordingTransport:
    """A transport that answers with a valid artifact for ``verb``."""
    return responding(anthropic_body(valid_artifact_json(verb), **kwargs))


def returning_text(verb_text: str, **kwargs: Any) -> RecordingTransport:
    """A transport whose text block is exactly ``verb_text`` -- valid JSON or not."""
    return responding(anthropic_body(verb_text, **kwargs))


class SlowTransport(httpx.AsyncBaseTransport):
    """Sleeps past the attempt timeout, then answers. Never actually reached by a bounded caller.

    A real ``asyncio.sleep`` rather than a stub, because the property under test is that the
    adapter's bound is a genuine wall-clock bound on the ATTEMPT and that the event loop stays free
    while it waits -- neither of which a fake clock could establish.
    """

    def __init__(self, *, delay: float, body: dict[str, Any] | None = None) -> None:
        self.delay = delay
        self.body = body or anthropic_body(valid_artifact_json("propose"))
        self.started = 0
        self.completed = 0

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.started += 1
        await asyncio.sleep(self.delay)
        self.completed += 1
        return httpx.Response(200, json=self.body)


#: The adapter asks for a schema derived from the canonical Pydantic model, so the model's own title
#: is in the outbound body and identifies the verb. Matching on that rather than on the task prose
#: keeps the fake honest: it reads the same field the provider would.
_SCHEMA_TITLE_TO_VERB = {
    "ProposalArtifact": "propose",
    "CritiqueArtifact": "critique",
    "DecisionSummaryArtifact": "summarize_decision",
    "PlanDraftArtifact": "decompose_plan",
}


def verb_aware(
    *,
    concerns: tuple[str, ...] = (),
    steps: int = 2,
    input_tokens: int = 400,
    output_tokens: int = 300,
) -> "RecordingTransport":
    """A transport that answers each verb with a valid artifact of the right type.

    ``concerns`` is what makes a discussion able to converge or not: the shipped mock always raises
    a standing concern, so a mock-mode discussion honestly never converges. A concern-free critique
    is supplied explicitly here, never substituted for a refused provider.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        content = body["messages"][0]["content"]
        verb = next(
            (v for title, v in _SCHEMA_TITLE_TO_VERB.items() if f'"title": "{title}"' in content),
            None,
        )
        if verb is None:  # pragma: no cover - a fixture bug, not a product path
            raise AssertionError("the outbound request names no known artifact schema")
        payload = valid_artifact_json(verb, steps=steps)
        if verb == "critique":
            payload["concerns"] = list(concerns)
        return httpx.Response(
            200,
            json=anthropic_body(
                payload,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                message_id=f"msg_{verb}",
            ),
        )

    return RecordingTransport(handler)


class GatedTransport(httpx.AsyncBaseTransport):
    """Holds a response until a test releases it, so a race can be driven deterministically.

    Sleeping for a fixed interval would make the zombie and concurrency tests depend on timing, and
    a race test that depends on timing proves whatever the machine happened to do that run. An
    explicit gate makes the interleaving the test asserts the interleaving that occurred.
    """

    def __init__(self, *, body: dict[str, Any] | None = None) -> None:
        self.gate = asyncio.Event()
        self.arrived = asyncio.Event()
        self.body = body or anthropic_body(valid_artifact_json("propose"))
        self.call_count = 0

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.call_count += 1
        self.arrived.set()
        await self.gate.wait()
        return httpx.Response(200, json=self.body)

    def release(self) -> None:
        self.gate.set()


def secret_name() -> str:
    return ANTHROPIC_SECRET_NAME


__all__ = [
    "FAKE_API_KEY",
    "ExplodingSecretProvider",
    "FakeBudgetEvaluator",
    "FakeBudgetStore",
    "FakePolicy",
    "FakeSecretProvider",
    "GatedTransport",
    "RecordingTransport",
    "SlowTransport",
    "UnauthorizedExternalCall",
    "anthropic_body",
    "blocked_evaluator",
    "live_config",
    "responding",
    "returning_artifact",
    "returning_text",
    "secret_name",
    "valid_artifact_json",
    "verb_aware",
]
