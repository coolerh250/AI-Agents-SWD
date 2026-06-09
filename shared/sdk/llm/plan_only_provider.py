"""Stage 35 -- real-LLM plan-only provider.

The provider implements ONLY :meth:`generate_development_plan`. Both
:meth:`generate_patch_proposal` and :meth:`generate_test_plan` raise
``LLMProviderError`` so a misconfigured caller can never trick the
real provider into producing a patch.

The pre-flight contract (enforced by :func:`real_llm_plan_only_guard`):

* ``RUN_REAL_LLM_TEST=true``
* ``ENABLE_REAL_LLM_NETWORK_CALL=true``
* ``LLM_PROVIDER`` in ``external_openai`` / ``external_anthropic``
* matching API key present in env
* ``interaction_type == development_plan``
* ``allow_real == True`` (explicit caller opt-in)

The provider does NOT enforce the budget gate itself -- that is the
:class:`BudgetPolicyEvaluator` upstream. By the time
:meth:`generate_development_plan` runs, the orchestrator has already
asserted ``decision.allowed is True``.

The wire call is implemented via ``httpx`` if the dependency is
available; otherwise the provider returns a "skipped (httpx missing)"
plan so unit tests can exercise the surface offline. The real wire
path is intentionally compact: prompt redaction is delegated to
``redact_text`` from the prompt-contract module so an accidentally-
leaked key never reaches the wire body.
"""

from __future__ import annotations

import json
import os
from typing import Any

from shared.sdk.llm.models import (
    LLMDevelopmentPlan,
    LLMPatchProposal,
    LLMTestPlan,
)
from shared.sdk.llm.prompt_contract import hash_text, redact_text
from shared.sdk.llm.provider import LLMProviderError

#: Provider names the plan-only path accepts. Must match the Stage 30
#: factory naming so existing operations / safety surfaces continue to
#: classify the provider as ``external_*``.
REAL_PROVIDER_NAMES: tuple[str, ...] = (
    "external_openai",
    "external_anthropic",
)


def real_llm_plan_only_guard(
    *,
    provider_name: str,
    allow_real: bool,
    interaction_type: str,
    env: dict[str, str] | None = None,
) -> tuple[bool, str]:
    """Return ``(allowed, reason)`` for a real plan-only call.

    Stage 35 narrows the Stage 30 guard further:
    ``interaction_type`` MUST equal ``development_plan``.
    """
    src: dict[str, str] = dict(env) if env is not None else dict(os.environ)
    if interaction_type != "development_plan":
        return False, "interaction_type_not_plan"
    if not allow_real:
        return False, "allow_real_false"
    if provider_name not in REAL_PROVIDER_NAMES:
        return False, "provider_not_real_plan_only"
    run_real = (src.get("RUN_REAL_LLM_TEST", "false") or "").strip().lower() == "true"
    if not run_real:
        return False, "run_real_llm_test_false"
    network_ok = (src.get("ENABLE_REAL_LLM_NETWORK_CALL", "false") or "").strip().lower() == "true"
    if not network_ok:
        return False, "network_call_disabled"
    if provider_name == "external_openai":
        key_env = "OPENAI_API_KEY"
    else:
        key_env = "ANTHROPIC_API_KEY"
    key_value = (src.get(key_env, "") or src.get("LLM_API_KEY", "") or "").strip()
    if not key_value:
        return False, "api_key_missing"
    return True, "ok"


def _safe_summary_from_text(text: str, *, limit: int = 240) -> str:
    """Return a redacted summary of free-form text."""
    return redact_text(text or "", limit=limit)


def _build_user_prompt_body(*, contract: dict[str, Any]) -> str:
    """Build the wire prompt body deterministically.

    The contract carries the prompt envelope; we never include
    secrets or environment-variable values. The contract itself is
    serialisable JSON.
    """
    body = json.dumps(contract, sort_keys=True, separators=(",", ":"))
    return redact_text(body, limit=4000)


def _parse_openai_plan(*, task_id: str, response_json: dict[str, Any]) -> LLMDevelopmentPlan:
    """Parse an OpenAI chat completion into an ``LLMDevelopmentPlan``."""
    choices = response_json.get("choices") or []
    if not choices:
        return LLMDevelopmentPlan(task_id=task_id, summary="empty_response")
    content = choices[0].get("message", {}).get("content", "")
    return _parse_plan_text(task_id=task_id, content=content)


