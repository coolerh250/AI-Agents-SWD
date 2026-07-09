"""Step 66B.2-V -- Operator UI Validation Record (documentation checks).

Confirms the operator's VISIBLE verdict on the Step 66B.2 Admin Console Task
Assignment UI is recorded verbatim, with the "Create Task" label wording noted
as a non-blocking difference (not a functional gap), Step 66B.2's final PASS
status documented, and the no-workflow/no-external/no-production-action
posture stated. Documentation-only stage -- no UI/backend code changed.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST = ROOT / "docs" / "test"

DOCS = {
    "validation-record": TEST / "step66b2-operator-ui-validation-record.md",
    "ui-report": TEST / "step66b2-task-assignment-ui-report.md",
    "operator-validation-request": TEST
    / "step66b2-task-assignment-ui-operator-validation-request.md",
    "known-gaps": TEST / "step66b2-known-gaps.md",
}


def _record_low() -> str:
    return DOCS["validation-record"].read_text(encoding="utf-8").lower()


def test_docs_exist() -> None:
    for name, p in DOCS.items():
        assert p.is_file(), name


def test_operator_validation_record_exists_and_visible() -> None:
    low = _record_low()
    assert "visible" in low


def test_ten_checklist_items_documented() -> None:
    low = _record_low()
    for term in (
        "/tasks` page",
        "test role simulation banner",
        "create task page",
        "task creation",
        "created task appears in list",
        "task detail opens",
        "submit draft works",
        "intake_review",
        "dispatch_enabled: false",
        "production_effect=true` warning",
    ):
        assert term.lower() in low, term


def test_create_task_label_documented_as_non_gap() -> None:
    low = _record_low()
    assert '"create task"' in low
    assert "not a functional gap" in low or "not a gap" in low


def test_not_classified_as_blocking_gap() -> None:
    low = _record_low()
    assert "no blocking gaps" in low
    if "partial_with_gaps" in low:
        assert "not classified as" in low


def test_step_66b2_final_pass_documented() -> None:
    low = _record_low()
    assert "step 66b.2 — pass" in low or "step 66b.2 - pass" in low


def test_no_workflow_execution_claimed() -> None:
    low = _record_low()
    assert "no new workflow was executed" in low


def test_no_external_action_claimed() -> None:
    low = _record_low()
    assert "no external action occurred" in low


def test_no_production_action_documented() -> None:
    low = _record_low()
    assert "no production action occurred" in low
    assert "production_executed_true_count=0" in low


def test_cross_doc_updates() -> None:
    assert "visible" in DOCS["ui-report"].read_text(encoding="utf-8").lower()
    assert "visible" in DOCS["operator-validation-request"].read_text(encoding="utf-8").lower()
    assert "create task" in DOCS["known-gaps"].read_text(encoding="utf-8").lower()


def test_no_secret_shapes() -> None:
    shapes = re.compile(
        r"(-----BEGIN [A-Z ]*PRIVATE KEY|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
        r"AKIA[0-9A-Z]{16}|xoxb-[A-Za-z0-9-]{10,}|sk-ant-[A-Za-z0-9_-]{20,})"
    )
    for name, p in DOCS.items():
        assert not shapes.search(p.read_text(encoding="utf-8")), name
