"""Step AT-M3.6B.1 -- the Anthropic live reasoning adapter.

One adapter, behind the existing ``ReasoningProvider`` protocol. It changes WHO authors a typed
reasoning artifact and nothing else: ``ReasoningService`` still owns the durable claim, the lease,
the attempt accounting, the terminal write and the replay, and ``TeamMessage`` / ``PlanRevision``
are still the only places an artifact becomes business state. There is no ``AnthropicReasoningService``
and no second reasoning store, because a second authority is how two answers to "what did the team
decide" get created.

AT-M3.6B.1 AUTHORIZES ZERO LIVE EXTERNAL CALLS. ``REASONING_LIVE_NETWORK_ENABLED`` defaults to
false, and :meth:`AnthropicReasoningProvider.preflight` refuses on that gate before it looks at a
model name, before it resolves a credential and before it constructs an HTTP client. Every test in
this slice drives the adapter through an injected in-process transport. Enabling the gate is
AT-M3.6B.2, which is a separate Product Owner decision that has not been made.

ORDER OF OPERATIONS, and why it is this order:

    network gate  ->  provider/model allowlist  ->  generation profile  ->  egress projection
    ->  outbound size  ->  active budget policy          [ preflight, BEFORE the attempt is claimed ]
    ->  budget evaluator + per-call cost cap  ->  credential  ->  wire  [ inside the verb ]

Everything knowable without spending anything happens first, so a refusal costs nothing. The
credential is resolved LAST, immediately before the request that needs it: reading a real secret in
order to discover that live calls are disabled would touch Vault for no reason and would make the
disabled path depend on the secret backend being reachable.

WHAT NEVER LEAVES THIS MODULE. The API key -- it exists as a ``SecretRef`` until the moment a header
is built, is never returned, never logged, never persisted and never placed in an exception. The
outbound payload -- it is not stored, not logged and not audited. The raw completion -- it is parsed
in memory and discarded; only the validated typed artifact survives, and only through the canonical
terminal write.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Mapping

from shared.sdk.agent_reasoning.egress import (
    EgressViolationError,
    approved_outbound_context,
)
from shared.sdk.agent_reasoning.live_config import (
    ANTHROPIC_API_BASE,
    ANTHROPIC_API_VERSION,
    ANTHROPIC_MESSAGES_PATH,
    ANTHROPIC_SECRET_NAME,
    ATTEMPT_TIMEOUT_SECONDS,
    CONNECT_TIMEOUT_SECONDS,
    LIVE_PROVIDER_NAME,
    MAX_COST_PER_CALL_USD,
    REQUIRED_POLICY_CAPS,
    GenerationProfile,
    LiveReasoningConfig,
    LiveReasoningConfigError,
    generation_profile,
)
from shared.sdk.agent_reasoning.models import (
    ARTIFACT_TYPE_FOR_VERB,
    PROVIDER_MODE_LIVE,
    ReasoningRequest,
    assert_artifact_within_size,
)
from shared.sdk.agent_reasoning.provider import (
    LiveProviderError,
    ProviderResult,
    ProviderUsage,
)

#: The instruction the model is given. Fixed per verb, owned by this repository, never supplied by a
#: caller and never persisted as business data -- it is code, and the shipped commit is its version.
_SYSTEM_INSTRUCTION = (
    "You are one participant in an autonomous software delivery team's structured reasoning step. "
    "Return ONE JSON object and nothing else: no prose before or after it, no Markdown code fence, "
    "no explanation. The object MUST match the provided JSON Schema exactly and MUST NOT contain "
    "any field the schema does not define. Never include chain-of-thought, scratchpad content, "
    "credentials, API keys or secrets in any field. State conclusions you would stand behind, not "
    "the process that produced them."
)

_VERB_TASK: dict[str, str] = {
    "propose": "Propose one option that advances the goal, with its rationale and what it leaves "
    "unresolved.",
    "critique": "Critique the standing proposal: state concerns and open questions, and recommend "
    "whether to proceed.",
    "summarize_decision": "Summarise what the team decided: the options considered, the option "
    "selected, and any dissent.",
    "decompose_plan": "Decompose the goal into a structured plan of discrete steps with explicit "
    "dependencies between step keys.",
}


def _http_failure_category(status_code: int) -> str:
    """Map a provider HTTP status onto the canonical taxonomy.

    Deliberately coarse. A vendor's status codes are implementation detail; what a caller needs from
    this mapping is exactly one bit -- is another attempt worth making -- and three categories carry
    it. 5xx is the server failing and is retryable; 4xx is the request being rejected
    deterministically and is not, so re-attempting it would spend money to fail identically.
    """
    if status_code == 429:
        return "rate_limited"
    if 500 <= status_code < 600:
        return "provider_unavailable"
    if 400 <= status_code < 500:
        return "provider_unauthorized"
    return "provider_unavailable"


class AnthropicReasoningProvider:
    """Live reasoning against Anthropic, for the one authorized model.

    ``name`` is the provider IDENTITY and ``mode`` is the provider CLASS. They are different facts:
    every reader of ``provider_mode`` asks "was this real", and only readers who care about the
    vendor read ``name``. Collapsing them into ``anthropic_live`` would force the first question to
    know the vendor list.
    """

    name = LIVE_PROVIDER_NAME
    mode = PROVIDER_MODE_LIVE

    def __init__(
        self,
        *,
        config: LiveReasoningConfig | None = None,
        secret_provider: Any | None = None,
        budget_evaluator: Any | None = None,
        budget_store: Any | None = None,
        transport: Any | None = None,
    ) -> None:
        self.config = config if config is not None else LiveReasoningConfig.resolve()
        self._secret_provider = secret_provider
        self._budget_evaluator = budget_evaluator
        self._budget_store = budget_store
        #: Test-injected in-process transport. Carries no URL, so injecting one cannot retarget the
        #: adapter at a different host -- the endpoint stays the fixed, runtime-owned constant.
        self._transport = transport

    @property
    def model_name(self) -> str:
        """The model that will actually answer. Configuration's answer, never the request's."""
        return self.config.model_name

    # --- lazily-built collaborators ------------------------------------------------------------

    def _secrets(self) -> Any:
        if self._secret_provider is None:
            from shared.sdk.secrets.provider import default_provider

            self._secret_provider = default_provider()
        return self._secret_provider

    def _budget(self) -> Any:
        if self._budget_evaluator is None:
            from shared.sdk.llm_budget.policy import BudgetPolicyEvaluator

            self._budget_evaluator = BudgetPolicyEvaluator()
        return self._budget_evaluator

    def _policies(self) -> Any:
        if self._budget_store is None:
            evaluator = self._budget()
            store = getattr(evaluator, "store", None)
            if store is None:
                from shared.sdk.llm_budget.store import BudgetPolicyStore

                store = BudgetPolicyStore()
            self._budget_store = store
        return self._budget_store

    # --- pre-flight ----------------------------------------------------------------------------

    async def preflight(self, request: ReasoningRequest) -> None:
        """Refuse, before any attempt is claimed, everything that can be refused for free.

        Called by ``ReasoningService`` before ``try_begin_invocation``. Raises
        :class:`LiveProviderError` carrying the canonical failure category; the service records that
        as a durable failed invocation rather than letting it escape, so a refusal is evidence
        rather than a stack trace -- the same shape the ``disabled`` provider has always had.
        """
        try:
            self.config.assert_callable()
        except LiveReasoningConfigError as exc:
            # The closed network gate is an operator POSTURE, not a rejected request: this runtime
            # has not been permitted to call anybody. That is what `provider_disabled` means.
            category = (
                "provider_disabled"
                if not self.config.live_network_enabled
                else "provider_unauthorized"
            )
            raise LiveProviderError(str(exc), failure_category=category) from exc

        try:
            profile = generation_profile(request.verb)
        except LiveReasoningConfigError as exc:
            raise LiveProviderError(str(exc), failure_category="provider_unauthorized") from exc

        try:
            approved_outbound_context(request.verb, request.context)
        except EgressViolationError as exc:
            raise LiveProviderError(str(exc), failure_category="provider_unauthorized") from exc

        await self._assert_budget_policy_authorized()
        # Referenced so a profile that cannot be built fails here rather than at the wire.
        assert profile.max_output_tokens > 0

    async def _assert_budget_policy_authorized(self) -> None:
        """An active policy carrying BOTH aggregate caps must exist before live mode may run.

        The existing evaluator already blocks when no policy exists at all. What it does not require
        is that the policy bound anything over time -- a policy with only a per-task cap bounds one
        call and not a thousand of them, and a first live slice must not be able to run all night
        inside a per-call limit.
        """
        policy = None
        try:
            policy = await self._policies().get_active_policy(provider=self.name)
        except Exception as exc:
            raise LiveProviderError(
                f"the live reasoning budget policy could not be read: {type(exc).__name__}",
                failure_category="budget_exceeded",
            ) from exc
        if policy is None:
            raise LiveProviderError(
                "no active LLM budget policy exists for live reasoning; a live provider call is "
                "not authorized without one",
                failure_category="budget_exceeded",
            )
        missing = [cap for cap in REQUIRED_POLICY_CAPS if getattr(policy, cap, None) is None]
        if missing:
            raise LiveProviderError(
                f"the active live reasoning budget policy does not set {sorted(missing)}; both an "
                "aggregate daily and an aggregate monthly cost cap are required",
                failure_category="budget_exceeded",
            )

    # --- the verbs -----------------------------------------------------------------------------

    async def propose(self, request: ReasoningRequest) -> ProviderResult:
        return await self._invoke("propose", request)

    async def critique(self, request: ReasoningRequest) -> ProviderResult:
        return await self._invoke("critique", request)

    async def summarize_decision(self, request: ReasoningRequest) -> ProviderResult:
        return await self._invoke("summarize_decision", request)

    async def decompose_plan(self, request: ReasoningRequest) -> ProviderResult:
        return await self._invoke("decompose_plan", request)

    # --- one attempt ---------------------------------------------------------------------------

    async def _invoke(self, verb: str, request: ReasoningRequest) -> ProviderResult:
        # Re-run the free checks. Not redundant: a verb can be called directly (a test does exactly
        # that), and "the caller promised to pre-flight" is not a guarantee the boundary can rely on.
        await self.preflight(request)

        profile = generation_profile(verb)
        projection = approved_outbound_context(verb, request.context)
        payload = self.build_request(verb, projection, profile)

        decision = await self._budget_preflight(verb, payload, profile)
        api_key = self._resolve_credential()

        usage, body = await self._call(payload, api_key)
        usage = ProviderUsage(
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            estimated_cost_usd=(
                float(decision.estimated_cost_usd) if decision is not None else None
            ),
            provider_request_id=usage.provider_request_id,
            model_name=self.model_name,
            call_occurred=True,
        )
        # Recorded BEFORE parsing. The call happened and is billable whatever the body turns out to
        # contain, and a parse failure a line later must not make the spend disappear from the
        # ledger.
        await self._record_usage(usage, decision)

        artifact = self._parse(verb, body, usage)
        return ProviderResult(artifact=artifact, usage=usage)

    # --- request -------------------------------------------------------------------------------

    def build_request(
        self, verb: str, projection: Mapping[str, Any], profile: GenerationProfile
    ) -> dict[str, Any]:
        """The exact outbound body. Deterministic, and built only from approved material.

        The response schema is derived from the canonical Pydantic artifact model rather than
        restated as prose, so the shape the model is asked for and the shape the parser enforces
        cannot drift apart.
        """
        artifact_type = ARTIFACT_TYPE_FOR_VERB[verb]
        schema = json.dumps(artifact_type.model_json_schema(), sort_keys=True, default=str)
        user_content = (
            f"TASK: {_VERB_TASK[verb]}\n\n"
            f"JSON_SCHEMA:\n{schema}\n\n"
            "CONTEXT:\n"
            f"{json.dumps(projection, sort_keys=True, ensure_ascii=False, default=str)}"
        )
        return {
            "model": self.model_name,
            "max_tokens": profile.max_output_tokens,
            "temperature": profile.temperature,
            "system": _SYSTEM_INSTRUCTION,
            "messages": [{"role": "user", "content": user_content}],
        }

    # --- budget --------------------------------------------------------------------------------

    async def _budget_preflight(
        self, verb: str, payload: Mapping[str, Any], profile: GenerationProfile
    ) -> Any:
        """Gate the spend before the wire. Conservative on both sides of the estimate."""
        from shared.sdk.llm_budget.estimator import estimate_tokens
        from shared.sdk.llm_budget.models import DECISION_ALLOWED

        outbound = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
        prompt_tokens = estimate_tokens(outbound)
        # Assume the model emits its entire allowance. It is the only completion count knowable
        # before the call, and assuming less would let a gate pass on an estimate the call can
        # legitimately exceed.
        completion_tokens = profile.max_output_tokens

        try:
            decision = await self._budget().preflight(
                provider=self.name,
                model_name=self.model_name,
                estimated_prompt_tokens=prompt_tokens,
                estimated_completion_tokens=completion_tokens,
                metadata={"reasoning_verb": verb, "provider_mode": self.mode},
            )
        except Exception as exc:
            raise LiveProviderError(
                f"the live reasoning budget pre-flight could not be evaluated: "
                f"{type(exc).__name__}",
                failure_category="budget_exceeded",
            ) from exc

        if decision.decision != DECISION_ALLOWED:
            raise LiveProviderError(
                f"budget pre-flight refused this call ({decision.decision}: "
                f"{decision.cap_breached or decision.reason})",
                failure_category="budget_exceeded",
            )
        estimated = float(decision.estimated_cost_usd or 0.0)
        if estimated > MAX_COST_PER_CALL_USD:
            # A second, independent ceiling. The operator's policy bounds the account; this bounds
            # any ONE call, so a generous monthly cap cannot be spent by a single request.
            raise LiveProviderError(
                f"the estimated cost of this call is ${estimated:.6f}, which exceeds the authorized "
                f"per-call maximum of ${MAX_COST_PER_CALL_USD:.2f}",
                failure_category="budget_exceeded",
            )
        return decision

    async def _record_usage(self, usage: ProviderUsage, decision: Any) -> None:
        """Write what the call actually consumed to the existing usage ledger.

        Best-effort by design. The money is already spent and the artifact may be perfectly valid;
        failing the reasoning call because a ledger insert failed would discard a paid result to
        record that it was paid for. The invocation row still carries the token counts, so a ledger
        failure degrades the accounting rather than erasing it.
        """
        if usage.input_tokens is None and usage.output_tokens is None:
            return
        try:
            await self._budget().record_usage(
                provider=self.name,
                model_name=self.model_name,
                prompt_tokens=int(usage.input_tokens or 0),
                completion_tokens=int(usage.output_tokens or 0),
                policy_id=getattr(decision, "policy_id", None),
                metadata={"provider_request_id": usage.provider_request_id},
            )
        except Exception:
            return

    # --- credential ----------------------------------------------------------------------------

    def _resolve_credential(self) -> str:
        """Resolve the API key, last, and only for a call that is otherwise fully authorized.

        The value is returned as a bare string because a header needs one; it is used once, in the
        request that follows, and is never stored on the adapter, returned to a caller, logged, or
        interpolated into an exception message.
        """
        ref = self._secrets().get_secret(ANTHROPIC_SECRET_NAME)
        if not ref:
            raise LiveProviderError(
                f"the live reasoning credential {ANTHROPIC_SECRET_NAME} is not available from the "
                "configured secret provider",
                failure_category="provider_unauthorized",
            )
        return ref.reveal()

    # --- wire ----------------------------------------------------------------------------------

    async def _call(self, payload: Mapping[str, Any], api_key: str) -> tuple[ProviderUsage, Any]:
        """One request. No retries at any layer, and a genuine wall-clock bound on the attempt."""
        import httpx

        timeout = httpx.Timeout(ATTEMPT_TIMEOUT_SECONDS, connect=CONNECT_TIMEOUT_SECONDS)
        # retries=0 is load-bearing. ReasoningService's attempt/takeover machinery is the ONE
        # authoritative retry layer; a transport that quietly retries under a 3-attempt budget
        # multiplies worst-case spend by a factor nothing in this architecture accounts for.
        transport = (
            self._transport if self._transport is not None else httpx.AsyncHTTPTransport(retries=0)
        )
        headers = {
            "x-api-key": api_key,
            "anthropic-version": ANTHROPIC_API_VERSION,
            "content-type": "application/json",
        }
        url = f"{ANTHROPIC_API_BASE}{ANTHROPIC_MESSAGES_PATH}"

        try:
            async with httpx.AsyncClient(timeout=timeout, transport=transport) as client:
                # An httpx timeout bounds one socket operation; this bounds the ATTEMPT, which is
                # the quantity that has to stay inside the database lease.
                response = await asyncio.wait_for(
                    client.post(url, headers=headers, json=dict(payload)),
                    timeout=ATTEMPT_TIMEOUT_SECONDS,
                )
        except (asyncio.TimeoutError, httpx.TimeoutException) as exc:
            raise LiveProviderError(
                f"the live reasoning provider did not respond within "
                f"{ATTEMPT_TIMEOUT_SECONDS:.0f}s ({type(exc).__name__})",
                failure_category="provider_timeout",
                usage=ProviderUsage(model_name=self.model_name, call_occurred=True),
            ) from exc
        except httpx.HTTPError as exc:
            # Only the exception CLASS is repeated. A transport exception's message can carry
            # whatever the far side put there, including echoed request content.
            raise LiveProviderError(
                f"the live reasoning provider could not be reached ({type(exc).__name__})",
                failure_category="provider_unavailable",
                usage=ProviderUsage(model_name=self.model_name, call_occurred=True),
            ) from exc

        return self._read_response(response)

    def _read_response(self, response: Any) -> tuple[ProviderUsage, Any]:
        """Turn an HTTP response into usage plus a decoded body, or a categorized failure.

        The provider's own error body is never echoed. Only the status code -- a bounded integer
        the provider cannot use to smuggle anything -- reaches the failure reason.
        """
        status = int(response.status_code)
        try:
            body = response.json()
        except Exception:
            body = None

        usage = self._usage_from(body)
        if status < 200 or status >= 300:
            raise LiveProviderError(
                f"the live reasoning provider returned HTTP {status}",
                failure_category=_http_failure_category(status),
                usage=usage,
            )
        if not isinstance(body, dict):
            raise LiveProviderError(
                "the live reasoning provider returned a body that is not a JSON object",
                failure_category="malformed_output",
                usage=usage,
            )
        return usage, body

    def _usage_from(self, body: Any) -> ProviderUsage:
        """Token counts and request id, defensively. A usage block is untrusted like everything else."""
        input_tokens: int | None = None
        output_tokens: int | None = None
        request_id: str | None = None
        if isinstance(body, dict):
            raw_usage = body.get("usage")
            if isinstance(raw_usage, dict):
                input_tokens = _int_or_none(raw_usage.get("input_tokens"))
                output_tokens = _int_or_none(raw_usage.get("output_tokens"))
            raw_id = body.get("id")
            if isinstance(raw_id, str) and raw_id:
                # Bounded, and it is an opaque message identifier -- not a credential.
                request_id = raw_id[:120]
        return ProviderUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            provider_request_id=request_id,
            model_name=self.model_name,
            call_occurred=True,
        )

    # --- parsing -------------------------------------------------------------------------------

    def _parse(self, verb: str, body: Mapping[str, Any], usage: ProviderUsage) -> Any:
        """Strict. Every rejection here is terminal and none of them repairs anything.

        No Markdown fence is stripped, no JSON block is regex-extracted, no partial object is
        accepted and no unknown field is dropped: each of those is a way of accepting output the
        model was told not to produce, and each would let a malformed completion become a durable
        team artifact.
        """
        artifact_type = ARTIFACT_TYPE_FOR_VERB[verb]

        blocks = body.get("content")
        if not isinstance(blocks, list):
            raise LiveProviderError(
                "the live reasoning response carried no content blocks",
                failure_category="malformed_output",
                usage=usage,
            )
        text = "".join(
            block.get("text", "")
            for block in blocks
            if isinstance(block, dict) and block.get("type") == "text"
        )
        if not text.strip():
            raise LiveProviderError(
                "the live reasoning response carried no text content",
                failure_category="malformed_output",
                usage=usage,
            )

        try:
            decoded = json.loads(text)
        except Exception as exc:
            raise LiveProviderError(
                f"the live reasoning response is not valid JSON ({type(exc).__name__})",
                failure_category="malformed_output",
                usage=usage,
            ) from exc
        if not isinstance(decoded, dict):
            raise LiveProviderError(
                "the live reasoning response decoded to a JSON value that is not an object",
                failure_category="malformed_output",
                usage=usage,
            )

        try:
            artifact = artifact_type.model_validate(decoded)
        except Exception as exc:
            # Covers a missing field, a wrong type, an extra field rejected by extra="forbid", and
            # every PlanContent bound -- step count, dependency count, capability count, output
            # count, constraint count, duplicate keys, unknown or self dependency.
            raise LiveProviderError(
                f"the live reasoning response does not satisfy {artifact_type.__name__} "
                f"({type(exc).__name__})",
                failure_category="malformed_output",
                usage=usage,
            ) from exc

        try:
            payload = artifact.as_safe_dict()
        except ValueError as exc:
            raise LiveProviderError(
                f"the live reasoning artifact was rejected by the content screen ({exc})",
                failure_category="content_safety_rejected",
                usage=usage,
            ) from exc

        try:
            assert_artifact_within_size(payload)
        except ValueError as exc:
            # The backstop for a provider that ignored max_tokens. Rejected here, before anything
            # durable exists, so no oversized artifact can reach a SUCCEEDED row.
            raise LiveProviderError(
                str(exc), failure_category="malformed_output", usage=usage
            ) from exc

        return artifact


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


__all__ = ["AnthropicReasoningProvider"]
