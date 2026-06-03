"""Stage 29 — deterministic QA rules.

Each rule returns 0..N finding dicts ready for ``QAStore.add_finding``.
A rule never executes code, never opens a network connection, and
never touches the file system outside the workspace path it is given.

The classifier ``classify_finding_auto_fixable`` decides whether the
development-agent should be asked to fix the finding deterministically.
Anything security-related or destructive is non-auto-fixable and goes
straight to ``blocked_for_human_review``.
"""

from __future__ import annotations

import os
import re
from typing import Any, Iterable

from shared.sdk.code_workspace.policy import (
    DEFAULT_DENIED_PATHS,
    validate_allowed_path,
    validate_no_destructive_change,
    validate_no_secret_content,
)
from shared.sdk.code_workspace.validator import (
    validate_diff_not_empty,
    validate_python_syntax_if_py,
)

#: Loop guard. Two attempts is the documented contract; an operator
#: may raise it via ``QA_MAX_AUTO_FIX_ATTEMPTS`` but the qa-agent will
#: still refuse to run more than the value it loads.
MAX_AUTO_FIX_ATTEMPTS_DEFAULT = 2

#: Required PR draft body sections (Stage 28 contract).
_PR_DRAFT_REQUIRED_SECTIONS = (
    "## Summary",
    "## Changed Files",
    "## Generated Diff Summary",
    "## Validation Result",
    "## Risk Assessment",
    "## Rollback Plan",
    "## Safety Notes",
)

#: Severity values that block the workflow.
_BLOCKING_SEVERITIES = frozenset({"error", "critical"})

#: Categories that are NEVER auto-fixable. The qa-agent must mark
#: findings in these categories ``auto_fixable=False`` and the dev-agent
#: must refuse to fix them.
_NON_AUTO_FIXABLE_CATEGORIES = frozenset(
    {
        "security",
        "policy",
        "regression",
    }
)


def _norm_path(p: str | None) -> str:
    if not p:
        return ""
    return p.replace("\\", "/").strip()


def _finding(
    *,
    severity: str,
    category: str,
    title: str,
    description: str,
    recommendation: str = "",
    file_path: str | None = None,
    auto_fixable: bool = False,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "severity": severity,
        "category": category,
        "title": title,
        "description": description,
        "recommendation": recommendation,
        "file_path": file_path,
        "auto_fixable": bool(auto_fixable),
        "metadata": dict(metadata or {}),
    }


# ---------------------------------------------------------------------------
# Individual rules
# ---------------------------------------------------------------------------


def validate_generated_files_exist(
    workspace_path: str, file_paths: Iterable[str]
) -> list[dict[str, Any]]:
    """Every artifact path must exist on disk under ``workspace_path``."""
    findings: list[dict[str, Any]] = []
    for rel in file_paths:
        if not rel:
            continue
        full = os.path.join(workspace_path, rel)
        if not os.path.isfile(full):
            findings.append(
                _finding(
                    severity="error",
                    category="syntax",
                    title="generated file missing",
                    description=f"workspace path {rel!r} is referenced as an artifact but the file is not on disk",
                    recommendation="re-run the deterministic generator or auto-fix",
                    file_path=rel,
                    auto_fixable=True,
                )
            )
    return findings


def validate_python_syntax(workspace_path: str, file_paths: Iterable[str]) -> list[dict[str, Any]]:
    """``py_compile`` every ``*.py`` — a failure is a critical finding."""
    py_paths = [p for p in file_paths if p and p.endswith(".py")]
    if not py_paths:
        return []
    ok, reason = validate_python_syntax_if_py(workspace_path, py_paths)
    if ok:
        return []
    return [
        _finding(
            severity="critical",
            category="syntax",
            title="python syntax error",
            description=f"py_compile failed: {reason}",
            recommendation="regenerate the affected file via the deterministic template; if the issue persists, escalate to human review",
            auto_fixable=True,
            metadata={"reason": reason},
        )
    ]


