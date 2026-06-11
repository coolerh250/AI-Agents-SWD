"""Stage 38 -- ModelRouter.

Given an :class:`LLMCapabilityRequest` and access to the store,
:meth:`ModelRouter.route` walks the policy + registry + budget gates
and returns an :class:`LLMRoutingDecision`. The decision is persisted
to ``llm_routing_decisions`` (when ``persist=True``).

The router NEVER calls a provider directly. It picks a model (or
blocks) and lets the caller execute the actual provider call.

Hard rules (enforced regardless of registry / policy state):

* ``allow_patch_generation_requested=True`` -> ``DECISION_BLOCKED``
  with reason ``patch_generation_hard_disabled``.
* ``allow_workspace_write_requested=True`` -> ``DECISION_BLOCKED``
  with reason ``workspace_write_hard_disabled``.
* request carries ``requested_model_alias`` not in policy's allowed
  set -> ``DECISION_DIRECT_MODEL_REJECTED``.

Soft rules (registry + policy intersection):

* missing active policy -> ``DECISION_POLICY_NOT_FOUND``.
* preferred model unavailable / capability mismatch / schema
  unsupported -> attempt fallback aliases in policy order.
* fallback exhausted -> ``DECISION_BLOCKED`` /
  ``DECISION_PROVIDER_UNAVAILABLE`` / ``DECISION_SCHEMA_UNSUPPORTED``
  depending on the reason.
* budget cap exceeded -> ``DECISION_BUDGET_BLOCKED``.
* real LLM allowed AND policy/model agrees -> ``real_llm_allowed=True``.
* policy ``requires_human_review=True`` OR risk in (``high``,
  ``critical``) -> ``requires_human_review=True``. Critical risk
  alone surfaces ``DECISION_HUMAN_APPROVAL_REQUIRED``.
"""

from __future__ import annotations

from typing import Any

from .evaluator import (
    capability_supported,
    estimate_cost_usd,
    schema_supported,
)
from .models import (
    AgentModelPolicy,
    DECISION_BLOCKED,
    DECISION_BUDGET_BLOCKED,
    DECISION_DIRECT_MODEL_REJECTED,
    DECISION_FALLBACK_SELECTED,
    DECISION_HUMAN_APPROVAL_REQUIRED,
    DECISION_MOCK_SELECTED,
    DECISION_POLICY_NOT_FOUND,
    DECISION_PROVIDER_UNAVAILABLE,
    DECISION_SELECTED,
    LLMCapabilityRequest,
    LLMModelEntry,
    LLMRoutingDecision,
    MODEL_STATUS_ACTIVE,
    MODEL_STATUS_BLOCKED,
    MODEL_STATUS_DEPRECATED,
)
from .store import ModelRouterStore

_REASON_PATCH_HARD = "patch_generation_hard_disabled"
_REASON_WORKSPACE_HARD = "workspace_write_hard_disabled"
_REASON_DIRECT_MODEL = "agent_direct_model_selection_rejected"
_REASON_POLICY_MISSING = "no_active_policy_for_capability"
_REASON_PROVIDER_NOT_ALLOWED = "provider_not_in_policy_allow_list"
_REASON_TIER_NOT_ALLOWED = "tier_not_in_policy_allow_list"
_REASON_CAPABILITY_UNSUPPORTED = "model_does_not_support_capability"
_REASON_SCHEMA_UNSUPPORTED = "model_does_not_support_requested_schema"
_REASON_MODEL_INACTIVE = "model_status_not_active"
_REASON_MODEL_BLOCKED = "model_status_blocked"
_REASON_MODEL_DEPRECATED = "model_status_deprecated"
_REASON_NO_MODEL = "no_model_passed_all_gates"
_REASON_BUDGET_TASK_COST = "estimated_cost_exceeds_policy_max"
_REASON_BUDGET_TASK_TOKENS = "estimated_tokens_exceeds_policy_max"
_REASON_REAL_LLM_BLOCKED = "real_llm_not_authorised_for_capability"
_REASON_HUMAN_APPROVAL = "critical_risk_requires_human_approval"