def _parse_anthropic_plan(*, task_id: str, response_json: dict[str, Any]) -> LLMDevelopmentPlan:
    """Parse a Claude messages response into an ``LLMDevelopmentPlan``."""
    blocks = response_json.get("content") or []
    text_chunks = [b.get("text", "") for b in blocks if b.get("type") == "text"]
    content = "\n".join(text_chunks)
    return _parse_plan_text(task_id=task_id, content=content)


def _parse_plan_text(*, task_id: str, content: str) -> LLMDevelopmentPlan:
    """Best-effort parser. Accepts JSON; falls back to free-text."""
    plan = LLMDevelopmentPlan(task_id=task_id)
    text = (content or "").strip()
    try:
        # The provider was instructed to emit JSON; tolerate fenced
        # code blocks.
        if text.startswith("```"):
            text = text.strip("` \n")
            if text.startswith("json"):
                text = text[4:].lstrip()
        parsed = json.loads(text) if text else {}
        if isinstance(parsed, dict):
            plan.summary = _safe_summary_from_text(str(parsed.get("summary", "")))
            plan.files_to_consider = [str(p) for p in parsed.get("files_to_consider") or [] if p]
            plan.proposed_steps = [
                _safe_summary_from_text(str(s), limit=160)
                for s in parsed.get("proposed_steps") or []
                if s
            ]
            plan.assumptions = [
                _safe_summary_from_text(str(a), limit=160)
                for a in parsed.get("assumptions") or []
                if a
            ]
            plan.questions = [
                _safe_summary_from_text(str(q), limit=160)
                for q in parsed.get("questions") or []
                if q
            ]
            plan.risks = [
                _safe_summary_from_text(str(r), limit=160) for r in parsed.get("risks") or [] if r
            ]
            plan.test_strategy = _safe_summary_from_text(
                str(parsed.get("test_strategy", "")), limit=500
            )
            try:
                plan.confidence = float(parsed.get("confidence", 0.5))
            except (TypeError, ValueError):
                plan.confidence = 0.5
            return plan
    except (TypeError, ValueError, json.JSONDecodeError):
        pass
    # Fallback: stash the free text as the summary so the safety
    # policy still scans it.
    plan.summary = _safe_summary_from_text(text)
    plan.proposed_steps = []
    plan.assumptions = ["model_returned_free_text", "best_effort_parse"]
    return plan