def validate_test_files_exist_for_api_task(
    workspace_path: str,
    file_paths: Iterable[str],
    *,
    template_hint: str = "",
) -> list[dict[str, Any]]:
    """Every demo_api app file must come with a matching test."""
    rels = [_norm_path(p) for p in file_paths if p]
    has_api_app = any(p.startswith("apps/demo-generated/") and p.endswith("_api.py") for p in rels)
    has_api_test = any(
        p.startswith("tests/generated/") and p.endswith("_api.py") and "test_" in p for p in rels
    )
    if template_hint == "demo_api" and has_api_app and not has_api_test:
        return [
            _finding(
                severity="error",
                category="test",
                title="missing generated test file for demo API",
                description="the demo_api template emitted an app file but the matching test file is not in the workspace",
                recommendation="re-run the deterministic generator to emit the matching tests/generated/test_<slug>_api.py",
                auto_fixable=True,
                metadata={"template_hint": template_hint},
            )
        ]
    return []


def validate_diff_present(
    artifacts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Each artifact must carry a non-empty unified diff with at least one hunk."""
    findings: list[dict[str, Any]] = []
    for art in artifacts:
        diff = art.get("diff_text") or ""
        ok, reason = validate_diff_not_empty(diff)
        if not ok:
            findings.append(
                _finding(
                    severity="warning",
                    category="syntax",
                    title="empty diff",
                    description=f"artifact {art.get('file_path', '?')} has no diff hunks ({reason})",
                    recommendation="regenerate the artifact to ensure a non-empty diff",
                    file_path=art.get("file_path"),
                    auto_fixable=True,
                    metadata={"reason": reason},
                )
            )
    return findings


def validate_no_denied_paths(
    file_paths: Iterable[str],
    *,
    denied: Iterable[str] = DEFAULT_DENIED_PATHS,
) -> list[dict[str, Any]]:
    """A denied path is a policy violation — never auto-fixable."""
    findings: list[dict[str, Any]] = []
    for rel in file_paths:
        if not rel:
            continue
        ok, reason = validate_allowed_path(rel, allowed=("",), denied=denied)
        if not ok and reason.startswith("denied:"):
            findings.append(
                _finding(
                    severity="critical",
                    category="policy",
                    title="denied path written by generator",
                    description=f"{rel} matches the workspace denylist ({reason})",
                    recommendation="reject the task and escalate to a human reviewer; the deterministic generator must not target denied paths",
                    file_path=rel,
                    auto_fixable=False,
                    metadata={"reason": reason},
                )
            )
    return findings


_SECRET_FILE_HINTS = (".env", ".pem", ".key")


def validate_no_secret_patterns(
    workspace_path: str, file_paths: Iterable[str]
) -> list[dict[str, Any]]:
    """Refuse generated content that contains a secret literal."""
    findings: list[dict[str, Any]] = []
    for rel in file_paths:
        if not rel:
            continue
        full = os.path.join(workspace_path, rel)
        try:
            with open(full, "r", encoding="utf-8") as fh:
                content = fh.read()
        except OSError:
            continue
        ok, reason = validate_no_secret_content(content)
        if not ok:
            findings.append(
                _finding(
                    severity="critical",
                    category="security",
                    title="secret-like content detected",
                    description=f"file {rel} contains content matching {reason}",
                    recommendation="never auto-fix — escalate to human review",
                    file_path=rel,
                    auto_fixable=False,
                    metadata={"reason": reason},
                )
            )
    return findings


def validate_pr_draft_sections(pr_draft: dict[str, Any] | None) -> list[dict[str, Any]]:
    """The PR draft body must carry the 7 mandatory sections (Stage 28)."""
    if not pr_draft:
        return [
            _finding(
                severity="error",
                category="documentation",
                title="missing PR draft",
                description="workspace has artifacts but no pr_draft_artifact",
                recommendation="re-run the development-agent so it produces a PR draft",
                auto_fixable=False,
                metadata={"reason": "pr_draft_missing"},
            )
        ]
    body = pr_draft.get("body") or ""
    missing = [section for section in _PR_DRAFT_REQUIRED_SECTIONS if section not in body]
    if not missing:
        return []
    return [
        _finding(
            severity="error",
            category="documentation",
            title="PR draft missing required sections",
            description=f"PR draft body is missing: {', '.join(missing)}",
            recommendation="auto-fix appends placeholder sections to the existing body",
            auto_fixable=True,
            metadata={"missing_sections": missing},
        )
    ]


def validate_destructive_diff(artifacts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Any artifact whose diff contains a destructive payload is critical / not auto-fixable."""
    findings: list[dict[str, Any]] = []
    for art in artifacts:
        diff = art.get("diff_text") or ""
        ok, reason = validate_no_destructive_change(diff)
        if not ok:
            findings.append(
                _finding(
                    severity="critical",
                    category="security",
                    title="destructive payload in generated diff",
                    description=f"{art.get('file_path', '?')} contains {reason}",
                    recommendation="never auto-fix — escalate to human review",
                    file_path=art.get("file_path"),
                    auto_fixable=False,
                    metadata={"reason": reason},
                )
            )
    return findings


_ACCEPTANCE_KEYWORD_PATTERN = re.compile(
    r"\b(test|endpoint|doc|documentation|api|helper|utility)\b", re.IGNORECASE
)


def validate_acceptance_alignment(
    *,
    work_item: dict[str, Any] | None,
    artifacts: list[dict[str, Any]],
    template_hint: str = "",
) -> list[dict[str, Any]]:
    """Soft check — every acceptance criterion should mention a keyword we delivered."""
    if not work_item:
        return []
    criteria = work_item.get("acceptance_criteria")
    if not criteria or not isinstance(criteria, list):
        return []
    delivered = " ".join(
        (a.get("file_path") or "") + " " + template_hint for a in artifacts
    ).lower()
    unmet = []
    for criterion in criteria:
        if not isinstance(criterion, str):
            continue
        kw_hits = _ACCEPTANCE_KEYWORD_PATTERN.findall(criterion)
        if not kw_hits:
            continue
        if not any(kw.lower() in delivered for kw in kw_hits):
            unmet.append(criterion)
    if not unmet:
        return []
    return [
        _finding(
            severity="warning",
            category="acceptance",
            title="acceptance criteria not visibly satisfied",
            description=f"the following acceptance criteria don't match any keyword in the generated files: {unmet[:3]!r}",
            recommendation="human reviewer should confirm the deterministic generator delivered what was asked",
            auto_fixable=False,
            metadata={"unmet": unmet[:5]},
        )
    ]


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def classify_finding_auto_fixable(finding: dict[str, Any]) -> bool:
    """Return True iff the finding's category is in the auto-fixable set."""
    if not finding.get("auto_fixable"):
        return False
    if finding.get("category") in _NON_AUTO_FIXABLE_CATEGORIES:
        return False
    return True


def apply_qa_rules(
    *,
    workspace_path: str,
    artifacts: list[dict[str, Any]],
    file_paths: list[str],
    pr_draft: dict[str, Any] | None,
    work_item: dict[str, Any] | None,
    template_hint: str = "",
) -> list[dict[str, Any]]:
    """Run every deterministic rule and return the merged finding list.

    Caller decides how to act on each finding — this function only
    inspects.
    """
    findings: list[dict[str, Any]] = []
    findings.extend(validate_generated_files_exist(workspace_path, file_paths))
    findings.extend(validate_python_syntax(workspace_path, file_paths))
    findings.extend(
        validate_test_files_exist_for_api_task(
            workspace_path, file_paths, template_hint=template_hint
        )
    )
    findings.extend(validate_diff_present(artifacts))
    findings.extend(validate_no_denied_paths(file_paths))
    findings.extend(validate_no_secret_patterns(workspace_path, file_paths))
    findings.extend(validate_pr_draft_sections(pr_draft))
    findings.extend(validate_destructive_diff(artifacts))
    findings.extend(
        validate_acceptance_alignment(
            work_item=work_item, artifacts=artifacts, template_hint=template_hint
        )
    )
    # Reconcile auto_fixable against the non-auto-fixable category list.
    for f in findings:
        if not classify_finding_auto_fixable(f):
            f["auto_fixable"] = False
    return findings


def is_blocking(finding: dict[str, Any]) -> bool:
    return finding.get("severity") in _BLOCKING_SEVERITIES
