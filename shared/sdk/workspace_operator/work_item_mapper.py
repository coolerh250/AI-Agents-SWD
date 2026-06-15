"""Stage 47 -- map FastAPI Todo work items to generated files + test evidence.

Deterministic mapping from ``project_work_items`` to ``WorkItemExecutionLink``
rows. No work-item dispatch happens this stage -- these links are evidence
that the controlled workspace produced (and, where applicable, tested) the
output for each work item. Delivery (DEL-*) stays ``pending`` for Step 47.
"""

from __future__ import annotations

from shared.sdk.workspace_operator.models import WorkItemExecutionLink


def _status_for(work_item_key: str, work_type: str, tests_status: str | None) -> str:
    key = (work_item_key or "").upper()
    wt = (work_type or "").lower()
    tests_passed = tests_status == "passed"
    if key.startswith("DEL") or wt == "release":
        return "pending"  # delivery package is Step 47
    if key == "QA-002":
        if tests_status == "failed":
            return "failed"
        return "passed" if tests_passed else "tested"
    if wt == "qa" or key.startswith("QA"):
        return "tested"
    if wt in ("backend", "database") and tests_passed:
        return "tested"
    # requirement / architecture / backend / database / documentation -> generated
    return "generated"


def map_work_items(
    work_items: list[dict],
    *,
    tests_status: str | None,
    evidence_artifact_id: str | None = None,
) -> list[WorkItemExecutionLink]:
    """Build one execution link per work item with a deterministic status."""
    links: list[WorkItemExecutionLink] = []
    for w in work_items:
        wid = str(w.get("id") or "")
        if not wid:
            continue
        key = str(w.get("work_item_key") or "")
        links.append(
            WorkItemExecutionLink(
                work_item_id=wid,
                work_item_key=key or None,
                execution_status=_status_for(key, str(w.get("work_type") or ""), tests_status),
                evidence_artifact_id=evidence_artifact_id,
            )
        )
    return links


__all__ = ["map_work_items"]