class RealLLMPlanOnlyProvider:
    """Plan-only real-LLM provider (OpenAI or Anthropic).

    The provider never produces patches. It always sets
    ``requires_human_review=True`` on the returned plan -- even when
    the real model returned a high confidence value.
    """

    def __init__(
        self,
        *,
        vendor: str,
        model_name: str | None = None,
        env: dict[str, str] | None = None,
    ) -> None:
        if vendor not in ("openai", "anthropic"):
            raise LLMProviderError(f"unknown_vendor:{vendor}")
        self._vendor = vendor
        self.name = f"external_{vendor}"
        # Default model -- conservative pick from the pricing table.
        if vendor == "openai":
            default_model = "gpt-4o-mini"
            env_var = "OPENAI_MODEL"
        else:
            default_model = "claude-3-5-haiku"
            env_var = "ANTHROPIC_MODEL"
        src = env if env is not None else os.environ
        self.model_name = (
            model_name or src.get(env_var, "") or default_model
        ).strip() or default_model

    # ------------------------------------------------------------------
    # Plan-only entry point.
    # ------------------------------------------------------------------

    def generate_development_plan(
        self,
        *,
        task_id: str,
        prompt_contract: dict[str, Any] | None = None,
        prompt_text: str | None = None,
        allow_real: bool = False,
        env: dict[str, str] | None = None,
        **_: Any,
    ) -> LLMDevelopmentPlan:
        """Issue ONE plan-only request. Caller asserts budget approved."""
        contract = prompt_contract or {}
        allowed, reason = real_llm_plan_only_guard(
            provider_name=self.name,
            allow_real=allow_real,
            interaction_type=contract.get("interaction_type", "development_plan"),
            env=env,
        )
        if not allowed:
            # The guard refused -- return a deterministic empty plan
            # so the caller can audit the reason without crashing.
            plan = LLMDevelopmentPlan(
                task_id=task_id,
                summary=f"real_llm_test_skipped:{reason}",
                assumptions=[
                    f"provider={self.name}",
                    f"real_call_skipped:{reason}",
                ],
                confidence=0.0,
                requires_human_review=True,
            )
            return plan

        # The real wire call. ``httpx`` is the project's HTTP client of
        # choice (already used elsewhere in the platform).
        try:
            import httpx
        except ImportError:
            return LLMDevelopmentPlan(
                task_id=task_id,
                summary="real_call_skipped:httpx_missing",
                assumptions=[f"provider={self.name}", "httpx_missing"],
                confidence=0.0,
                requires_human_review=True,
            )

        src = env if env is not None else os.environ
        timeout = float(src.get("LLM_REAL_TIMEOUT_SECONDS", "30") or 30)
        user_body = _build_user_prompt_body(contract=contract)
        # The prompt body is JSON-encoded contract; we ALSO append
        # the operator's free-text task summary (after redaction) so a
        # real LLM has enough context to plan. Both pieces are bounded.
        free_text = (prompt_text or "").strip()
        if free_text:
            user_body += "\n\nTASK_SUMMARY:\n" + redact_text(free_text, limit=2000)

        if self._vendor == "openai":
            api_key = (src.get("OPENAI_API_KEY", "") or src.get("LLM_API_KEY", "") or "").strip()
            url = "https://api.openai.com/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": self.model_name,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are a planning-only assistant. Return JSON "
                            "with fields: summary, files_to_consider (list), "
                            "proposed_steps (list), assumptions (list), "
                            "questions (list), risks (list), test_strategy, "
                            "confidence (0..1). Do NOT produce code, patches, "
                            "or file contents. Always set "
                            "requires_human_review=true."
                        ),
                    },
                    {"role": "user", "content": user_body},
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.2,
            }
            parser = _parse_openai_plan
        else:
            api_key = (src.get("ANTHROPIC_API_KEY", "") or src.get("LLM_API_KEY", "") or "").strip()
            url = "https://api.anthropic.com/v1/messages"
            headers = {
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            }
            payload = {
                "model": self.model_name,
                "max_tokens": 1024,
                "system": (
                    "You are a planning-only assistant. Return JSON with "
                    "fields: summary, files_to_consider, proposed_steps, "
                    "assumptions, questions, risks, test_strategy, "
                    "confidence (0..1). No code or file contents."
                ),
                "messages": [{"role": "user", "content": user_body}],
            }
            parser = _parse_anthropic_plan

        try:
            response = httpx.post(url, headers=headers, json=payload, timeout=timeout)
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            return LLMDevelopmentPlan(
                task_id=task_id,
                summary=f"real_call_failed:{exc.__class__.__name__}",
                assumptions=[f"provider={self.name}", "wire_call_failed"],
                confidence=0.0,
                requires_human_review=True,
            )

        plan = parser(task_id=task_id, response_json=data)
        plan.requires_human_review = True
        # Track usage on the plan so the caller can record cost.
        usage = data.get("usage") if isinstance(data, dict) else None
        if isinstance(usage, dict):
            tokens_in = usage.get("prompt_tokens") or usage.get("input_tokens") or 0
            tokens_out = usage.get("completion_tokens") or usage.get("output_tokens") or 0
            plan.assumptions = list(plan.assumptions) + [
                f"actual_prompt_tokens={int(tokens_in)}",
                f"actual_completion_tokens={int(tokens_out)}",
                f"provider={self.name}",
                f"model={self.model_name}",
                f"response_hash={hash_text(json.dumps(data, sort_keys=True))[:16]}",
            ]
        else:
            plan.assumptions = list(plan.assumptions) + [
                f"provider={self.name}",
                f"model={self.model_name}",
                "actual_usage_unknown",
            ]
        return plan

    # ------------------------------------------------------------------
    # Hard-refused entry points.
    # ------------------------------------------------------------------

    def generate_patch_proposal(self, **_: Any) -> LLMPatchProposal:
        raise LLMProviderError(f"plan_only_provider_refuses_patch:{self.name}")

    def generate_test_plan(self, **_: Any) -> LLMTestPlan:
        raise LLMProviderError(f"plan_only_provider_refuses_test_plan:{self.name}")


__all__ = [
    "REAL_PROVIDER_NAMES",
    "RealLLMPlanOnlyProvider",
    "real_llm_plan_only_guard",
]
