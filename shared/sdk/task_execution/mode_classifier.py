"""Deterministic execution-mode classifier.

No LLM call. Rules:

* If the request explicitly mentions Scrum-shaped vocabulary
  (``scrum`` / ``sprint`` / ``backlog`` / ``story`` /
  ``acceptance criteria`` / ``definition of done`` / ``DoD`` /
  ``project kickoff`` / the CJK equivalents 敏捷 / 衝刺 / 待辦清單)
  -> ``scrum_project``.
* Else if the request mentions dev-shaped vocabulary (``build`` /
  ``implement`` / ``develop`` / ``fix`` / ``refactor`` / ``code`` /
  ``test`` / ``API`` / ``UI`` / ``feature`` / ``bug`` / 開發 / 修正 /
  實作 / 測試) -> ``delivery_task``.
* Else -> ``simple_task``.

A short / TBD / "請再確認" / "need clarification" / "缺少" /
"看不懂" / "?" description sets ``clarification_required=True``.

The classifier is a pure function so it's trivially testable. The
caller decides what to DO with the result (create a clarification
request, mark ready_for_development, etc).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

EXECUTION_MODES = ("simple_task", "delivery_task", "scrum_project")

WORK_ITEM_STATUSES = (
    "intake_received",
    "analyzing",
    "needs_clarification",
    "clarified",
    "ready_for_development",
    "in_progress",
    "completed",
    "blocked",
    "canceled",
)

SCRUM_KEYWORDS = (
    "scrum",
    "sprint",
    "backlog",
    "user story",
    "story point",
    "acceptance criteria",
    "definition of done",
    "dod ",
    "project kickoff",
    "kickoff",
    "敏捷",
    "衝刺",
    "待辦清單",
    "驗收標準",
    "完成定義",
)

DEV_KEYWORDS = (
    "build",
    "implement",
    "develop",
    "fix",
    "refactor",
    "code",
    "test",
    "api",
    "ui",
    "feature",
    "bug",
    "endpoint",
    "schema",
    "開發",
    "修正",
    "實作",
    "測試",
    "重構",
)

GITHUB_KEYWORDS = (
    "pr",
    "pull request",
    "github",
    "branch",
    "merge",
    "commit",
    "repo",
    "repository",
)

CLARIFICATION_SIGNALS = (
    "tbd",
    "to be decided",
    "to be determined",
    "need clarification",
    "needs clarification",
    "please clarify",
    "請再確認",
    "請確認",
    "請補充",
    "需要釐清",
    "缺少",
    "看不懂",
    "再說",
    "?",
    "？",
)


@dataclass
class ClassificationResult:
    """The deterministic classifier output.

    ``reason`` carries the keyword family that triggered the bucket
    so /operations and tests can pin behaviour without re-running the
    classifier.
    """

    execution_mode: str
    scrum_enabled: bool
    development_required: bool
    github_required: bool
    clarification_required: bool
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "execution_mode": self.execution_mode,
            "scrum_enabled": self.scrum_enabled,
            "development_required": self.development_required,
            "github_required": self.github_required,
            "clarification_required": self.clarification_required,
            "reason": self.reason,
        }


def _contains_any(haystack: str, needles: tuple[str, ...]) -> str | None:
    for n in needles:
        if n in haystack:
            return n
    return None


def needs_clarification_signals(description: str) -> tuple[bool, str]:
    """Return ``(needed, reason)`` for clarification.

    A description shorter than 6 non-whitespace chars, missing a verb-
    shape, or carrying any clarification trigger ⇒ needs clarification.
    """
    text = (description or "").strip().lower()
    if len(re.sub(r"\s+", "", text)) < 6:
        return True, "description_too_short"
    hit = _contains_any(text, CLARIFICATION_SIGNALS)
    if hit:
        return True, f"signal:{hit.strip()}"
    return False, ""


def classify_execution_mode(
    *,
    request_type: str | None,
    description: str | None,
    github_options: dict[str, Any] | None = None,
    explicit_mode: str | None = None,
    message_content: str | None = None,
) -> ClassificationResult:
    """Deterministic classifier — no LLM, no remote call.

    ``explicit_mode`` short-circuits the rule chain when the caller
    knows the answer (e.g. orchestrator restart). ``github_options``
    short-circuits ``github_required``.
    """
    text_parts = [
        (request_type or "").lower(),
        (description or "").lower(),
        (message_content or "").lower(),
    ]
    haystack = " | ".join(text_parts)

    if explicit_mode in EXECUTION_MODES:
        mode = explicit_mode
        reason = f"explicit:{explicit_mode}"
    else:
        scrum_hit = _contains_any(haystack, SCRUM_KEYWORDS)
        dev_hit = _contains_any(haystack, DEV_KEYWORDS)
        if scrum_hit:
            mode = "scrum_project"
            reason = f"scrum_keyword:{scrum_hit.strip()}"
        elif dev_hit or (request_type or "").lower().startswith("dev."):
            mode = "delivery_task"
            reason = (
                f"dev_keyword:{dev_hit.strip()}"
                if dev_hit
                else f"request_type:{(request_type or '').lower()}"
            )
        else:
            mode = "simple_task"
            reason = "default"

    scrum_enabled = mode == "scrum_project"
    development_required = mode in ("delivery_task", "scrum_project")

    github_required = False
    if isinstance(github_options, dict):
        github_required = bool(github_options.get("enabled"))
    if not github_required:
        github_required = bool(_contains_any(haystack, GITHUB_KEYWORDS))

    needs_clar, clar_reason = needs_clarification_signals(description or "")
    if needs_clar:
        # Tack the clarification reason onto the main reason so
        # /operations can show both.
        reason = f"{reason};clarification:{clar_reason}"

    return ClassificationResult(
        execution_mode=mode,
        scrum_enabled=scrum_enabled,
        development_required=development_required,
        github_required=github_required,
        clarification_required=needs_clar,
        reason=reason,
    )
