"""Step 66C.1-V -- Operator API Validation Record (documentation checks).

Confirms the operator's READY_WITH_GAPS verdict on the Step 66C.1 Agent
Workroom & Clarification Data/API Foundation is recorded verbatim, gaps
G1-G5 and their 66C.2/66C.3/66C.4/66S future-step mapping are documented, and
the no-workflow/no-resume/no-external/no-production-action posture is stated.
Documentation-only stage -- no backend/UI code changed.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST = ROOT / "docs" / "test"

DOCS = {
    "validation-record": TEST / "step66c1-operator-api-validation-record.md",
    "foundation-report": TEST / "step66c1-workroom-clarification-api-foundation-report.md",
    "operator-validation-request": TEST / "step66c1-operator-validation-request.md",
    "known-gaps": TEST / "step66c1-known-gaps.md",
    "implementation-sequence": TEST / "ai-team-work-step66-implementation-sequence.md",
    "risk-register": TEST / "ai-team-work-risk-register.md",
}


def _record_low() -> str:
    return DOCS["validation-record"].read_text(encoding="utf-8").lower()


def test_docs_exist() -> None:
    for name, p in DOCS.items():
        assert p.is_file(), name


def test_ready_with_gaps_documented() -> None:
    assert "ready_with_gaps" in _record_low()


def test_gaps_g1_to_g5_documented() -> None:
    low = _record_low()
    for gap in ("g1", "g2", "g3", "g4", "g5"):
        assert gap in low, gap
    for phrase in (
        "message visibility filtering",
        "reminder / expiry scheduler",
        "audit lookup",
        "project/team rbac scoping",
        "answered-twice guard",
    ):
        assert phrase in low, phrase


def test_future_step_mapping_documented() -> None:
    low = _record_low()
    for stage in ("66c.2", "66c.3", "66c.4", "66s"):
        assert stage in low, stage


def test_no_workflow_dispatch_claimed() -> None:
    low = _record_low()
    assert "no workflow dispatch" in low or "workflow dispatch | none" in low


def test_no_workflow_resume_claimed() -> None:
    low = _record_low()
    assert "no workflow resume" in low or "workflow resume | none" in low


def test_no_external_action_claimed() -> None:
    assert "no external action occurred" in _record_low()


def test_no_production_action_documented() -> None:
    low = _record_low()
    assert "no production action occurred" in low
    assert "production_executed_true_count=0" in low


def test_step_66c1_final_pass_documented() -> None:
    low = _record_low()
    assert "step 66c.1 — pass" in low or "step 66c.1 - pass" in low


def test_cross_doc_updates() -> None:
    assert "ready_with_gaps" in DOCS["foundation-report"].read_text(encoding="utf-8").lower()
    assert (
        "ready_with_gaps" in DOCS["operator-validation-request"].read_text(encoding="utf-8").lower()
    )
    known_gaps_low = DOCS["known-gaps"].read_text(encoding="utf-8").lower()
    assert "g1" in known_gaps_low
    assert "g5" in known_gaps_low
    seq_low = DOCS["implementation-sequence"].read_text(encoding="utf-8").lower()
    for stage in ("66c.2", "66c.3", "66c.4", "66s"):
        assert stage in seq_low, stage


def test_no_secret_shapes() -> None:
    shapes = re.compile(
        r"(-----BEGIN [A-Z ]*PRIVATE KEY|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
        r"AKIA[0-9A-Z]{16}|xoxb-[A-Za-z0-9-]{10,}|sk-ant-[A-Za-z0-9_-]{20,})"
    )
    for name, p in DOCS.items():
        assert not shapes.search(p.read_text(encoding="utf-8")), name
