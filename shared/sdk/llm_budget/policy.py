"""Budget policy evaluator.

Two public entry points:

* :meth:`BudgetPolicyEvaluator.preflight` -- gates a real-LLM call
  BEFORE the wire request. Returns a :class:`BudgetDecision`
  describing the outcome and inserts one ``llm_budget_events`` row
  with ``event_type=preflight``.
* :meth:`BudgetPolicyEvaluator.record_usage` -- recorded after the
  real call lands. Inserts a ``recorded_usage`` event and, if the
  cumulative usage tipped any cap, follows up with a
  ``budget_exceeded`` event so operators see the breach without
  scanning the ledger.

Mock provider is exempt from cap checks (cost is always $0). The
``preflight`` for a real provider with no active policy returns
``decision=blocked`` with ``reason=no_active_budget_policy`` -- a
real LLM cannot run without an explicit budget.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .estimator import LLMCostEstimator
from .models import (
    DECISION_ALLOWED,
    DECISION_BLOCKED,
    DECISION_RECORDED,
    DECISION_WARNING,
    ENFORCEMENT_BLOCK,
    EVENT_TYPE_BUDGET_EXCEEDED,
    EVENT_TYPE_BUDGET_WARNING,
    EVENT_TYPE_PREFLIGHT,
    EVENT_TYPE_RECORDED_USAGE,
    BudgetDecision,
    LLMBudgetPolicy,
)
from .store import BudgetPolicyStore


@dataclass
class _CapResult:
    cap: str | None
    reason: str | None
    budget_remaining_usd: float | None


class BudgetPolicyEvaluator:
    """Run policy + record events. Mock provider is exempt."""

    def __init__(
        self,
        *,
        store: BudgetPolicyStore | None = None,
        estimator: LLMCostEstimator | None = None,
    ) -> None:
        self.store = store or BudgetPolicyStore()
        self.estimator = estimator or LLMCostEstimator()

    async def preflight(
        self,
        *,
        provider: str,
        model_name: str,
        prompt_text: str | None = None,
        estimated_prompt_tokens: int | None = None,
        estimated_completion_tokens: int | None = None,
        task_id: str | None = None,
        workflow_id: str | None = None,
        user_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> BudgetDecision:
        """Gate a real-LLM call.

        Estimation rules:

        * If the caller provides token counts, use them as-is.
        * Else estimate prompt tokens from ``prompt_text`` and assume
          completion tokens = 50% of prompt tokens (rounded up,
          minimum 32) so the budget gate has a non-zero estimate
          even for a very short prompt.
        """
        # Cost / token estimation.
        from .estimator import estimate_tokens

        if estimated_prompt_tokens is None:
            estimated_prompt_tokens = estimate_tokens(prompt_text)
        if estimated_completion_tokens is None:
            estimated_completion_tokens = max(32, (estimated_prompt_tokens + 1) // 2)

        try:
            cost_info = self.estimator.estimate_cost(
                provider=provider,
                model_name=model_name,
                prompt_tokens=estimated_prompt_tokens,
                completion_tokens=estimated_completion_tokens,
            )
        except ValueError as exc:
            # Unknown provider -> block + record.
            decision = BudgetDecision(
                decision=DECISION_BLOCKED,
                reason=str(exc),
                enforcement_mode=ENFORCEMENT_BLOCK,
                policy_id=None,
                policy_name=None,
                provider=provider,
                model_name=model_name,
                estimated_prompt_tokens=int(estimated_prompt_tokens),
                estimated_completion_tokens=int(estimated_completion_tokens),
                estimated_total_tokens=int(estimated_prompt_tokens + estimated_completion_tokens),
                estimated_cost_usd=0.0,
                budget_remaining_usd=None,
                cap_breached="unknown_provider",
                metadata=dict(metadata or {}),
            )
            await self._persist(decision, task_id, workflow_id)
            return decision

        estimated_cost = float(cost_info["cost_usd"])
        total_tokens = int(cost_info["total_tokens"])
        fallback_used = bool(cost_info.get("fallback_used"))

        # Mock provider -> always allowed, $0 cost.
        if provider == "mock":
            decision = BudgetDecision(
                decision=DECISION_ALLOWED,
                reason="mock_provider_exempt",
                enforcement_mode=ENFORCEMENT_BLOCK,
                policy_id=None,
                policy_name=None,
                provider=provider,
                model_name=cost_info["model_name"],
                estimated_prompt_tokens=int(estimated_prompt_tokens),
                estimated_completion_tokens=int(estimated_completion_tokens),
                estimated_total_tokens=total_tokens,
                estimated_cost_usd=estimated_cost,
                budget_remaining_usd=None,
                metadata={"mock_provider": True},
            )
            await self._persist(decision, task_id, workflow_id)
            return decision

        # Active policy lookup.
        policy = await self.store.get_active_policy(
            provider=provider,
            task_id=task_id,
            workflow_id=workflow_id,
            user_id=user_id,
        )
        if policy is None:
            decision = BudgetDecision(
                decision=DECISION_BLOCKED,
                reason="no_active_budget_policy",
                enforcement_mode=ENFORCEMENT_BLOCK,
                policy_id=None,
                policy_name=None,
                provider=provider,
                model_name=cost_info["model_name"],
                estimated_prompt_tokens=int(estimated_prompt_tokens),
                estimated_completion_tokens=int(estimated_completion_tokens),
                estimated_total_tokens=total_tokens,
                estimated_cost_usd=estimated_cost,
                budget_remaining_usd=None,
                cap_breached="no_policy",
                metadata={"fallback_model_used": fallback_used},
            )
            await self._persist(decision, task_id, workflow_id)
            return decision

        cap = await self._check_caps(
            policy=policy,
            task_id=task_id,
            estimated_total_tokens=total_tokens,
            estimated_cost_usd=estimated_cost,
        )
        if cap.cap is not None:
            # Cap breached.
            decision_label = (
                DECISION_BLOCKED
                if policy.enforcement_mode == ENFORCEMENT_BLOCK
                else DECISION_WARNING
            )
            decision = BudgetDecision(
                decision=decision_label,
                reason=cap.reason,
                enforcement_mode=policy.enforcement_mode,
                policy_id=policy.policy_id,
                policy_name=policy.policy_name,
                provider=provider,
                model_name=cost_info["model_name"],
                estimated_prompt_tokens=int(estimated_prompt_tokens),
                estimated_completion_tokens=int(estimated_completion_tokens),
                estimated_total_tokens=total_tokens,
                estimated_cost_usd=estimated_cost,
                budget_remaining_usd=cap.budget_remaining_usd,
                cap_breached=cap.cap,
                metadata={"fallback_model_used": fallback_used},
            )
            await self._persist(decision, task_id, workflow_id)
            return decision

        # Allowed.
        decision = BudgetDecision(
            decision=DECISION_ALLOWED,
            reason=None,
            enforcement_mode=policy.enforcement_mode,
            policy_id=policy.policy_id,
            policy_name=policy.policy_name,
            provider=provider,
            model_name=cost_info["model_name"],
            estimated_prompt_tokens=int(estimated_prompt_tokens),
            estimated_completion_tokens=int(estimated_completion_tokens),
            estimated_total_tokens=total_tokens,
            estimated_cost_usd=estimated_cost,
            budget_remaining_usd=cap.budget_remaining_usd,
            metadata={"fallback_model_used": fallback_used},
        )
        await self._persist(decision, task_id, workflow_id)
        return decision

    async def record_usage(
        self,
        *,
        provider: str,
        model_name: str,
        prompt_tokens: int,
        completion_tokens: int,
        task_id: str | None = None,
        workflow_id: str | None = None,
        policy_id: str | None = None,
        actual_cost_usd: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Record actual usage AFTER the LLM call lands.

        If ``actual_cost_usd`` is None, the cost is recomputed from the
        estimator's pricing table so the ledger always has a value.
        Mock provider is always $0.
        """
        if provider == "mock":
            total = int(prompt_tokens) + int(completion_tokens)
            await self.store.record_budget_event(
                task_id=task_id,
                workflow_id=workflow_id,
                policy_id=policy_id,
                provider=provider,
                model_name=model_name,
                event_type=EVENT_TYPE_RECORDED_USAGE,
                decision=DECISION_RECORDED,
                estimated_prompt_tokens=int(prompt_tokens),
                estimated_completion_tokens=int(completion_tokens),
                estimated_total_tokens=total,
                actual_prompt_tokens=int(prompt_tokens),
                actual_completion_tokens=int(completion_tokens),
                actual_total_tokens=total,
                estimated_cost_usd=0.0,
                actual_cost_usd=0.0,
                budget_remaining_usd=None,
                reason=None,
                metadata=dict(metadata or {}),
            )
            return {"recorded": True, "actual_cost_usd": 0.0, "exceeded": False}

        if actual_cost_usd is None:
            try:
                cost_info = self.estimator.estimate_cost(
                    provider=provider,
                    model_name=model_name,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                )
                actual_cost_usd = float(cost_info["cost_usd"])
            except ValueError:
                actual_cost_usd = 0.0

        total_tokens = int(prompt_tokens) + int(completion_tokens)
        await self.store.record_budget_event(
            task_id=task_id,
            workflow_id=workflow_id,
            policy_id=policy_id,
            provider=provider,
            model_name=model_name,
            event_type=EVENT_TYPE_RECORDED_USAGE,
            decision=DECISION_RECORDED,
            estimated_prompt_tokens=int(prompt_tokens),
            estimated_completion_tokens=int(completion_tokens),
            estimated_total_tokens=total_tokens,
            actual_prompt_tokens=int(prompt_tokens),
            actual_completion_tokens=int(completion_tokens),
            actual_total_tokens=total_tokens,
            estimated_cost_usd=float(actual_cost_usd),
            actual_cost_usd=float(actual_cost_usd),
            budget_remaining_usd=None,
            reason=None,
            metadata=dict(metadata or {}),
        )

        # Post-record breach check: if a cap is now exceeded, emit one
        # budget_exceeded event so operators see it without scanning.
        exceeded = False
        if task_id and policy_id:
            policy = await self.store.get_active_policy(provider=provider, task_id=task_id)
            if policy:
                cap = await self._check_caps(
                    policy=policy,
                    task_id=task_id,
                    estimated_total_tokens=0,
                    estimated_cost_usd=0.0,
                )
                if cap.cap is not None:
                    exceeded = True
                    await self.store.record_budget_event(
                        task_id=task_id,
                        workflow_id=workflow_id,
                        policy_id=policy_id,
                        provider=provider,
                        model_name=model_name,
                        event_type=EVENT_TYPE_BUDGET_EXCEEDED,
                        decision=DECISION_BLOCKED,
                        estimated_cost_usd=0.0,
                        reason=cap.reason,
                        metadata={"cap_breached": cap.cap},
                    )

        return {
            "recorded": True,
            "actual_cost_usd": float(actual_cost_usd),
            "exceeded": exceeded,
        }

    async def _check_caps(
        self,
        *,
        policy: LLMBudgetPolicy,
        task_id: str | None,
        estimated_total_tokens: int,
        estimated_cost_usd: float,
    ) -> _CapResult:
        # Per-task token cap.
        if policy.max_tokens_per_task is not None and policy.max_tokens_per_task > 0:
            used_tokens = 0
            if task_id:
                used = await self.store.get_task_usage(task_id=task_id)
                used_tokens = int(used.get("tokens") or 0)
            if used_tokens + estimated_total_tokens > policy.max_tokens_per_task:
                return _CapResult(
                    cap="token_per_task",
                    reason=(
                        "token_per_task_cap_exceeded "
                        f"(used={used_tokens} estimated={estimated_total_tokens} "
                        f"cap={policy.max_tokens_per_task})"
                    ),
                    budget_remaining_usd=None,
                )

        # Per-task cost cap.
        if policy.max_cost_per_task_usd is not None and policy.max_cost_per_task_usd > 0:
            used_cost = 0.0
            if task_id:
                used = await self.store.get_task_usage(task_id=task_id)
                used_cost = float(used.get("cost_usd") or 0.0)
            if used_cost + estimated_cost_usd > policy.max_cost_per_task_usd:
                return _CapResult(
                    cap="cost_per_task",
                    reason=(
                        "cost_per_task_cap_exceeded "
                        f"(used=${used_cost:.4f} estimated=${estimated_cost_usd:.4f} "
                        f"cap=${policy.max_cost_per_task_usd:.4f})"
                    ),
                    budget_remaining_usd=max(
                        0.0,
                        policy.max_cost_per_task_usd - used_cost - estimated_cost_usd,
                    ),
                )

        # Daily cost cap.
        if policy.max_cost_per_day_usd is not None and policy.max_cost_per_day_usd > 0:
            daily = await self.store.get_daily_usage_usd(provider=policy.provider)
            if daily + estimated_cost_usd > policy.max_cost_per_day_usd:
                return _CapResult(
                    cap="cost_per_day",
                    reason=(
                        "cost_per_day_cap_exceeded "
                        f"(used=${daily:.4f} estimated=${estimated_cost_usd:.4f} "
                        f"cap=${policy.max_cost_per_day_usd:.4f})"
                    ),
                    budget_remaining_usd=max(
                        0.0,
                        policy.max_cost_per_day_usd - daily - estimated_cost_usd,
                    ),
                )

        # Monthly cost cap.
        if policy.max_cost_per_month_usd is not None and policy.max_cost_per_month_usd > 0:
            monthly = await self.store.get_monthly_usage_usd(provider=policy.provider)
            if monthly + estimated_cost_usd > policy.max_cost_per_month_usd:
                return _CapResult(
                    cap="cost_per_month",
                    reason=(
                        "cost_per_month_cap_exceeded "
                        f"(used=${monthly:.4f} estimated=${estimated_cost_usd:.4f} "
                        f"cap=${policy.max_cost_per_month_usd:.4f})"
                    ),
                    budget_remaining_usd=max(
                        0.0,
                        policy.max_cost_per_month_usd - monthly - estimated_cost_usd,
                    ),
                )

        # Compute remaining budget under the tightest cap.
        remaining: float | None = None
        if policy.max_cost_per_day_usd is not None and policy.max_cost_per_day_usd > 0:
            daily = await self.store.get_daily_usage_usd(provider=policy.provider)
            remaining_day = max(0.0, policy.max_cost_per_day_usd - daily - estimated_cost_usd)
            remaining = remaining_day if remaining is None else min(remaining, remaining_day)
        if policy.max_cost_per_month_usd is not None and policy.max_cost_per_month_usd > 0:
            monthly = await self.store.get_monthly_usage_usd(provider=policy.provider)
            remaining_month = max(
                0.0,
                policy.max_cost_per_month_usd - monthly - estimated_cost_usd,
            )
            remaining = remaining_month if remaining is None else min(remaining, remaining_month)
        return _CapResult(cap=None, reason=None, budget_remaining_usd=remaining)

    async def _persist(
        self,
        decision: BudgetDecision,
        task_id: str | None,
        workflow_id: str | None,
    ) -> None:
        """Insert one preflight event row for ``decision``."""
        event_type = EVENT_TYPE_PREFLIGHT
        if decision.decision == DECISION_WARNING:
            event_type = EVENT_TYPE_BUDGET_WARNING
        try:
            await self.store.record_budget_event(
                task_id=task_id,
                workflow_id=workflow_id,
                policy_id=decision.policy_id,
                provider=decision.provider,
                model_name=decision.model_name,
                event_type=event_type,
                decision=decision.decision,
                estimated_prompt_tokens=decision.estimated_prompt_tokens,
                estimated_completion_tokens=decision.estimated_completion_tokens,
                estimated_total_tokens=decision.estimated_total_tokens,
                estimated_cost_usd=decision.estimated_cost_usd,
                budget_remaining_usd=decision.budget_remaining_usd,
                reason=decision.reason,
                metadata={
                    "cap_breached": decision.cap_breached,
                    **(decision.metadata or {}),
                },
            )
        except Exception:
            # Persistence is best-effort -- the decision result is the
            # authoritative gate. A failed insert is recorded as a
            # metric upstream.
            pass

    def explain_decision(self, decision: BudgetDecision) -> str:
        """Return a short human-readable explanation."""
        if decision.allowed:
            return (
                f"allowed under policy {decision.policy_name or 'none'} "
                f"({decision.provider}/{decision.model_name})"
            )
        if decision.warning:
            return (
                f"warning under policy {decision.policy_name or 'none'}: "
                f"{decision.reason or 'unknown'}"
            )
        return (
            f"blocked under policy {decision.policy_name or 'none'}: "
            f"{decision.reason or 'unknown'}"
        )


__all__ = ["BudgetPolicyEvaluator"]
