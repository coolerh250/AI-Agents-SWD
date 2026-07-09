"""Step 66A.3 -- AI Agents Team Work final UX blueprint (docs + posture)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST = ROOT / "docs" / "test"

DOCS = {
    "final-ux-blueprint": TEST / "ai-team-work-final-ux-blueprint.md",
    "mvp-implementation-scope": TEST / "ai-team-work-mvp-implementation-scope.md",
    "frontend-page-map": TEST / "ai-team-work-frontend-page-map.md",
    "task-lifecycle-model": TEST / "ai-team-work-task-lifecycle-model.md",
    "agent-workroom-blueprint": TEST / "ai-team-work-agent-workroom-blueprint.md",
    "delivery-inbox-blueprint": TEST / "ai-team-work-delivery-inbox-blueprint.md",
    "operator-action-center-blueprint": TEST / "ai-team-work-operator-action-center-blueprint.md",
    "web-research-governance-blueprint": TEST / "ai-team-work-web-research-governance-blueprint.md",
    "data-model-blueprint": TEST / "ai-team-work-data-model-blueprint.md",
    "api-blueprint": TEST / "ai-team-work-api-blueprint.md",
    "rbac-blueprint": TEST / "ai-team-work-rbac-blueprint.md",
    "step66-implementation-sequence": TEST / "ai-team-work-step66-implementation-sequence.md",
    "risk-register": TEST / "ai-team-work-risk-register.md",
    "acceptance-criteria": TEST / "ai-team-work-acceptance-criteria.md",
}


def _low(name: str) -> str:
    return DOCS[name].read_text(encoding="utf-8").lower()


def _all_low() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in DOCS.values()).lower()


def test_docs_exist() -> None:
    for name, p in DOCS.items():
        assert p.is_file(), name


def test_frontend_pages_listed() -> None:
    pm = _low("frontend-page-map")
    for page in (
        "/tasks/new",
        "/tasks/{id}/workroom",
        "/deliveries",
        "/operator/approvals",
        "/operator/dlq-retry",
        "/notifications",
        "/settings/web-research-sources",
    ):
        assert page in pm, page


def test_task_lifecycle_states_listed() -> None:
    lc = _low("task-lifecycle-model")
    for st in (
        "clarification_needed",
        "clarification_expired",
        "delivery_ready",
        "changes_requested",
        "qa_rerun_requested",
        "accepted",
        "archived",
    ):
        assert st in lc, st


def test_workroom_message_types_listed() -> None:
    wr = _low("agent-workroom-blueprint")
    for mt in (
        "clarification_question",
        "clarification_answer",
        "request_changes_note",
        "qa_result_note",
        "approval_request_note",
    ):
        assert mt in wr, mt


def test_delivery_actions_listed() -> None:
    di = _low("delivery-inbox-blueprint")
    for act in ("accept", "reject", "request changes", "re-run qa", "escalate", "archive"):
        assert act in di, act


def test_operator_queues_listed() -> None:
    oac = _low("operator-action-center-blueprint")
    for q in ("pending approvals", "dlq / retry", "incidents", "integration health"):
        assert q in oac, q


def test_web_whitelist_v01_listed() -> None:
    wr = _low("web-research-governance-blueprint")
    assert "whitelist v0.1" in wr
    for s in ("owasp", "nist", "arxiv"):
        assert s in wr, s


def test_data_models_listed() -> None:
    dm = _low("data-model-blueprint")
    for m in (
        "task_messages",
        "clarification_requests",
        "delivery_actions",
        "web_research_sources",
        "role_permissions",
    ):
        assert m in dm, m


def test_api_endpoints_listed() -> None:
    api = _low("api-blueprint")
    for ep in (
        "post /tasks",
        "get /deliveries",
        "post /deliveries/{id}/accept",
        "post /operator/dlq-retry/{id}/replay",
    ):
        assert ep in api, ep


def test_implementation_sequence_listed() -> None:
    seq = _low("step66-implementation-sequence")
    for st in ("66b", "66c", "66d", "66e", "66f", "66g", "66h"):
        assert st in seq, st


def test_risks_listed() -> None:
    rr = _low("risk-register")
    assert "workroom complexity" in rr
    assert "dlq replay safety" in rr


def test_acceptance_criteria_listed() -> None:
    ac = _low("acceptance-criteria")
    assert "acceptance criteria" in ac
    assert "operator" in ac
    assert "prod_exec=0" in ac


def test_decisions_and_confirmations_reflected() -> None:
    um = _low("final-ux-blueprint")
    for i in range(1, 15):
        assert f"d{i}" in um, f"D{i}"
    for i in range(1, 6):
        assert f"q{i}" in um, f"Q{i}"


def test_blueprint_only_posture() -> None:
    low = _all_low()
    for phrase in (
        "no ui implementation",
        "no backend implementation",
        "no runtime change",
        "no workflow execution",
        "no external action",
        "no production action",
    ):
        assert phrase in low, phrase


def test_no_secret_shapes() -> None:
    shapes = re.compile(
        r"(-----BEGIN [A-Z ]*PRIVATE KEY|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
        r"AKIA[0-9A-Z]{16}|xoxb-[A-Za-z0-9-]{10,}|sk-ant-[A-Za-z0-9_-]{20,})"
    )
    for name, p in DOCS.items():
        assert not shapes.search(p.read_text(encoding="utf-8")), name
