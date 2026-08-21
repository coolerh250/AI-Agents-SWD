"""Step AT-M3.1 -- deterministic mock reasoning provider.

No network, no credential, no vendor dependency. Every artifact is derived deterministically from
the request's verb, round number and context, so the same input always produces the same output --
useful for tests and demos, and never mistakable for a live model's output because the text says so
and the service records ``provider_mode='mock'`` on every invocation this provider produces.

Reuses the existing redaction/hashing helpers (``shared/sdk/llm/prompt_contract``) rather than
duplicating them: even in mock mode, caller-supplied free text is redacted before it is echoed
into a summary, so a caller that accidentally puts something secret-shaped into ``context`` does
not see it echoed back unredacted.
"""

from __future__ import annotations

import json

from shared.sdk.agent_reasoning.models import (
    CritiqueArtifact,
    DecisionSummaryArtifact,
    ProposalArtifact,
    ReasoningRequest,
)
from shared.sdk.llm.prompt_contract import hash_text, redact_text

_MOCK_ASSUMPTION = "mock_provider_no_live_model"


def _digest(request: ReasoningRequest) -> str:
    payload = json.dumps(
        {"verb": request.verb, "round": request.round_number, "context": request.context},
        sort_keys=True,
        default=str,
    )
    return hash_text(payload)[:12]


def _redacted(value: object, *, limit: int = 160, default: str) -> str:
    text = redact_text(str(value), limit=limit) if value else ""
    return text or default


class MockReasoningProvider:
    """Deterministic in-process generator. The default provider."""

    name = "mock"
    mode = "mock"

    def propose(self, request: ReasoningRequest) -> ProposalArtifact:
        digest = _digest(request)
        topic = _redacted(
            request.context.get("goal_statement") or request.context.get("summary"),
            default="the requested work",
        )
        return ProposalArtifact(
            summary=f"[mock] proposal for: {topic}",
            rationale_summary=(
                f"[mock] deterministic proposal derived from input digest {digest}; "
                "no live model was consulted"
            ),
            assumptions=(_MOCK_ASSUMPTION,),
            constraints=(),
            risks=(),
            questions=(),
            recommendation=(
                "[mock] proceed with the smallest viable decomposition; "
                "revisit once a live provider is authorized"
            ),
            confidence=0.5,
        )

    def critique(self, request: ReasoningRequest) -> CritiqueArtifact:
        digest = _digest(request)
        target = _redacted(request.context.get("proposal_summary"), default="the standing proposal")
        return CritiqueArtifact(
            summary=f"[mock] critique of: {target}",
            rationale_summary=(
                f"[mock] deterministic critique derived from input digest {digest}; "
                "no live model was consulted"
            ),
            concerns=(_MOCK_ASSUMPTION,),
            questions=(),
            recommendation=(
                "[mock] no objection raised; a live review is required before this is treated "
                "as genuine critique"
            ),
            confidence=0.5,
        )

    def summarize_decision(self, request: ReasoningRequest) -> DecisionSummaryArtifact:
        digest = _digest(request)
        raw_options = request.context.get("options_considered") or ["proceed", "hold"]
        options = tuple(
            _redacted(option, limit=200, default="option") for option in raw_options
        ) or ("proceed",)
        selected = _redacted(request.context.get("selected_option"), limit=200, default=options[0])
        return DecisionSummaryArtifact(
            summary=f"[mock] decision summary (digest {digest})",
            rationale_summary="[mock] deterministic summary; no live model was consulted",
            options_considered=options,
            selected_option=selected,
            dissent_summary=None,
            confidence=0.5,
        )


__all__ = ["MockReasoningProvider"]
