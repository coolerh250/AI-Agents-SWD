"""Step 66B.3-V -- Operator Validation Record (documentation checks).

Confirms the operator's VISIBLE verdict on the Step 66B.3 RBAC / Audit / Safety
Hardening is recorded verbatim, Step 66B.3's final PASS status is documented, and
the no-workflow/no-external/no-production-action posture is stated.
Documentation-only stage -- no UI/backend code changed.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST = ROOT / "docs" / "test"

DOCS = {
    "validation-record": TEST / "step66b3-operator-validation-record.md",
    "hardening-report": TEST / "step66b3-rbac-audit-safety-hardening-report.md",
    "operator-validation-request": TEST
    / "step66b3-rbac-audit-safety-hardening-operator-validation-request.md",
    "known-gaps": TEST / "step66b3-known-gaps.md",
}


def _record_low() -> str:
    return DOCS["validation-record"].read_text(encoding="utf-8").lower()


def test_docs_exist() -> None:
    for name, p in DOCS.items():
        assert p.is_file(), name


def test_operator_validation_record_exists_and_visible() -> None:
    assert "visible" in _record_low()


def test_ten_checklist_items_documented() -> None:
    low = _record_low()
    for term in (
        "/tasks` page",
        "test role simulation banner",
        "current actor / role readout",
        "readable role labels",
        "/tasks/{id}` safety panel",
        "production_effect` warning",
        "dispatch_enabled=false`",
        "production_effect=true` blocked",
        "rbac error readability",
        "production_executed_true_count=0`",
    ):
        assert term.lower() in low, term


def test_step_66b3_final_pass_documented() -> None:
    low = _record_low()
    assert "step 66b.3 — pass" in low or "step 66b.3 - pass" in low


def test_no_workflow_execution_claimed() -> None:
    assert "no new workflow was executed" in _record_low()


def test_no_external_action_claimed() -> None:
    assert "no external action occurred" in _record_low()


def test_no_production_action_documented() -> None:
    low = _record_low()
    assert "no production action occurred" in low
    assert "production_executed_true_count=0" in low


def test_cross_doc_updates() -> None:
    assert "visible" in DOCS["hardening-report"].read_text(encoding="utf-8").lower()
    assert "visible" in DOCS["operator-validation-request"].read_text(encoding="utf-8").lower()
    assert "visible" in DOCS["known-gaps"].read_text(encoding="utf-8").lower()


def test_no_secret_shapes() -> None:
    shapes = re.compile(
        r"(-----BEGIN [A-Z ]*PRIVATE KEY|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
        r"AKIA[0-9A-Z]{16}|xoxb-[A-Za-z0-9-]{10,}|sk-ant-[A-Za-z0-9_-]{20,})"
    )
    for name, p in DOCS.items():
        assert not shapes.search(p.read_text(encoding="utf-8")), name
