"""Stage 49 -- build an operator-readable acceptance checklist.

Maps the mini delivery pilot evidence (acceptance evaluations, QA, safety,
known limitations) into a flat checklist for a human operator. Functional /
testing / safety items reflect collected evidence; human-review items stay
``pending`` -- the checklist NEVER auto-checks a human review item.
"""

from __future__ import annotations


def build_acceptance_checklist(evidence: dict) -> dict:
    """Return ``{"items": [...], "summary": {...}}`` for operator review."""
    acc_evals = evidence.get("acceptance_evaluations") or []
    acc_summary = evidence.get("acceptance_summary") or {}
    qa = evidence.get("qa") or {}
    safety = evidence.get("safety") or {}

    items: list[dict] = []

    # Functional criteria -- one per acceptance evaluation.
    for ev in acc_evals:
        status = ev.get("evaluation_status")
        items.append(
            {
                "key": ev.get("criterion_key") or "acceptance_criterion",
                "category": "functional",
                "label": ev.get("rationale_summary") or "acceptance criterion",
                "status": "checked" if status == "satisfied" else "pending",
                "evidence_ref": {
                    "evidence_type": ev.get("evidence_type"),
                    "evaluation_status": status,
                },
                "human_review": False,
            }
        )

    # Testing evidence.
    items.append(
        {
            "key": "testing_evidence",
            "category": "testing",
            "label": f"Automated tests: {qa.get('status', 'unknown')}",
            "status": (
                "checked" if qa.get("status") in ("passed", "passed_with_findings") else "pending"
            ),
            "evidence_ref": {
                "qa_status": qa.get("status"),
                "tests_passed": qa.get("tests_passed"),
                "tests_failed": qa.get("tests_failed"),
            },
            "human_review": False,
        }
    )

    # Safety evidence.
    items.append(
        {
            "key": "safety_evidence",
            "category": "safety",
            "label": f"Controlled-only safety posture: {safety.get('status', 'unknown')}",
            "status": (
                "checked" if safety.get("status") in ("safe", "safe_with_findings") else "pending"
            ),
            "evidence_ref": {"safety_status": safety.get("status")},
            "human_review": False,
        }
    )

    # Known limitations (informational, always acknowledged in the package).
    items.append(
        {
            "key": "known_limitations",
            "category": "known_limitations",
            "label": "Known limitations documented (no auth, SQLite only, no deploy)",
            "status": "checked",
            "evidence_ref": {},
            "human_review": False,
        }
    )

    # Human review items -- ALWAYS pending; never auto-checked.
    for key, label in (
        ("human_functional_acceptance", "Operator confirms functional acceptance"),
        ("human_business_acceptance", "Business owner accepts the delivery"),
    ):
        items.append(
            {
                "key": key,
                "category": "human_review",
                "label": label,
                "status": "pending",
                "evidence_ref": {},
                "human_review": True,
            }
        )

    summary = {
        "total_items": len(items),
        "checked_items": sum(1 for i in items if i["status"] == "checked"),
        "pending_items": sum(1 for i in items if i["status"] == "pending"),
        "human_review_pending": sum(
            1 for i in items if i["human_review"] and i["status"] == "pending"
        ),
        "acceptance_satisfied": acc_summary.get("satisfied", 0),
        "acceptance_failed": acc_summary.get("failed", 0),
    }
    return {"items": items, "summary": summary}


__all__ = ["build_acceptance_checklist"]
