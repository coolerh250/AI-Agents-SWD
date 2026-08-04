from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts/verify_step66sync1_codex_frontend_reconciliation.py"
ACK_DOC = REPO / "docs/handoffs/program-sync/step66sync1-codex-acknowledgement.md"
GAP_DOC = REPO / "docs/handoffs/program-sync/step66sync1-codex-frontend-gap-register.md"
EVIDENCE_DOC = REPO / "docs/test/step66sync1-codex-frontend-reconciliation-evidence.md"
APP_TSX = REPO / "apps/admin-console/src/App.tsx"
MARKER = "STEP66SYNC1_CODEX_FRONTEND_RECONCILIATION_VERIFY: PASS"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_verifier_passes() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=REPO,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert MARKER in result.stdout


def test_required_docs_contain_context_and_marker() -> None:
    combined = "\n".join(read(path) for path in [ACK_DOC, GAP_DOC, EVIDENCE_DOC])

    for token in [
        "AIAT-SYNC-20260803-01",
        "c1db4cc",
        "828ea90",
        "UNRESOLVED_CANONICAL_MISMATCHES: 0",
        "OPEN_PRODUCT_OWNER_DECISIONS: 3",
        "production_executed_true_count=0",
        MARKER,
    ]:
        assert token in combined


def test_all_routes_from_source_are_inventoried() -> None:
    app = read(APP_TSX)
    evidence = read(EVIDENCE_DOC)
    routes = re.findall(r'<Route\s+path="([^"]+)"', app)

    assert routes
    for route in routes:
        assert f"| `{route}` |" in evidence


def test_control_center_and_questions_are_classified() -> None:
    evidence = read(EVIDENCE_DOC)

    for area in [
        "Goal and Acceptance",
        "Work Items and Task Graph",
        "Agent and Partner Activity Timeline",
        "Artifacts and Evidence",
        "Approvals, Blockers and Failures",
        "QA, Delivery and Final Acceptance",
    ]:
        assert area in evidence

    for question in [
        "What is currently being worked on?",
        "Which Agent or AI partner is responsible?",
        "Which requirement does the work correspond to?",
        "What generation mode is currently used?",
        "Which artifacts are complete?",
        "What commits, branches, or Draft PRs exist?",
        "Which step failed or retried?",
        "Did it enter DLQ?",
        "Who needs to approve?",
        "Did QA pass?",
        "Is it deliverable now?",
        "How much LLM cost?",
        "How many external actions occurred?",
        "What is production action count?",
        "Has PO accepted delivery?",
    ]:
        assert question in evidence

    assert "YES: 1" in evidence
    assert "PARTIAL: 10" in evidence
    assert "NO: 2" in evidence
    assert "DECISION_DEPENDENT: 2" in evidence


def test_d_decisions_are_carried_forward() -> None:
    combined = "\n".join(read(path) for path in [ACK_DOC, GAP_DOC, EVIDENCE_DOC])

    assert "D-1" in combined
    assert "D-2" in combined
    assert "D-3" in combined
    assert "DECISION_DEPENDENT" in combined
    assert "Implementation started:\nNO" in combined


def test_api_inventory_names_missing_contracts() -> None:
    evidence = read(EVIDENCE_DOC)

    assert "| Partner executions | NOT_IMPLEMENTED | NOT_IMPLEMENTED | NOT_IMPLEMENTED |" in evidence
    assert "| Approvals | Placeholder only | NOT_IMPLEMENTED for UI | NOT_IMPLEMENTED |" in evidence
    assert "| PO acceptance | latest delivery state only; formal inbox/detail missing | partial |" in evidence


def test_no_runtime_source_changed() -> None:
    result = subprocess.run(
        [
            "git",
            "diff",
            "--name-only",
            "HEAD",
            "--",
            "apps",
            "services",
            "infra",
            "shared",
            "migrations",
        ],
        cwd=REPO,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == ""
