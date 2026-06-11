"""Stage 30 — development-agent's LLM-assisted planning pipeline.

The development-agent gains a second generator mode,
``llm_assisted_proposal``. The mode is opt-in via two env vars:

* ``ENABLE_LLM_ASSISTED_PLANNING=true``  (off by default)
* ``LLM_PROVIDER=mock``                  (default; never the wire)

When enabled, the agent:

1. builds a deterministic prompt contract,
2. calls ``LLMProvider.generate_development_plan`` + redacts hash &
   preview, persists an ``llm_interactions`` row,
3. calls ``LLMProvider.generate_patch_proposal`` + redacts & persists,
4. runs :func:`shared.sdk.llm.policy.apply_llm_safety_policy` on the
   proposal,
5. inserts one ``llm_proposal_artifacts`` row with the safety result,
6. when policy is ``allowed``, converts the proposal into a controlled
   ``code_workspace`` artifact set (using the same deterministic write
   pipeline as Stage 28 — the LLM doesn't get to write files
   directly),
7. when policy is ``blocked``, leaves the workspace alone and emits
   ``llm.proposal_blocked`` / ``llm_proposal_blocked`` events.

The pipeline NEVER bypasses the existing code-workspace allowlist /
denylist / py_compile / diff-not-empty validators. It always sets
``production_executed=false`` and never writes a secret.
"""

from __future__ import annotations

import contextlib
import os
from typing import Any

from shared.sdk.audit.publisher import publish_audit_event
from shared.sdk.code_workspace import (
    CodeWorkspaceStore,
    DEFAULT_ALLOWED_PATHS,
    DEFAULT_DENIED_PATHS,
    classify_change_risk,
    compute_unified_diff,
    hash_content,
    summarize_diff,
    validate_allowed_path,
)
from shared.sdk.llm import (
    LLMInteractionStore,
    LLMSafetyPolicy,
    apply_llm_safety_policy,
    build_prompt_contract,
    get_provider,
    hash_text,
    redact_text,
)
from shared.sdk.llm.models import LLMDevelopmentPlan, LLMPatchProposal
from shared.sdk.llm_routing import (
    DECISION_BUDGET_BLOCKED,
    DECISION_DIRECT_MODEL_REJECTED,
    DECISION_FALLBACK_SELECTED,
    DECISION_MOCK_SELECTED,
    DECISION_POLICY_NOT_FOUND,
    DECISION_SELECTED,
    LLMRoutingDecision,
    ModelRouter,
    ModelRouterStore,
    build_capability_request,
)
from shared.sdk.notifications.client import send_notification
from shared.sdk.observability.metrics import (
    LLM_ESTIMATED_COST_TOTAL,
    LLM_INTERACTIONS_TOTAL,
    LLM_MODEL_DIRECT_SELECTION_REJECTED_TOTAL,
    LLM_MODEL_POLICY_MISSING_TOTAL,
    LLM_MODEL_ROUTING_BLOCKED_TOTAL,
    LLM_MODEL_ROUTING_BUDGET_BLOCKED_TOTAL,
    LLM_MODEL_ROUTING_FALLBACK_TOTAL,
    LLM_MODEL_ROUTING_HUMAN_REVIEW_TOTAL,
    LLM_MODEL_ROUTING_REQUESTS_TOTAL,
    LLM_MODEL_ROUTING_SELECTED_TOTAL,
    LLM_POLICY_BLOCKS_TOTAL,
    LLM_PROPOSALS_TOTAL,
    LLM_REAL_CALLS_BLOCKED_TOTAL,
    LLM_REAL_CALLS_TOTAL,
    LLM_TOKEN_USAGE_TOTAL,
)
from shared.sdk.observability.tracing import start_span


def llm_planning_enabled() -> bool:
    return os.environ.get("ENABLE_LLM_ASSISTED_PLANNING", "false").strip().lower() == "true"