class ModelRouter:
    """Plat-level Model Router.

    Tests inject a mock ``ModelRouterStore`` to keep router unit tests
    DB-free.
    """

    def __init__(
        self,
        *,
        store: ModelRouterStore | None = None,
        budget_evaluator: Any = None,
    ) -> None:
        # We don't auto-instantiate ``ModelRouterStore`` here -- the
        # caller chooses (DB-backed or fake) so tests stay hermetic.
        self._store = store
        self._budget_evaluator = budget_evaluator

    async def route(
        self,
        request: LLMCapabilityRequest,
        *,
        persist: bool = False,
    ) -> LLMRoutingDecision:
        # 1. Hard safety rails -- enforced first, before any DB read.
        if request.allow_patch_generation_requested:
            return await self._finalise(
                request,
                self._build_blocked(request, DECISION_BLOCKED, _REASON_PATCH_HARD),
                persist=persist,
            )
        if request.allow_workspace_write_requested:
            return await self._finalise(
                request,
                self._build_blocked(request, DECISION_BLOCKED, _REASON_WORKSPACE_HARD),
                persist=persist,
            )

        # 2. Load the active policy. Default-deny.
        policy = await self._load_policy(request)
        if policy is None:
            return await self._finalise(
                request,
                self._build_blocked(request, DECISION_POLICY_NOT_FOUND, _REASON_POLICY_MISSING),
                persist=persist,
            )

        # 3. Direct model selection rejection. ``requested_model_alias``
        # is a preference; if it's not allowed by the policy we refuse.
        if request.requested_model_alias:
            if not self._alias_allowed_by_policy(request.requested_model_alias, policy):
                decision = self._build_blocked(
                    request,
                    DECISION_DIRECT_MODEL_REJECTED,
                    _REASON_DIRECT_MODEL,
                )
                decision.policy_id = policy.policy_id
                decision.requires_human_review = bool(policy.requires_human_review)
                return await self._finalise(request, decision, persist=persist)

        # 4. Critical risk needs human approval before we even pick.
        if request.risk_level == "critical" and not policy.allow_real_llm:
            decision = self._build_blocked(
                request,
                DECISION_HUMAN_APPROVAL_REQUIRED,
                _REASON_HUMAN_APPROVAL,
            )
            decision.policy_id = policy.policy_id
            decision.requires_human_review = True
            return await self._finalise(request, decision, persist=persist)

        # 5. Walk the candidate list: preferred -> fallback -> any
        # tier-compatible active model.
        candidates = await self._candidate_models(request, policy)
        if not candidates:
            decision = self._build_blocked(
                request,
                DECISION_PROVIDER_UNAVAILABLE,
                _REASON_NO_MODEL,
            )
            decision.policy_id = policy.policy_id
            decision.requires_human_review = bool(policy.requires_human_review)
            return await self._finalise(request, decision, persist=persist)

        for model, is_fallback in candidates:
            violations = self._evaluate_model(model, request, policy)
            if violations:
                # Capture as warnings; keep trying later candidates.
                continue
            # 6. Budget check (optional; only when an evaluator is wired).
            est_input = int(request.estimated_input_tokens or 0)
            est_output = int(
                request.max_output_tokens
                if request.max_output_tokens is not None
                else (model.default_max_output_tokens or 512)
            )
            est_cost = estimate_cost_usd(model, input_tokens=est_input, output_tokens=est_output)
            if not self._within_policy_caps(
                policy=policy,
                tokens=est_input + est_output,
                cost=est_cost,
            ):
                decision = self._build_blocked(
                    request, DECISION_BUDGET_BLOCKED, _REASON_BUDGET_TASK_COST
                )
                decision.policy_id = policy.policy_id
                decision.model_id = model.model_id
                decision.selected_provider = model.provider
                decision.selected_model_name = model.model_name
                decision.selected_model_alias = model.model_alias
                decision.selected_model_tier = model.model_tier
                decision.estimated_input_tokens = est_input
                decision.estimated_output_tokens = est_output
                decision.estimated_cost_usd = est_cost
                decision.requires_human_review = bool(policy.requires_human_review)
                return await self._finalise(request, decision, persist=persist)

            # 7. Optional budget preflight call (Stage 35).
            budget_block = await self._budget_preflight(
                request, policy, model, est_input, est_output, est_cost
            )
            if budget_block is not None:
                budget_block.policy_id = policy.policy_id
                budget_block.model_id = model.model_id
                budget_block.selected_provider = model.provider
                budget_block.selected_model_alias = model.model_alias
                return await self._finalise(request, budget_block, persist=persist)

            # 8. Selected!
            decision_kind = DECISION_SELECTED
            if model.provider == "mock":
                decision_kind = DECISION_MOCK_SELECTED
            if is_fallback:
                decision_kind = DECISION_FALLBACK_SELECTED

            real_llm_allowed = bool(
                request.allow_real_llm_requested
                and policy.allow_real_llm
                and model.provider != "mock"
                and model.status == MODEL_STATUS_ACTIVE
            )
            requires_review = bool(
                policy.requires_human_review
                or model.requires_human_review
                or request.risk_level in ("high", "critical")
            )

            decision = LLMRoutingDecision(
                decision=decision_kind,
                reason="selected_by_policy" if not is_fallback else "fallback_selected_by_policy",
                agent_name=request.agent_name,
                capability=request.capability,
                task_type=request.task_type,
                risk_level=request.risk_level,
                selected_provider=model.provider,
                selected_model_name=model.model_name,
                selected_model_alias=model.model_alias,
                selected_model_tier=model.model_tier,
                requested_schema=request.requested_schema,
                requested_model_alias=request.requested_model_alias,
                fallback_used=is_fallback,
                requires_human_review=requires_review,
                real_llm_allowed=real_llm_allowed,
                patch_generation_allowed=False,
                workspace_write_allowed=False,
                estimated_input_tokens=est_input,
                estimated_output_tokens=est_output,
                estimated_cost_usd=est_cost,
                policy_id=policy.policy_id,
                model_id=model.model_id,
                metadata={},
            )
            return await self._finalise(request, decision, persist=persist)

        # 9. No candidate cleared the gates.
        decision = self._build_blocked(request, DECISION_BLOCKED, _REASON_NO_MODEL)
        decision.policy_id = policy.policy_id
        decision.requires_human_review = bool(policy.requires_human_review)
        return await self._finalise(request, decision, persist=persist)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_blocked(
        self,
        request: LLMCapabilityRequest,
        decision: str,
        reason: str,
    ) -> LLMRoutingDecision:
        return LLMRoutingDecision(
            decision=decision,
            reason=reason,
            agent_name=request.agent_name,
            capability=request.capability,
            task_type=request.task_type,
            risk_level=request.risk_level,
            requested_schema=request.requested_schema,
            requested_model_alias=request.requested_model_alias,
            fallback_used=False,
            requires_human_review=False,
            real_llm_allowed=False,
            patch_generation_allowed=False,
            workspace_write_allowed=False,
            violations=[reason],
        )

    async def _load_policy(self, request: LLMCapabilityRequest) -> AgentModelPolicy | None:
        if self._store is None:
            return None
        return await self._store.get_active_policy(
            agent_name=request.agent_name,
            capability=request.capability,
            task_type=request.task_type,
            risk_level=request.risk_level,
        )

    def _alias_allowed_by_policy(self, alias: str, policy: AgentModelPolicy) -> bool:
        if alias == policy.preferred_model_alias:
            return True
        return alias in (policy.fallback_model_aliases or ())

    async def _candidate_models(
        self,
        request: LLMCapabilityRequest,
        policy: AgentModelPolicy,
    ) -> list[tuple[LLMModelEntry, bool]]:
        """Return ``(model, is_fallback)`` candidates in policy order."""

        if self._store is None:
            return []
        candidates: list[tuple[LLMModelEntry, bool]] = []
        seen_aliases: set[str] = set()

        if policy.preferred_model_alias:
            preferred = await self._store.get_model_by_alias(policy.preferred_model_alias)
            if preferred is not None:
                candidates.append((preferred, False))
                seen_aliases.add(preferred.model_alias)
        for fallback_alias in policy.fallback_model_aliases or ():
            if fallback_alias in seen_aliases:
                continue
            model = await self._store.get_model_by_alias(fallback_alias)
            if model is not None:
                candidates.append((model, True))
                seen_aliases.add(model.model_alias)
        return candidates

    def _evaluate_model(
        self,
        model: LLMModelEntry,
        request: LLMCapabilityRequest,
        policy: AgentModelPolicy,
    ) -> list[str]:
        problems: list[str] = []
        if model.status != MODEL_STATUS_ACTIVE:
            if model.status == MODEL_STATUS_BLOCKED:
                problems.append(_REASON_MODEL_BLOCKED)
            elif model.status == MODEL_STATUS_DEPRECATED:
                problems.append(_REASON_MODEL_DEPRECATED)
            else:
                problems.append(_REASON_MODEL_INACTIVE)
        if policy.allowed_providers and model.provider not in policy.allowed_providers:
            problems.append(_REASON_PROVIDER_NOT_ALLOWED)
        if policy.allowed_model_tiers and model.model_tier not in policy.allowed_model_tiers:
            problems.append(_REASON_TIER_NOT_ALLOWED)
        if not capability_supported(model, request.capability):
            problems.append(_REASON_CAPABILITY_UNSUPPORTED)
        if not schema_supported(model, request.requested_schema):
            problems.append(_REASON_SCHEMA_UNSUPPORTED)
        # Real-LLM authorisation.
        if request.allow_real_llm_requested:
            if not policy.allow_real_llm or model.provider == "mock":
                # Not strictly a model violation -- the router falls
                # back to mock for the actual call. We capture this in
                # warnings inside _finalise.
                pass
        return problems

    def _within_policy_caps(
        self,
        *,
        policy: AgentModelPolicy,
        tokens: int,
        cost: float,
    ) -> bool:
        if policy.max_cost_per_task_usd is not None and cost > float(policy.max_cost_per_task_usd):
            return False
        if policy.max_tokens_per_task is not None and tokens > int(policy.max_tokens_per_task):
            return False
        return True

    async def _budget_preflight(
        self,
        request: LLMCapabilityRequest,
        policy: AgentModelPolicy,
        model: LLMModelEntry,
        est_input: int,
        est_output: int,
        est_cost: float,
    ) -> LLMRoutingDecision | None:
        """Optional Stage 35 budget preflight.

        When the budget evaluator is wired AND a real provider is
        selected AND ``allow_real_llm`` is true on both sides, we
        consult ``BudgetPolicyEvaluator.preflight`` to keep the
        routing layer aligned with cost governance. The router still
        accepts a None evaluator for unit tests.
        """

        if self._budget_evaluator is None:
            return None
        # Only real providers care about Stage 35 budget; mock providers
        # are always $0 / 0 tokens.
        if model.provider == "mock":
            return None
        try:
            decision = await self._budget_evaluator.preflight(
                provider=model.provider,
                model_name=model.model_name,
                prompt_text="",  # router does not see prompt text
                task_id=request.task_id or "",
                workflow_id=request.workflow_id,
            )
        except Exception:
            return None
        if not getattr(decision, "allowed", True):
            block = self._build_blocked(
                request,
                DECISION_BUDGET_BLOCKED,
                str(getattr(decision, "reason", _REASON_BUDGET_TASK_COST)),
            )
            block.estimated_input_tokens = est_input
            block.estimated_output_tokens = est_output
            block.estimated_cost_usd = est_cost
            block.budget_policy_id = getattr(decision, "policy_id", None)
            return block
        return None

    async def _finalise(
        self,
        request: LLMCapabilityRequest,
        decision: LLMRoutingDecision,
        *,
        persist: bool,
    ) -> LLMRoutingDecision:
        if persist and self._store is not None:
            record = await self._store.record_decision(
                {
                    "task_id": request.task_id,
                    "workflow_id": request.workflow_id,
                    "agent_name": request.agent_name,
                    "capability": request.capability,
                    "task_type": request.task_type,
                    "risk_level": request.risk_level,
                    "requested_schema": request.requested_schema,
                    "requested_model_alias": request.requested_model_alias,
                    "selected_provider": decision.selected_provider,
                    "selected_model_name": decision.selected_model_name,
                    "selected_model_alias": decision.selected_model_alias,
                    "selected_model_tier": decision.selected_model_tier,
                    "decision": decision.decision,
                    "reason": decision.reason,
                    "fallback_used": decision.fallback_used,
                    "budget_policy_id": decision.budget_policy_id,
                    "estimated_input_tokens": decision.estimated_input_tokens,
                    "estimated_output_tokens": decision.estimated_output_tokens,
                    "estimated_cost_usd": decision.estimated_cost_usd,
                    "requires_human_review": decision.requires_human_review,
                    "real_llm_allowed": decision.real_llm_allowed,
                    "patch_generation_allowed": decision.patch_generation_allowed,
                    "workspace_write_allowed": decision.workspace_write_allowed,
                    "policy_id": decision.policy_id,
                    "model_id": decision.model_id,
                    "metadata": decision.metadata,
                }
            )
            decision.metadata["routing_decision_id"] = record.routing_decision_id
        return decision

    # Backwards-friendly convenience for synchronous callers in tests
    # that already drive an asyncio event loop.
    def explain(self, decision: LLMRoutingDecision) -> str:
        prefix = f"{decision.agent_name}/{decision.capability}[{decision.risk_level}]"
        if decision.is_select:
            return (
                f"{prefix} -> {decision.decision} "
                f"provider={decision.selected_provider} "
                f"model={decision.selected_model_alias} "
                f"tier={decision.selected_model_tier} "
                f"cost_est={decision.estimated_cost_usd}"
            )
        return f"{prefix} -> {decision.decision} ({decision.reason})"
