"""Stage 30 — deterministic safety policy applied to every LLM output.

This is the *only* gate between an LLM response and the controlled
code-workspace path. The policy is intentionally strict:

* schema valid
* every ``file_path`` passes the code-workspace allowlist + denylist
* every ``change_type`` is ``create`` / ``update`` (never ``delete``)
* no ``proposed_content`` carries a secret-shaped literal
* no proposed_files touch denied paths
* no destructive shell / SQL / git command appears in any content
* no production_deploy / no branch_protection edit
* ``max_files_changed`` not exceeded
* ``max_content_chars_per_file`` not exceeded
* ``confidence >= min_confidence_for_auto_proposal`` else warn
* ``requires_human_review`` forced to ``True`` regardless of input

A non-empty ``violations`` list flips ``allowed`` to ``False`` and the
caller MUST refuse to convert the proposal into a code_workspace.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from shared.sdk.code_workspace.policy import (
    DEFAULT_ALLOWED_PATHS,
    DEFAULT_DENIED_PATHS,
    validate_allowed_path,
    validate_change_type,
    validate_no_destructive_change,
    validate_no_secret_content,
)
from shared.sdk.llm.models import (
    ALLOWED_CHANGE_TYPES,
    LLMDevelopmentPlan,
    LLMFileChange,
    LLMPatchProposal,
    LLMTestPlan,
)

#: Stage 30 defaults — paranoid by design. Override via :class:`LLMSafetyPolicy`.
DEFAULT_POLICY_LIMITS: dict[str, Any] = {
    "max_files_changed": 5,
    "max_content_chars_per_file": 20000,
    "min_confidence_for_auto_proposal": 0.7,
    "requires_human_review": True,
}


@dataclass
class LLMSafetyPolicy:
    """Configurable safety limits."""

    max_files_changed: int = DEFAULT_POLICY_LIMITS["max_files_changed"]
    max_content_chars_per_file: int = DEFAULT_POLICY_LIMITS["max_content_chars_per_file"]
    min_confidence_for_auto_proposal: float = DEFAULT_POLICY_LIMITS[
        "min_confidence_for_auto_proposal"
    ]
    requires_human_review: bool = DEFAULT_POLICY_LIMITS["requires_human_review"]
    allowed_paths: tuple[str, ...] = DEFAULT_ALLOWED_PATHS
    denied_paths: tuple[str, ...] = DEFAULT_DENIED_PATHS

    def limits(self) -> dict[str, Any]:
        return {
            "max_files_changed": self.max_files_changed,
            "max_content_chars_per_file": self.max_content_chars_per_file,
            "min_confidence_for_auto_proposal": self.min_confidence_for_auto_proposal,
            "requires_human_review": self.requires_human_review,
        }


@dataclass
class _Result:
    allowed: bool = True
    warnings: list[str] = field(default_factory=list)
    violations: list[dict[str, Any]] = field(default_factory=list)
    requires_human_review: bool = True
    inspected_files: int = 0
    limits: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "warnings": list(self.warnings),
            "violations": list(self.violations),
            "requires_human_review": self.requires_human_review,
            "inspected_files": self.inspected_files,
            "limits": dict(self.limits),
        }


def _check_path(path: str, policy: LLMSafetyPolicy) -> tuple[bool, str]:
    return validate_allowed_path(
        path,
        allowed=policy.allowed_paths,
        denied=policy.denied_paths,
    )


def _check_change(
    change: LLMFileChange | dict[str, Any], policy: LLMSafetyPolicy
) -> list[dict[str, Any]]:
    if isinstance(change, dict):
        file_path = str(change.get("file_path") or "")
        change_type = str(change.get("change_type") or "")
        content = str(change.get("proposed_content") or "")
    else:
        file_path = change.file_path
        change_type = change.change_type
        content = change.proposed_content or ""

    violations: list[dict[str, Any]] = []
    ok_path, why_path = _check_path(file_path, policy)
    if not ok_path:
        violations.append(
            {
                "rule": "path_blocked",
                "file_path": file_path,
                "reason": why_path,
            }
        )
    ok_ct, why_ct = validate_change_type(change_type)
    if not ok_ct or change_type not in ALLOWED_CHANGE_TYPES:
        violations.append(
            {
                "rule": "change_type_blocked",
                "file_path": file_path,
                "reason": why_ct,
            }
        )
    ok_secret, why_secret = validate_no_secret_content(content)
    if not ok_secret:
        violations.append(
            {
                "rule": "secret_like_content",
                "file_path": file_path,
                "reason": why_secret,
            }
        )
    ok_destr, why_destr = validate_no_destructive_change(content)
    if not ok_destr:
        violations.append(
            {
                "rule": "destructive_content",
                "file_path": file_path,
                "reason": why_destr,
            }
        )
    if len(content) > policy.max_content_chars_per_file:
        violations.append(
            {
                "rule": "content_too_large",
                "file_path": file_path,
                "reason": (
                    f"content_chars={len(content)} > " f"max={policy.max_content_chars_per_file}"
                ),
            }
        )
    return violations


def _check_plan_text(plan: LLMDevelopmentPlan | LLMTestPlan) -> list[dict[str, Any]]:
    """Scrub the plan's free-text fields for destructive commands and
    secret-like content. Plans don't write files, but they CAN smuggle
    a credential through ``summary`` / ``risks`` if a real LLM
    misbehaves — refuse those too."""
    violations: list[dict[str, Any]] = []
    fields: list[str] = []
    if isinstance(plan, LLMDevelopmentPlan):
        fields = [
            plan.summary or "",
            plan.test_strategy or "",
            *(plan.assumptions or []),
            *(plan.questions or []),
            *(plan.risks or []),
            *(plan.proposed_steps or []),
        ]
    else:
        fields = [
            *(plan.unit_tests or []),
            *(plan.integration_tests or []),
            *(plan.manual_tests or []),
            *(plan.acceptance_checks or []),
            *(plan.risks or []),
        ]
    for snippet in fields:
        ok_secret, why = validate_no_secret_content(snippet)
        if not ok_secret:
            violations.append({"rule": "secret_like_content", "reason": why})
        ok_destr, why = validate_no_destructive_change(snippet)
        if not ok_destr:
            violations.append({"rule": "destructive_content", "reason": why})
    return violations


def apply_llm_safety_policy(
    output: LLMDevelopmentPlan | LLMPatchProposal | LLMTestPlan,
    *,
    policy: LLMSafetyPolicy | None = None,
) -> dict[str, Any]:
    """Apply the safety policy to a single LLM output object.

    Returns a JSON-serialisable result dict. Always sets
    ``requires_human_review=True`` regardless of the response value —
    Stage 30 does not allow auto-acceptance.
    """
    policy = policy or LLMSafetyPolicy()
    result = _Result(limits=policy.limits(), requires_human_review=True)

    if output is None:
        result.allowed = False
        result.violations.append({"rule": "schema_invalid", "reason": "output_is_none"})
        return result.to_dict()

    if isinstance(output, LLMPatchProposal):
        if len(output.changes) > policy.max_files_changed:
            result.violations.append(
                {
                    "rule": "too_many_files",
                    "reason": (
                        f"changes={len(output.changes)} > max=" f"{policy.max_files_changed}"
                    ),
                }
            )
        result.inspected_files = len(output.changes)
        for change in output.changes:
            result.violations.extend(_check_change(change, policy))
        # cross-check proposed_files list as well.
        for path in output.proposed_files or []:
            ok_path, why_path = _check_path(path, policy)
            if not ok_path:
                result.violations.append(
                    {"rule": "path_blocked", "file_path": path, "reason": why_path}
                )
        if output.confidence < policy.min_confidence_for_auto_proposal:
            result.warnings.append(
                f"low_confidence:{output.confidence:.2f}"
                f"<{policy.min_confidence_for_auto_proposal:.2f}"
            )
    elif isinstance(output, LLMDevelopmentPlan):
        result.violations.extend(_check_plan_text(output))
        # files_to_consider is informational — but if the LLM listed
        # denied paths there, we still warn so the operator notices.
        for path in output.files_to_consider or []:
            ok_path, why_path = _check_path(path, policy)
            if not ok_path:
                result.warnings.append(f"file_listed_but_blocked:{path}:{why_path}")
        if output.confidence < policy.min_confidence_for_auto_proposal:
            result.warnings.append(
                f"low_confidence:{output.confidence:.2f}"
                f"<{policy.min_confidence_for_auto_proposal:.2f}"
            )
    elif isinstance(output, LLMTestPlan):
        result.violations.extend(_check_plan_text(output))
    else:
        result.violations.append(
            {"rule": "schema_invalid", "reason": f"unknown_type:{type(output).__name__}"}
        )

    result.allowed = not result.violations
    return result.to_dict()
