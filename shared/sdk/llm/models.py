"""Stage 30 — Pydantic-style dataclasses for LLM-assisted development.

We deliberately use ``dataclass`` (not Pydantic) so the SDK has no extra
runtime dependency surface. Each model exposes ``to_dict()`` for the
operations + Discord views; ``from_provider()`` for provider responses
that already shape themselves correctly.

Schema rules (enforced in :mod:`shared.sdk.llm.policy`):

* ``change_type`` MUST be ``create`` or ``update`` — ``delete`` is
  refused outright.
* ``file_path`` MUST normalize through the code-workspace allowlist.
* ``proposed_content`` MUST NOT match any secret-like pattern.
* ``proposed_files`` MUST NOT touch any denylisted path.
* ``confidence`` is bound to ``[0.0, 1.0]``.
* ``requires_human_review`` defaults to ``True`` in this stage and the
  policy unconditionally re-affirms it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

#: Stage 30 explicitly forbids ``delete``. Mirrors the code-workspace
#: contract added in Stage 28.
ALLOWED_CHANGE_TYPES: tuple[str, ...] = ("create", "update")


def _clamp_confidence(value: Any) -> float:
    try:
        c = float(value)
    except (TypeError, ValueError):
        return 0.0
    if c < 0.0:
        return 0.0
    if c > 1.0:
        return 1.0
    return c


@dataclass
class LLMFileChange:
    """One proposed file change inside a patch proposal."""

    file_path: str
    change_type: str = "create"
    proposed_content: str = ""
    diff_summary: str = ""
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "file_path": self.file_path,
            "change_type": self.change_type,
            "proposed_content": self.proposed_content,
            "diff_summary": self.diff_summary,
            "reason": self.reason,
        }


@dataclass
class LLMDevelopmentPlan:
    """High-level plan returned by ``LLMProvider.generate_development_plan``."""

    task_id: str
    summary: str = ""
    files_to_consider: list[str] = field(default_factory=list)
    proposed_steps: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    questions: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    test_strategy: str = ""
    confidence: float = 0.5
    requires_human_review: bool = True

    def __post_init__(self) -> None:
        self.confidence = _clamp_confidence(self.confidence)
        # Stage 30 unconditionally requires human review — even an
        # over-confident mock response cannot bypass it.
        self.requires_human_review = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "summary": self.summary,
            "files_to_consider": list(self.files_to_consider),
            "proposed_steps": list(self.proposed_steps),
            "assumptions": list(self.assumptions),
            "questions": list(self.questions),
            "risks": list(self.risks),
            "test_strategy": self.test_strategy,
            "confidence": self.confidence,
            "requires_human_review": self.requires_human_review,
        }


@dataclass
class LLMPatchProposal:
    """File-level patch proposal returned by ``generate_patch_proposal``.

    Note: a patch proposal is NOT a workspace mutation. It lives in the
    ``llm_proposal_artifacts`` table until safety policy + (eventually)
    human review accept it, at which point a separate controlled-path
    converts it into ``code_change_artifacts``.
    """

    task_id: str
    patch_id: str = ""
    proposed_files: list[str] = field(default_factory=list)
    changes: list[LLMFileChange] = field(default_factory=list)
    rationale: str = ""
    risk_level: str = "low"
    safety_notes: list[str] = field(default_factory=list)
    test_commands: list[str] = field(default_factory=list)
    rollback_plan: str = ""
    confidence: float = 0.5
    requires_human_review: bool = True

    def __post_init__(self) -> None:
        self.confidence = _clamp_confidence(self.confidence)
        self.requires_human_review = True
        # Keep proposed_files and changes in sync — proposed_files is
        # what policy + storage scans first.
        if not self.proposed_files and self.changes:
            self.proposed_files = [c.file_path for c in self.changes if c.file_path]

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "patch_id": self.patch_id,
            "proposed_files": list(self.proposed_files),
            "changes": [c.to_dict() for c in self.changes],
            "rationale": self.rationale,
            "risk_level": self.risk_level,
            "safety_notes": list(self.safety_notes),
            "test_commands": list(self.test_commands),
            "rollback_plan": self.rollback_plan,
            "confidence": self.confidence,
            "requires_human_review": self.requires_human_review,
        }


@dataclass
class LLMTestPlan:
    """Test plan returned by ``generate_test_plan``."""

    task_id: str
    unit_tests: list[str] = field(default_factory=list)
    integration_tests: list[str] = field(default_factory=list)
    manual_tests: list[str] = field(default_factory=list)
    acceptance_checks: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "unit_tests": list(self.unit_tests),
            "integration_tests": list(self.integration_tests),
            "manual_tests": list(self.manual_tests),
            "acceptance_checks": list(self.acceptance_checks),
            "risks": list(self.risks),
        }


@dataclass
class LLMInteraction:
    """One row from ``llm_interactions``."""

    interaction_id: str
    task_id: str
    workflow_id: str | None = None
    provider: str = "mock"
    model_name: str = "mock-deterministic"
    interaction_type: str = "development_plan"
    prompt_hash: str = ""
    prompt_preview: str = ""
    response_hash: str = ""
    response_preview: str = ""
    status: str = "ok"
    token_usage: dict[str, Any] | None = None
    safety_result: dict[str, Any] = field(default_factory=dict)
    created_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "interaction_id": self.interaction_id,
            "task_id": self.task_id,
            "workflow_id": self.workflow_id,
            "provider": self.provider,
            "model_name": self.model_name,
            "interaction_type": self.interaction_type,
            "prompt_hash": self.prompt_hash,
            "prompt_preview": self.prompt_preview,
            "response_hash": self.response_hash,
            "response_preview": self.response_preview,
            "status": self.status,
            "token_usage": dict(self.token_usage) if self.token_usage else None,
            "safety_result": dict(self.safety_result),
            "created_at": self.created_at,
        }


@dataclass
class LLMProposalArtifact:
    """One row from ``llm_proposal_artifacts``."""

    proposal_id: str
    task_id: str
    workflow_id: str | None
    interaction_id: str | None
    proposal_type: str = "patch_proposal"
    status: str = "proposed"
    proposed_files: list[dict[str, Any]] = field(default_factory=list)
    plan: dict[str, Any] = field(default_factory=dict)
    safety_result: dict[str, Any] = field(default_factory=dict)
    requires_human_review: bool = True
    linked_workspace_id: str | None = None
    created_at: str | None = None
    updated_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "task_id": self.task_id,
            "workflow_id": self.workflow_id,
            "interaction_id": self.interaction_id,
            "proposal_type": self.proposal_type,
            "status": self.status,
            "proposed_files": list(self.proposed_files),
            "plan": dict(self.plan),
            "safety_result": dict(self.safety_result),
            "requires_human_review": self.requires_human_review,
            "linked_workspace_id": self.linked_workspace_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class LLMUsageRecord:
    """One row from ``llm_usage_records``. Stage 30 mock = zero cost."""

    usage_id: str
    task_id: str
    provider: str = "mock"
    model_name: str = "mock-deterministic"
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost: float = 0.0
    created_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "usage_id": self.usage_id,
            "task_id": self.task_id,
            "provider": self.provider,
            "model_name": self.model_name,
            "prompt_tokens": int(self.prompt_tokens),
            "completion_tokens": int(self.completion_tokens),
            "total_tokens": int(self.total_tokens),
            "estimated_cost": float(self.estimated_cost),
            "created_at": self.created_at,
        }