def configured_provider_name() -> str:
    return (os.environ.get("LLM_PROVIDER", "mock") or "mock").strip().lower() or "mock"


def real_llm_enabled() -> bool:
    """Whether the operator opted into a real wire-level LLM call.

    Stage 30 still refuses to wire the actual network even when this is
    true — see :class:`ExternalLLMProviderGuard`.
    """
    return os.environ.get("RUN_REAL_LLM_TEST", "false").strip().lower() == "true"


class LLMPlannerPipeline:
    """Stateless pipeline used by ``DevelopmentAgent``.

    Construct one per ``handle()`` call. The pipeline holds no
    references that survive across tasks.
    """

    def __init__(
        self,
        *,
        llm_store: LLMInteractionStore | None = None,
        code_store: CodeWorkspaceStore | None = None,
        provider_name: str | None = None,
        router_store: ModelRouterStore | None = None,
    ) -> None:
        self._llm_store = llm_store or LLMInteractionStore()
        self._code_store = code_store or CodeWorkspaceStore()
        name = (provider_name or configured_provider_name()).strip().lower()
        self._provider_name = name or "mock"
        self._provider = get_provider(self._provider_name)
        self._policy = LLMSafetyPolicy()
        # Stage 38 -- Model Router. Defaults to a DB-backed store; tests
        # inject a fake. ``None`` makes the routing call a no-op, which
        # keeps existing tests that don't touch the DB unchanged.
        self._router_store = router_store
        self._router = ModelRouter(store=router_store) if router_store is not None else None
        self._routing_decisions: list[LLMRoutingDecision] = []

    @property
    def provider_name(self) -> str:
        return self._provider_name

    @property
    def model_name(self) -> str:
        return getattr(self._provider, "model_name", "mock-deterministic")

    # ------------------------------------------------------------------
    # Core entry point — drives the full proposal flow for one task.
    # ------------------------------------------------------------------

    async def run(
        self,
        *,
        task_id: str,
        workflow_id: str | None,
        description: str,
        request_type: str,
        execution_mode: str,
        acceptance_criteria: list[str] | None,
    ) -> dict[str, Any]:
        """Return a dict the caller can fold into its audit / response.

        Keys returned:

        * ``enabled``       — whether LLM planning was opted-in
        * ``provider``      — chosen provider name
        * ``policy_result`` — full safety policy dict
        * ``allowed``       — bool (policy.allowed)
        * ``blocked``       — bool (NOT allowed OR provider refused)
        * ``proposal_id``   — uuid string (or "")
        * ``proposal_status`` — proposed | policy_passed | blocked
        * ``interactions``  — [{interaction_id, type, status}, …]
        * ``proposed_files`` — list of dicts
        * ``usage``         — {provider, total_tokens, estimated_cost}
        * ``requires_human_review`` — True
        """
        contract_plan = build_prompt_contract(
            task_id=task_id,
            execution_mode=execution_mode,
            interaction_type="development_plan",
            description=description,
            allowed_paths=list(DEFAULT_ALLOWED_PATHS),
            denied_paths=list(DEFAULT_DENIED_PATHS),
            output_schema_name="LLMDevelopmentPlan",
            request_type=request_type,
            acceptance_criteria=acceptance_criteria,
        )
        contract_patch = dict(contract_plan)
        contract_patch.update(
            {
                "interaction_type": "patch_proposal",
                "output_schema_name": "LLMPatchProposal",
            }
        )

        plan: LLMDevelopmentPlan = await self._call_plan_provider(
            task_id=task_id,
            description=description,
            request_type=request_type,
            execution_mode=execution_mode,
            workflow_id=workflow_id,
        )
        plan_interaction = await self._persist_interaction(
            task_id=task_id,
            workflow_id=workflow_id,
            interaction_type="development_plan",
            prompt=contract_plan,
            response=plan,
        )

        proposal: LLMPatchProposal = await self._call_proposal_provider(
            task_id=task_id,
            description=description,
            request_type=request_type,
            execution_mode=execution_mode,
            workflow_id=workflow_id,
        )
        proposal_interaction = await self._persist_interaction(
            task_id=task_id,
            workflow_id=workflow_id,
            interaction_type="patch_proposal",
            prompt=contract_patch,
            response=proposal,
        )

        safety_result = apply_llm_safety_policy(proposal, policy=self._policy)
        allowed = bool(safety_result.get("allowed"))
        # Record per-rule blocks for the policy_blocks counter.
        for violation in safety_result.get("violations") or []:
            rule = str(violation.get("rule") or "unknown")
            LLM_POLICY_BLOCKS_TOTAL.labels(rule=rule).inc()

        status = "policy_passed" if allowed else "blocked"
        proposal_artifact = await self._llm_store.record_proposal(
            task_id=task_id,
            workflow_id=workflow_id,
            interaction_id=proposal_interaction.interaction_id,
            proposal_type="patch_proposal",
            status=status,
            proposed_files=[c.to_dict() for c in proposal.changes],
            plan={
                "summary": plan.summary,
                "proposed_steps": plan.proposed_steps,
                "rationale": proposal.rationale,
                "risk_level": proposal.risk_level,
                "rollback_plan": proposal.rollback_plan,
                "test_commands": proposal.test_commands,
                "confidence_plan": plan.confidence,
                "confidence_proposal": proposal.confidence,
                "patch_id": proposal.patch_id,
                "files_to_consider": plan.files_to_consider,
                "questions": plan.questions,
                "assumptions": plan.assumptions,
            },
            safety_result=safety_result,
            requires_human_review=True,
        )
        LLM_PROPOSALS_TOTAL.labels(
            provider=self._provider_name,
            proposal_type="patch_proposal",
            status=status,
        ).inc()

        # Stage 30 zero-cost usage record.
        await self._llm_store.record_usage(
            task_id=task_id,
            provider=self._provider_name,
            model_name=self.model_name,
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            estimated_cost=0.0,
        )
        LLM_TOKEN_USAGE_TOTAL.labels(provider=self._provider_name, model=self.model_name).inc(0)
        LLM_ESTIMATED_COST_TOTAL.labels(provider=self._provider_name, model=self.model_name).inc(0)

        # Audit + notification side effects.
        await self._record_audit_and_notify(
            task_id=task_id,
            workflow_id=workflow_id,
            allowed=allowed,
            proposal_id=proposal_artifact.proposal_id,
            interaction_ids=[
                plan_interaction.interaction_id,
                proposal_interaction.interaction_id,
            ],
            safety_result=safety_result,
        )

        return {
            "enabled": True,
            "provider": self._provider_name,
            "model_name": self.model_name,
            "policy_result": safety_result,
            "allowed": allowed,
            "blocked": not allowed,
            "proposal_id": proposal_artifact.proposal_id,
            "proposal_status": status,
            "interactions": [
                {
                    "interaction_id": plan_interaction.interaction_id,
                    "interaction_type": "development_plan",
                    "status": plan_interaction.status,
                },
                {
                    "interaction_id": proposal_interaction.interaction_id,
                    "interaction_type": "patch_proposal",
                    "status": proposal_interaction.status,
                },
            ],
            "proposed_files": [c.to_dict() for c in proposal.changes],
            "patch_id": proposal.patch_id,
            "plan_summary": plan.summary,
            "rationale": proposal.rationale,
            "rollback_plan": proposal.rollback_plan,
            "usage": {
                "provider": self._provider_name,
                "model_name": self.model_name,
                "total_tokens": 0,
                "estimated_cost": 0.0,
            },
            "requires_human_review": True,
            # Stage 38 -- routing decisions taken for this task. Empty
            # list when the router was not wired (mock / unit-test
            # paths). The orchestrator surfaces these via
            # /operations/llm/routing-decisions/{task_id}.
            "routing_decisions": [d.to_safe_dict() for d in self._routing_decisions],
            "_plan_obj": plan,
            "_proposal_obj": proposal,
        }

    # ------------------------------------------------------------------
    # Provider call with guard + metrics
    # ------------------------------------------------------------------

    def _record_real_call_skip(self) -> None:
        if self._provider_name in (
            "external_openai_placeholder",
            "external_anthropic_placeholder",
        ):
            LLM_REAL_CALLS_TOTAL.labels(provider=self._provider_name, result="skipped").inc()
            LLM_REAL_CALLS_BLOCKED_TOTAL.labels(
                provider=self._provider_name, reason="network_call_disabled"
            ).inc()

    async def _route_capability(
        self,
        *,
        task_id: str,
        workflow_id: str | None,
        capability: str,
        risk_level: str,
        requested_schema: str,
        estimated_input_tokens: int,
        allow_real_llm_requested: bool = False,
        allow_patch_generation_requested: bool = False,
    ) -> LLMRoutingDecision | None:
        """Stage 38 -- record a routing decision (if router is wired).

        Returns the decision so the caller can decide whether to
        proceed with the provider call. When ``self._router`` is
        ``None`` (tests / call sites that don't drive the DB) the
        method returns ``None`` and the caller stays on the historic
        provider path.
        """

        if self._router is None:
            return None
        request = build_capability_request(
            agent_name="development-agent",
            capability=capability,
            task_id=task_id,
            workflow_id=workflow_id,
            risk_level=risk_level,
            requested_schema=requested_schema,
            estimated_input_tokens=int(estimated_input_tokens or 0),
            allow_real_llm_requested=bool(allow_real_llm_requested),
            allow_patch_generation_requested=bool(allow_patch_generation_requested),
        )
        LLM_MODEL_ROUTING_REQUESTS_TOTAL.labels(
            agent_name="development-agent", capability=capability
        ).inc()
        with start_span(
            "llm_routing.request",
            **{
                "service.name": "development-agent",
                "agent_name": "development-agent",
                "capability": capability,
                "task_id": task_id or "",
                "requested_schema": requested_schema,
                "risk_level": risk_level,
            },
        ):
            decision = await self._router.route(request, persist=True)
        self._record_routing_metrics(decision)
        self._routing_decisions.append(decision)
        return decision

    def _record_routing_metrics(self, decision: LLMRoutingDecision) -> None:
        if decision.decision in (
            DECISION_SELECTED,
            DECISION_MOCK_SELECTED,
            DECISION_FALLBACK_SELECTED,
        ):
            LLM_MODEL_ROUTING_SELECTED_TOTAL.labels(
                agent_name=decision.agent_name,
                provider=decision.selected_provider or "unknown",
                model_tier=decision.selected_model_tier or "unknown",
                decision=decision.decision,
            ).inc()
            if decision.fallback_used:
                LLM_MODEL_ROUTING_FALLBACK_TOTAL.labels(
                    agent_name=decision.agent_name,
                    model_tier=decision.selected_model_tier or "unknown",
                ).inc()
        else:
            LLM_MODEL_ROUTING_BLOCKED_TOTAL.labels(
                agent_name=decision.agent_name,
                reason=decision.reason or "unknown",
            ).inc()
        if decision.decision == DECISION_POLICY_NOT_FOUND:
            LLM_MODEL_POLICY_MISSING_TOTAL.labels(
                agent_name=decision.agent_name, capability=decision.capability
            ).inc()
        if decision.decision == DECISION_BUDGET_BLOCKED:
            LLM_MODEL_ROUTING_BUDGET_BLOCKED_TOTAL.labels(
                agent_name=decision.agent_name,
                provider=decision.selected_provider or "unknown",
            ).inc()
        if decision.decision == DECISION_DIRECT_MODEL_REJECTED:
            LLM_MODEL_DIRECT_SELECTION_REJECTED_TOTAL.labels(
                agent_name=decision.agent_name, capability=decision.capability
            ).inc()
        if decision.requires_human_review:
            LLM_MODEL_ROUTING_HUMAN_REVIEW_TOTAL.labels(
                agent_name=decision.agent_name,
                capability=decision.capability,
            ).inc()

    async def _call_plan_provider(
        self,
        *,
        task_id: str,
        description: str,
        request_type: str,
        execution_mode: str,
        workflow_id: str | None = None,
    ) -> LLMDevelopmentPlan:
        # Stage 38 -- consult Model Router first. For mock provider
        # the routing yields mock_selected and the call proceeds. For
        # a real provider with no active policy / unauthorised alias /
        # budget overrun, the router blocks and we raise.
        decision = await self._route_capability(
            task_id=task_id,
            workflow_id=workflow_id,
            capability="development_plan",
            risk_level="medium",
            requested_schema="LLMDevelopmentPlan",
            estimated_input_tokens=max(len(description) // 4, 1),
            allow_real_llm_requested=real_llm_enabled(),
        )
        self._guard_routing(decision, "development_plan")
        with start_span(
            "llm.call_provider",
            **{
                "service.name": "development-agent",
                "agent": "development-agent",
                "task_id": task_id,
                "provider": self._provider_name,
                "interaction_type": "development_plan",
                "real_call": "false",
            },
        ):
            self._record_real_call_skip()
            return self._provider.generate_development_plan(
                task_id=task_id,
                description=description,
                request_type=request_type,
                execution_mode=execution_mode,
            )

    async def _call_proposal_provider(
        self,
        *,
        task_id: str,
        description: str,
        request_type: str,
        execution_mode: str,
        workflow_id: str | None = None,
    ) -> LLMPatchProposal:
        # Stage 38 -- patch_generation is hard-disabled at the router
        # level for any real provider. The router records the
        # decision (typically mock_selected for the default config or
        # BLOCKED with patch_generation_hard_disabled when the caller
        # opted in). The mock provider then continues to produce its
        # deterministic proposal artifact.
        decision = await self._route_capability(
            task_id=task_id,
            workflow_id=workflow_id,
            capability="code_patch_proposal",
            risk_level="high",
            requested_schema="LLMPatchProposal",
            estimated_input_tokens=max(len(description) // 4, 1),
            allow_real_llm_requested=real_llm_enabled(),
            # Patch generation is hard-disabled. We pass the flag
            # explicitly so the router records ``DECISION_BLOCKED``
            # with reason ``patch_generation_hard_disabled`` whenever
            # this code path is exercised in real mode.
            allow_patch_generation_requested=real_llm_enabled(),
        )
        self._guard_routing(decision, "code_patch_proposal", allow_mock_fallback=True)
        with start_span(
            "llm.call_provider",
            **{
                "service.name": "development-agent",
                "agent": "development-agent",
                "task_id": task_id,
                "provider": self._provider_name,
                "interaction_type": "patch_proposal",
                "real_call": "false",
            },
        ):
            self._record_real_call_skip()
            return self._provider.generate_patch_proposal(
                task_id=task_id,
                description=description,
                request_type=request_type,
                execution_mode=execution_mode,
            )

    def _guard_routing(
        self,
        decision: LLMRoutingDecision | None,
        capability: str,
        *,
        allow_mock_fallback: bool = True,
    ) -> None:
        """Raise unless the routing decision authorises a provider call.

        Mock provider invocation is still allowed when the router
        could not be consulted (no DB / no router). The intent is to
        gate real-LLM calls, not to break the mock baseline.
        """

        if decision is None:
            return
        if decision.is_select:
            return
        # Decision is non-select. For mock provider we MAY still
        # produce the mock artifact (the deterministic mock has no
        # external side effects) when the call site has indicated it
        # can fall back; otherwise we raise an LLMProviderError.
        if allow_mock_fallback and self._provider_name == "mock":
            return
        raise RuntimeError(
            f"ModelRouter blocked {capability}: decision={decision.decision} "
            f"reason={decision.reason}"
        )

    # ------------------------------------------------------------------
    # Interaction persistence (hash + redacted preview only)
    # ------------------------------------------------------------------

    async def _persist_interaction(
        self,
        *,
        task_id: str,
        workflow_id: str | None,
        interaction_type: str,
        prompt: dict[str, Any],
        response: Any,
    ) -> Any:
        prompt_str = _stable_json(prompt)
        response_str = _stable_json(
            response.to_dict() if hasattr(response, "to_dict") else response
        )
        with start_span(
            "llm.persist_interaction",
            **{
                "service.name": "development-agent",
                "agent": "development-agent",
                "task_id": task_id,
                "provider": self._provider_name,
                "interaction_type": interaction_type,
            },
        ):
            interaction = await self._llm_store.record_interaction(
                task_id=task_id,
                workflow_id=workflow_id,
                provider=self._provider_name,
                model_name=self.model_name,
                interaction_type=interaction_type,
                prompt_hash=hash_text(prompt_str),
                prompt_preview=redact_text(prompt_str),
                response_hash=hash_text(response_str),
                response_preview=redact_text(response_str),
                status="ok",
                token_usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                safety_result={},
            )
        LLM_INTERACTIONS_TOTAL.labels(
            provider=self._provider_name,
            model=self.model_name,
            interaction_type=interaction_type,
            status="ok",
        ).inc()
        return interaction

    # ------------------------------------------------------------------
    # Audit + notification
    # ------------------------------------------------------------------

    async def _record_audit_and_notify(
        self,
        *,
        task_id: str,
        workflow_id: str | None,
        allowed: bool,
        proposal_id: str,
        interaction_ids: list[str],
        safety_result: dict[str, Any],
    ) -> None:
        decision_type = "llm_proposal_created" if allowed else "llm_proposal_blocked"
        result_label = "policy_passed" if allowed else "blocked"
        with contextlib.suppress(Exception):
            await publish_audit_event(
                task_id=task_id,
                workflow_id=workflow_id or "",
                agent="development-agent",
                decision_type=decision_type,
                summary=(
                    f"llm proposal {proposal_id} {result_label} for {task_id} "
                    f"(provider={self._provider_name})"
                ),
                result=result_label,
                artifact_refs={
                    "proposal_id": proposal_id,
                    "interaction_ids": interaction_ids,
                    "provider": self._provider_name,
                    "model_name": self.model_name,
                    "safety_result": {
                        "allowed": safety_result.get("allowed"),
                        "violations": [
                            {"rule": v.get("rule"), "reason": v.get("reason")}
                            for v in (safety_result.get("violations") or [])
                        ],
                        "warnings": list(safety_result.get("warnings") or []),
                        "requires_human_review": True,
                    },
                    "token_usage": {"total_tokens": 0, "estimated_cost": 0.0},
                    "real_call": False,
                    "production_executed": False,
                },
            )
        # Also record an "interaction recorded" decision per interaction
        # so the audit timeline has a per-call entry.
        for iid in interaction_ids:
            with contextlib.suppress(Exception):
                await publish_audit_event(
                    task_id=task_id,
                    workflow_id=workflow_id or "",
                    agent="development-agent",
                    decision_type="llm_interaction_recorded",
                    summary=(
                        f"llm interaction {iid} recorded for {task_id} "
                        f"(provider={self._provider_name})"
                    ),
                    result="ok",
                    artifact_refs={
                        "interaction_id": iid,
                        "provider": self._provider_name,
                        "model_name": self.model_name,
                        "real_call": False,
                        "production_executed": False,
                    },
                )
        with contextlib.suppress(Exception):
            await send_notification(
                task_id,
                "llm.proposal_created" if allowed else "llm.proposal_blocked",
                (
                    f"llm proposal {proposal_id} {result_label} for {task_id} "
                    f"(provider={self._provider_name}, requires_human_review=true)"
                ),
            )
        if allowed:
            with contextlib.suppress(Exception):
                await send_notification(
                    task_id,
                    "llm.proposal_policy_passed",
                    f"llm proposal {proposal_id} policy passed for {task_id}",
                )
        if self._provider_name in (
            "external_openai_placeholder",
            "external_anthropic_placeholder",
        ):
            with contextlib.suppress(Exception):
                await send_notification(
                    task_id,
                    "llm.real_test_skipped",
                    f"real llm call skipped for {task_id} (provider={self._provider_name})",
                )
            with contextlib.suppress(Exception):
                await publish_audit_event(
                    task_id=task_id,
                    workflow_id=workflow_id or "",
                    agent="development-agent",
                    decision_type="llm_real_test_skipped",
                    summary=(
                        f"real llm call skipped for {task_id} " f"(provider={self._provider_name})"
                    ),
                    result="skipped",
                    artifact_refs={
                        "provider": self._provider_name,
                        "reason": "network_call_disabled",
                        "real_call": False,
                        "production_executed": False,
                    },
                )

    # ------------------------------------------------------------------
    # Optional follow-up: convert an allowed proposal into a controlled
    # code-workspace artifact set. The caller decides whether to call
    # this; the pipeline never auto-commits.
    # ------------------------------------------------------------------

    async def convert_to_workspace_artifacts(
        self,
        *,
        task_id: str,
        workflow_id: str | None,
        workspace_id: str,
        proposal_id: str,
        proposal: LLMPatchProposal,
    ) -> list[dict[str, Any]]:
        """Materialise an allowed LLM proposal into ``code_change_artifacts``.

        ``CodeWorkspaceStore.add_code_change_artifact`` is the only
        write path — we never bypass the existing Stage 28 validator.
        Each change is re-checked against the allowlist HERE as well so
        a misbehaving policy can't smuggle a denied path through.
        """
        results: list[dict[str, Any]] = []
        for change in proposal.changes:
            ok_path, why = validate_allowed_path(
                change.file_path,
                allowed=DEFAULT_ALLOWED_PATHS,
                denied=DEFAULT_DENIED_PATHS,
            )
            if not ok_path:
                results.append(
                    {
                        "file_path": change.file_path,
                        "status": "refused",
                        "reason": why,
                    }
                )
                continue
            content = change.proposed_content or ""
            diff_text = compute_unified_diff("", content, file_path=change.file_path)
            diff_summary_dict = summarize_diff(diff_text)
            # Store expects str — collapse the summary to a one-line label.
            diff_summary_str = (
                f"+{diff_summary_dict.get('added', 0)}/-{diff_summary_dict.get('removed', 0)} "
                f"({diff_summary_dict.get('hunks', 0)} hunks)"
            )
            artifact = await self._code_store.add_code_change_artifact(
                task_id=task_id,
                workflow_id=workflow_id,
                workspace_id=workspace_id,
                file_path=change.file_path,
                change_type=change.change_type,
                before_sha="",
                after_sha=hash_content(content),
                diff_summary=diff_summary_str,
                diff_text=diff_text[:4000],
                generated_content_preview=content[:20000],
                validation_status="pending",
            )
            results.append(
                {
                    "file_path": change.file_path,
                    "status": "accepted",
                    "artifact_id": artifact.artifact_id,
                }
            )
        with contextlib.suppress(Exception):
            await self._llm_store.update_proposal_status(
                proposal_id, status="accepted_for_workspace", linked_workspace_id=workspace_id
            )
        return results


def _stable_json(value: Any) -> str:
    import json

    try:
        return json.dumps(value, sort_keys=True, default=str)
    except Exception:
        return str(value)


def proposed_files_risk(changes: list[dict[str, Any]]) -> dict[str, object]:
    """Re-use the code-workspace risk classifier on LLM proposed files."""
    return classify_change_risk(list(changes))
