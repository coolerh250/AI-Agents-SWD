"""Step 66SYNC.1-C -- tests for the Claude Design POC journey / UX reconciliation.

Deterministic, read-only. Mirrors scripts/verify_step66sync1_claude_design_reconciliation.py.
Must run with 0 failed and 0 skipped.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "docs" / "design" / "ai-agent-team-functional-poc-control-center-spec.md"
ACK = ROOT / "docs" / "handoffs" / "program-sync" / "step66sync1-claude-design-acknowledgement.md"
GAPS = ROOT / "docs" / "handoffs" / "program-sync" / "step66sync1-claude-design-ux-gap-register.md"
EVID = ROOT / "docs" / "test" / "step66sync1-claude-design-reconciliation-evidence.md"

CANONICAL_MAIN = "c1db4cc"
CC_HEAD = "828ea90"
CODEX_HEAD = "78aa4ee"
CONTEXT_ID = "AIAT-SYNC-20260803-01"

REQUIRED_SCREENS = [
    "POC Goal Entry",
    "Scope and Acceptance Review",
    "Execution Plan",
    "Project Overview",
    "Task Graph",
    "Agent/Partner Timeline",
    "Artifact Explorer",
    "Approval Center",
    "Blocker and Failure Center",
    "QA Dashboard",
    "Delivery Package",
    "Final Acceptance",
    "Cost and External Actions",
    "Safety Summary",
    "Retrospective",
]


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8") if p.is_file() else ""


def test_deliverables_exist():
    for p in (SPEC, ACK, GAPS, EVID):
        assert p.is_file(), f"missing {p}"


def test_context_and_heads():
    for p in (SPEC, ACK, EVID):
        t = _read(p)
        assert CONTEXT_ID in t
        assert CANONICAL_MAIN in t
        assert CC_HEAD in t
        assert CODEX_HEAD in t
    ack = _read(ACK).lower()
    assert "context_match" in ack
    assert "unresolved_canonical_mismatches: 0" in ack
    assert "open_product_owner_decisions: 3" in ack


def test_decisions_carried():
    for tag in ("D-1", "D-2", "D-3"):
        assert tag in _read(SPEC)
        assert tag in _read(ACK)
        assert tag in _read(GAPS)
    assert "product_owner_decision_required" in _read(SPEC).lower()
    assert "decision_dependent" in _read(GAPS).lower()


def test_journey_13_steps():
    spec = _read(SPEC).lower()
    for marker in (
        "inputs a development goal",
        "interprets the problem statement",
        "reviews scope and non-scope",
        "approves requirements and acceptance criteria",
        "builds an execution plan",
        "reviews task graph and responsibility",
        "begin collaboration",
        "observes real-time progress and artifacts",
        "handles approval, blocker, or scope change",
        "qa runs verification",
        "builds the delivery package",
        "performs final acceptance",
        "presents a retrospective",
    ):
        assert marker in spec, f"journey marker missing: {marker}"


def test_all_screens_present():
    spec = _read(SPEC).lower()
    for screen in REQUIRED_SCREENS:
        assert screen.lower() in spec, f"screen missing: {screen}"


def test_delivery_acceptance_and_failure_flows():
    spec = _read(SPEC).lower()
    for term in ("delivery package", "final acceptance", "accepted_with_follow_up", "rejected"):
        assert term in spec
    for term in ("dlq", "retry", "manual remediation", "abort", "partial delivery"):
        assert term in spec
    assert "mapping_gap" in spec


def test_privacy_exclusions():
    spec = _read(SPEC).lower()
    for term in ("private chain of thought", "raw system prompt", "raw token", "secret", "credential"):
        assert term in spec, f"must-not-display exclusion missing: {term}"


def test_no_final_visual_or_frontend_authorization():
    ack = _read(ACK).lower()
    assert "final visual design started:" in ack
    assert "frontend implementation authorized:" in ack
    # both answered NO
    assert "no" in ack.split("final visual design started:")[1][:20]
    assert "no" in ack.split("frontend implementation authorized:")[1][:20]


def test_no_local_absolute_paths():
    for p in (SPEC, ACK, GAPS, EVID):
        t = _read(p)
        assert "C:/Users" not in t and "C:\\Users" not in t
        assert "/home/" not in t
