"""Step 66C.3-V -- Operator Validation Record (docs-only checks).

Pure documentation stage: no backend change, no frontend runtime change, no
workflow execution. This file follows the repo's tests/test_stepNN_*.py
convention -- it confirms the operator validation record documents the
VISIBLE response, all 12 checklist items, G1/G3/G5 fixed status, and the
required safety/posture statements.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST = ROOT / "docs" / "test"

DOCS = {
    "operator-validation-record": TEST / "step66c3-operator-validation-record.md",
    "hardening-report": TEST / "step66c3-workroom-audit-visibility-hardening-report.md",
    "operator-validation-request": TEST / "step66c3-operator-validation-request.md",
    "known-gaps": TEST / "step66c3-known-gaps.md",
}

CHECKLIST_ITEMS = [
    "workroom visible",
    "visibility note visible",
    "audit evidence section visible",
    "allowed role can view safe audit evidence",
    "restricted role gets a readable restricted message",
    "does not expose raw message body",
    "does not expose raw clarification answer",
    "second answer attempt is blocked",
    "clarification_already_answered",
    "dispatch_enabled: false",
    "resume_dispatch_enabled: false",
    "production_executed_true_count = 0",
]


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower())


def _all_low() -> str:
    return _norm("\n".join(p.read_text(encoding="utf-8") for p in DOCS.values()))


def _record_low() -> str:
    return _norm(DOCS["operator-validation-record"].read_text(encoding="utf-8"))


def test_docs_exist() -> None:
    for name, p in DOCS.items():
        assert p.is_file(), name


def test_visible_documented() -> None:
    assert "visible" in _record_low()


def test_all_12_checklist_items_documented() -> None:
    record_low = _record_low()
    for item in CHECKLIST_ITEMS:
        assert item in record_low, item


def test_g1_g3_g5_fixed_documented() -> None:
    record_low = _record_low()
    for gap_id in ("g1", "g3", "g5"):
        assert gap_id in record_low, gap_id
    assert "fixed" in record_low


def test_remaining_gaps_mapped() -> None:
    low = _all_low()
    for gap_id in ("g2", "g4", "g6"):
        assert gap_id in low, gap_id
    for target in ("66c.4", "66s", "later"):
        assert target in low, target
    assert "pagination" in low
    assert "client-hidden rbac" in low


def test_step66c4_ready_to_start_documented() -> None:
    low = _all_low()
    assert "ready_to_start" in low


def test_no_workflow_dispatch_claimed() -> None:
    assert "no workflow dispatch" in _all_low()


def test_no_workflow_resume_claimed() -> None:
    assert "no workflow resume" in _all_low()


def test_no_external_action_claimed() -> None:
    assert "no external action" in _all_low()


def test_no_production_action_documented() -> None:
    assert "no production action" in _all_low()


def test_production_executed_true_count_zero_documented() -> None:
    assert "production_executed_true_count=0" in _all_low()


def test_no_secret_shapes() -> None:
    shapes = re.compile(
        r"(-----BEGIN [A-Z ]*PRIVATE KEY|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
        r"AKIA[0-9A-Z]{16}|xoxb-[A-Za-z0-9-]{10,}|sk-ant-[A-Za-z0-9_-]{20,})"
    )
    for name, p in DOCS.items():
        assert not shapes.search(p.read_text(encoding="utf-8")), name
