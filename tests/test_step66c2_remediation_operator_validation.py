"""Step 66C.2-R-V -- Operator Validation Record (docs-only checks).

Pure documentation stage: no backend change, no UI change, no workflow
execution. This file follows the repo's tests/test_stepNN_*.py convention --
it confirms the operator validation record documents the VISIBLE response,
the NOT_VISIBLE -> PASS_AFTER_REMEDIATION status history, and the required
safety/posture statements.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST = ROOT / "docs" / "test"

DOCS = {
    "operator-validation-record": TEST / "step66c2-remediation-operator-validation-record.md",
    "workroom-ui-report": TEST / "step66c2-workroom-ui-report.md",
    "remediation-report": TEST / "step66c2-remediation-report.md",
    "remediation-operator-validation-request": TEST
    / "step66c2-remediation-operator-validation-request.md",
    "known-gaps": TEST / "step66c2-known-gaps.md",
}


def _all_low() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in DOCS.values()).lower()


def _record_low() -> str:
    return DOCS["operator-validation-record"].read_text(encoding="utf-8").lower()


def test_docs_exist() -> None:
    for name, p in DOCS.items():
        assert p.is_file(), name


def test_visible_documented() -> None:
    assert "visible" in _record_low()


def test_pass_after_remediation_documented() -> None:
    assert "pass_after_remediation" in _all_low()


def test_initial_not_visible_preserved_as_historical_record() -> None:
    low = _all_low()
    assert "not_visible" in low
    assert "initial" in low


def test_clarification_ui_remediation_recorded_as_fixed() -> None:
    record_low = _record_low()
    assert "no longer a gap" in record_low or "no longer listed as a gap" in record_low
    assert "clarification" in record_low


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
