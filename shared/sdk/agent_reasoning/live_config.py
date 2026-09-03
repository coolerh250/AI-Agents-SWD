"""Step AT-M3.6B.1 -- configuration authority for the live reasoning path.

Everything a live provider call is allowed to do is decided HERE, from configuration, and never
from a request. That is the whole point of this module: ``ReasoningRequest`` carries
``provider_name`` and ``model_name``, and until AT-M3.6B.1 those fields were harmless because every
name other than ``mock`` refused. The moment a live adapter exists they would otherwise be a
caller-controlled route to paid inference against a model nobody authorized. So the runtime asks
this module what provider, what model, what generation profile and what limits apply, and the
request's own opinion is kept only as the truthful record of what was ASKED for
(``requested_provider_name``), never as what was DONE.

Two gates, deliberately separate:

``REASONING_PROVIDER``              WHICH provider class the runtime resolves. Choosing ``anthropic``
                                    means "this deployment is wired for live reasoning".
``REASONING_LIVE_NETWORK_ENABLED``  Whether a NEW live attempt may actually reach the network.
                                    Defaults to false and stays false for the whole of AT-M3.6B.1.

They are separate because the safety surface has to be able to say "configured for Anthropic, and
not permitted to call it" without those two facts collapsing into one boolean. A deployment that
merely names a provider has not been authorized to spend money, and AT-M3.6B.2 -- which is the
stage that may flip the second gate -- is a separate Product Owner decision that has not been made.

Non-production only. AT-M3.6B.1 authorizes ZERO live external calls.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping

from shared.sdk.agent_reasoning.provider import DEFAULT_REASONING_PROVIDER

#: The provider IDENTITY this slice implements. One provider, deliberately: a first live slice with
#: a fallback chain has to answer "which model actually produced this artifact" for every failure
#: path, and migration 040 freezes ``model_name`` on the invocation row precisely so that question
#: has one answer.
LIVE_PROVIDER_NAME = "anthropic"

#: The ONLY authorized model. A frozenset rather than a single string because membership is the
#: check the runtime performs, and a one-element allowlist is still an allowlist -- it is not a
#: model registry, and it must not grow into one (AT-D18 Minimal Governance Kernel).
AUTHORIZED_MODELS: frozenset[str] = frozenset({"claude-sonnet-5"})

#: What the runtime uses when configuration names no model. Still checked against the allowlist, so
#: a future edit that changes one without the other fails closed rather than silently widening.
DEFAULT_LIVE_MODEL = "claude-sonnet-5"

#: The fixed provider endpoint. Owned by the runtime, never supplied by a caller: an adapter that
#: accepts an arbitrary base URL is an adapter that can be pointed at an exfiltration endpoint by
#: whoever controls a config value. The only override is the test-transport injection point on the
#: adapter itself, which carries no URL at all.
ANTHROPIC_API_BASE = "https://api.anthropic.com"
ANTHROPIC_MESSAGES_PATH = "/v1/messages"
ANTHROPIC_API_VERSION = "2023-06-01"

#: Env var names. Named once so nothing spells them twice.
ENV_REASONING_PROVIDER = "REASONING_PROVIDER"
ENV_REASONING_MODEL = "REASONING_MODEL"
ENV_LIVE_NETWORK_ENABLED = "REASONING_LIVE_NETWORK_ENABLED"

#: The secret this adapter needs, resolved through the existing SecretProvider (env / Vault KV v2 /
#: mock-vault). The NAME is configuration; the VALUE never appears in this repository, in a request,
#: in the database, in audit, in a log or in an API response.
ANTHROPIC_SECRET_NAME = "ANTHROPIC_API_KEY"

# --- timeouts ---------------------------------------------------------------------------------

#: TCP/TLS connect bound.
CONNECT_TIMEOUT_SECONDS = 10.0

#: Total wall-clock bound on ONE provider attempt -- connect, send, wait, read, all of it. Enforced
#: as an outer async timeout as well as an httpx timeout, because an HTTP read timeout alone bounds
#: a single socket read rather than the attempt.
ATTEMPT_TIMEOUT_SECONDS = 60.0

#: The database-clock lease AT-M3.1 stamps on a claimed attempt
#: (``store.DEFAULT_LEASE_TTL_SECONDS``). Restated here as a bound to check against, NOT as a second
#: authority -- the store owns the lease and this module never sets it.
#:
#: THE ORDERING IS LOAD-BEARING: connect < attempt << lease. An attempt that outlives its lease is
#: not merely late; it gets taken over, and the takeover is what turns one logical reasoning call
#: into two billable provider calls. 10 + 60 leaves roughly 50 seconds of the 120-second lease for
#: parsing, validation and the terminal commit, so a provider that is merely slow cannot manufacture
#: a duplicate charge. The fix for a slower provider is a shorter attempt timeout, never a longer
#: lease: lengthening the lease lengthens how long a genuinely dead worker strands its invocation,
#: which is the failure migration 040 exists to remove.
LEASE_TTL_SECONDS_REFERENCE = 120.0

# --- generation ------------------------------------------------------------------------------

#: Fixed sampling temperature for every reasoning verb. Low rather than zero: these verbs ask for
#: judgement, and this is not a determinism claim. Canonical reproducibility in this architecture
#: means "the same invocation replays the same durable artifact" -- which migration 040 guarantees
#: by storing the artifact -- and never "asking the model again returns the same text".
GENERATION_TEMPERATURE = 0.2

#: Per-verb output ceiling. The provider default is never used: an unbounded completion is an
#: unbounded bill and an unbounded artifact. ``decompose_plan`` gets more because it returns a
#: structured plan rather than three prose fields.
MAX_OUTPUT_TOKENS_BY_VERB: dict[str, int] = {
    "propose": 1500,
    "critique": 1500,
    "summarize_decision": 1500,
    "decompose_plan": 4000,
}

# --- cost -------------------------------------------------------------------------------------

#: Hard ceiling on the conservative pre-flight estimate for ONE external call. Enforced before the
#: request leaves, in addition to -- not instead of -- the operator's LLMBudgetPolicy.
MAX_COST_PER_CALL_USD = 0.50

#: Ceiling across every attempt of one correlation_id. Not a separate enforcement point and
#: deliberately not a separate number to keep in sync: it is MAX_COST_PER_CALL_USD multiplied by
#: AT-M3.1's existing ``DEFAULT_MAX_ATTEMPTS`` of 3, so bounding the per-call estimate bounds this
#: by construction.
MAX_COST_PER_INVOCATION_USD = 1.50

#: A live provider resolves only when the operator has an ACTIVE budget policy carrying both of
#: these caps. The existing evaluator already blocks when no policy exists at all; requiring the two
#: aggregate caps is what stops a policy that bounds one call but not a thousand of them.
REQUIRED_POLICY_CAPS: tuple[str, ...] = ("max_cost_per_day_usd", "max_cost_per_month_usd")


class LiveReasoningConfigError(ValueError):
    """Configuration names a provider, model or posture that is not authorized."""


@dataclass(frozen=True)
class GenerationProfile:
    """The generation settings for ONE verb. Configuration-owned; never caller-supplied.

    A caller cannot set temperature, max_tokens or any other sampling parameter: none of them are
    read from ``ReasoningRequest.context``, and the egress projector rejects a context carrying a
    key it does not recognise, so a generation-parameter injection attempt does not reach the wire.
    """

    verb: str
    max_output_tokens: int
    temperature: float


def generation_profile(verb: str) -> GenerationProfile:
    """The fixed profile for ``verb``. Raises for a verb this slice does not generate."""
    if verb not in MAX_OUTPUT_TOKENS_BY_VERB:
        raise LiveReasoningConfigError(f"no generation profile for reasoning verb {verb!r}")
    return GenerationProfile(
        verb=verb,
        max_output_tokens=MAX_OUTPUT_TOKENS_BY_VERB[verb],
        temperature=GENERATION_TEMPERATURE,
    )


def _flag(raw: str | None) -> bool:
    return (raw or "").strip().lower() == "true"


@dataclass(frozen=True)
class LiveReasoningConfig:
    """The resolved live posture of this runtime. Built from configuration only."""

    provider_name: str
    model_name: str
    live_network_enabled: bool

    @property
    def model_is_authorized(self) -> bool:
        return self.model_name in AUTHORIZED_MODELS

    @classmethod
    def resolve(cls, env: Mapping[str, str] | None = None) -> "LiveReasoningConfig":
        """Read the live posture. Never raises -- an unauthorized posture is REPORTED, not thrown.

        The safety surface has to be able to describe a misconfigured runtime, and a resolver that
        raised would make ``/operations/safety`` fail exactly when an operator most needs to read
        it. Refusing a CALL is a different job, and belongs to the adapter's pre-flight.
        """
        src = env if env is not None else os.environ
        return cls(
            # The unset default is the SAME default the factory uses, so this object always
            # describes the provider the runtime would actually resolve. Defaulting to the live
            # provider here would make the safety surface report "anthropic" on a runtime that
            # resolves the mock -- a false positive on the one surface an operator checks.
            provider_name=(src.get(ENV_REASONING_PROVIDER) or "").strip().lower()
            or DEFAULT_REASONING_PROVIDER,
            model_name=(src.get(ENV_REASONING_MODEL) or "").strip() or DEFAULT_LIVE_MODEL,
            live_network_enabled=_flag(src.get(ENV_LIVE_NETWORK_ENABLED)),
        )

    def assert_callable(self) -> None:
        """Raise unless this posture may make a NEW external call.

        Order matters: the network gate is checked FIRST, so a runtime that is not permitted to call
        the provider refuses without ever consulting the model allowlist, without resolving a
        credential and without touching the network stack. AT-M3.6B.1 ships with the gate false, so
        this is the branch every live attempt in this slice takes.
        """
        if not self.live_network_enabled:
            raise LiveReasoningConfigError(
                f"live reasoning network access is disabled ({ENV_LIVE_NETWORK_ENABLED} is not "
                "'true'); no external provider call is authorized"
            )
        if self.provider_name != LIVE_PROVIDER_NAME:
            raise LiveReasoningConfigError(
                f"live reasoning is configured for provider {self.provider_name!r}, which is not "
                f"the authorized provider {LIVE_PROVIDER_NAME!r}"
            )
        if not self.model_is_authorized:
            raise LiveReasoningConfigError(
                f"model {self.model_name!r} is not in the authorized model allowlist"
            )


__all__ = [
    "ANTHROPIC_API_BASE",
    "ANTHROPIC_API_VERSION",
    "ANTHROPIC_MESSAGES_PATH",
    "ANTHROPIC_SECRET_NAME",
    "ATTEMPT_TIMEOUT_SECONDS",
    "AUTHORIZED_MODELS",
    "CONNECT_TIMEOUT_SECONDS",
    "DEFAULT_LIVE_MODEL",
    "ENV_LIVE_NETWORK_ENABLED",
    "ENV_REASONING_MODEL",
    "ENV_REASONING_PROVIDER",
    "GENERATION_TEMPERATURE",
    "GenerationProfile",
    "LEASE_TTL_SECONDS_REFERENCE",
    "LIVE_PROVIDER_NAME",
    "LiveReasoningConfig",
    "LiveReasoningConfigError",
    "MAX_COST_PER_CALL_USD",
    "MAX_COST_PER_INVOCATION_USD",
    "MAX_OUTPUT_TOKENS_BY_VERB",
    "REQUIRED_POLICY_CAPS",
    "generation_profile",
]
