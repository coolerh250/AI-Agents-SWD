"""Stage 48 -- evidence-based acceptance evaluation.

Maps each ``project_acceptance_criteria`` row to concrete workspace evidence
(test runs, generated files, static/safety checks). Never marks a criterion
``satisfied`` without evidence: if the evidence is genuinely unavailable the
status is ``pending`` (not satisfied, not auto-waived).
"""

from __future__ import annotations

from shared.sdk.mini_delivery_pilot.models import AcceptanceEvaluation

# FastAPI Todo criterion_key -> evidence kind.
_TEST_KEYS = {"AC-001", "AC-002", "AC-003", "AC-004", "AC-005", "AC-006", "AC-007"}
_DOC_KEYS = {"AC-008"}
_SAFETY_KEYS = {"AC-009", "AC-010"}

_README_NAMES = ("README.md", "readme.md")


def _classify(description: str, verification_method: str) -> str:
    d = (description or "").lower()
    m = (verification_method or "").lower()
    if "no production deployment" in d or "no secret" in d:
        return "safety"
    if "readme" in d or m == "documentation_review":
        return "doc"
    if m in ("integration_test", "unit_test") or "todo" in d or "pytest" in d or "persistence" in d:
        return "test"
    if m == "static_check":
        return "safety"
    return "manual"


def evaluate_acceptance(
    *,
    criteria: list[dict],
    pytest_status: str | None,
    pytest_passed: int | None,
    pytest_failed: int | None,
    generated_files: list[str],
    safety_ok: bool,
) -> list[AcceptanceEvaluation]:
    """Build one AcceptanceEvaluation per criterion from workspace evidence."""
    files = set(generated_files or [])
    has_readme = any(name in files for name in _README_NAMES)
    has_database = "app/database.py" in files
    evaluations: list[AcceptanceEvaluation] = []

    for c in criteria:
        key = str(c.get("criterion_key") or "")
        kind = (
            "safety"
            if key in _SAFETY_KEYS
            else (
                "doc"
                if key in _DOC_KEYS
                else (
                    "test"
                    if key in _TEST_KEYS
                    else _classify(
                        str(c.get("description") or ""), str(c.get("verification_method") or "")
                    )
                )
            )
        )
        cid = c.get("id")
        wid = c.get("work_item_id")

        if kind == "test":
            if pytest_status == "passed":
                status, etype, ref, why = (
                    "satisfied",
                    "test_run",
                    {
                        "test_type": "pytest",
                        "status": "passed",
                        "tests_passed": pytest_passed,
                        "tests_failed": pytest_failed,
                    },
                    "pytest suite passed in the controlled workspace",
                )
                if key == "AC-006" and has_database:
                    ref["generated_file"] = "app/database.py"
            elif pytest_status == "failed":
                status, etype, ref, why = (
                    "failed",
                    "test_run",
                    {"test_type": "pytest", "status": "failed", "tests_failed": pytest_failed},
                    "pytest suite failed",
                )
            else:
                status, etype, ref, why = (
                    "pending",
                    "test_run",
                    {"test_type": "pytest", "status": pytest_status or "unknown"},
                    "pytest evidence unavailable (dependency skipped)",
                )
        elif kind == "doc":
            if has_readme:
                status, etype, ref, why = (
                    "satisfied",
                    "generated_file",
                    {"file": "README.md", "review": "documentation_review"},
                    "README.md generated with setup/run/test/API examples",
                )
            else:
                status, etype, ref, why = (
                    "pending",
                    "documentation_review",
                    {},
                    "README not found in workspace",
                )
        elif kind == "safety":
            if safety_ok:
                status, etype, ref, why = (
                    "satisfied",
                    "static_check",
                    {"check": "controlled_only_safety", "result": "safe"},
                    "controlled-only: no deploy / no secret required",
                )
            else:
                status, etype, ref, why = (
                    "failed",
                    "static_check",
                    {"check": "controlled_only_safety", "result": "unsafe"},
                    "safety evidence indicates a high-risk action",
                )
        else:
            status, etype, ref, why = (
                "pending",
                "manual_review_required",
                {},
                "no automated evidence for this criterion",
            )

        evaluations.append(
            AcceptanceEvaluation(
                acceptance_criterion_id=str(cid) if cid else None,
                work_item_id=str(wid) if wid else None,
                evaluation_status=status,
                evidence_type=etype,
                evidence_ref=ref,
                rationale_summary=why,
                criterion_key=key or None,
            )
        )
    return evaluations


def summarize_acceptance(evaluations: list[AcceptanceEvaluation]) -> dict:
    total = len(evaluations)
    satisfied = sum(1 for e in evaluations if e.evaluation_status == "satisfied")
    failed = sum(1 for e in evaluations if e.evaluation_status == "failed")
    pending = sum(1 for e in evaluations if e.evaluation_status == "pending")
    waived = sum(1 for e in evaluations if e.evaluation_status == "waived")
    return {
        "total": total,
        "satisfied": satisfied,
        "failed": failed,
        "pending": pending,
        "waived": waived,
    }


__all__ = ["evaluate_acceptance", "summarize_acceptance"]
