"""Stage 49 -- section builder produces the 14 required sections."""

from __future__ import annotations

from shared.sdk.delivery_package.checklist_builder import build_acceptance_checklist
from shared.sdk.delivery_package.models import REQUIRED_SECTION_KEYS
from shared.sdk.delivery_package.section_builder import build_sections


def _evidence() -> dict:
    return {
        "project_id": "p1",
        "workspace_id": "w1",
        "design_review_session_id": "d1",
        "project": {"title": "Todo", "project_type": "service"},
        "work_items": [{"id": "wi1"}],
        "review": {"decision": "go"},
        "blocking_findings_count": 0,
        "pilot": {"id": "pilot1", "pilot_type": "fastapi_todo_service", "status": "completed"},
        "workspace_report": {
            "files": [{"relative_path": "app/main.py", "content_hash": "abc", "size_bytes": 10}],
            "test_runs": [
                {"test_type": "pytest", "status": "passed", "tests_total": 5, "tests_passed": 5}
            ],
        },
        "qa": {"status": "passed", "tests_total": 5, "tests_passed": 5, "tests_failed": 0},
        "safety": {"status": "safe", "production_executed_count": 0},
        "acceptance_summary": {"total": 10, "satisfied": 10, "failed": 0, "pending": 0},
        "acceptance_evaluations": [
            {
                "criterion_key": "AC-001",
                "evaluation_status": "satisfied",
                "evidence_type": "test_run",
            }
        ],
    }


def test_all_14_sections_built_and_ready() -> None:
    ev = _evidence()
    checklist = build_acceptance_checklist(ev)
    sections = build_sections(ev, checklist)
    assert [s.section_key for s in sections] == list(REQUIRED_SECTION_KEYS)
    assert all(s.status == "ready" for s in sections)


def test_missing_workspace_marks_section_missing() -> None:
    ev = _evidence()
    ev["workspace_report"] = {"files": [], "test_runs": []}
    ev["workspace_id"] = None
    checklist = build_acceptance_checklist(ev)
    sections = build_sections(ev, checklist)
    by_key = {s.section_key: s for s in sections}
    assert by_key["generated_files_manifest"].status == "missing"
    assert by_key["implementation_summary"].status == "missing"


def test_section_content_has_no_raw_code() -> None:
    ev = _evidence()
    checklist = build_acceptance_checklist(ev)
    sections = build_sections(ev, checklist)
    manifest = next(s for s in sections if s.section_key == "generated_files_manifest")
    # Manifest carries paths + hashes only, never file bodies.
    for f in manifest.content["files"]:
        assert set(f) <= {"relative_path", "content_hash", "size_bytes"}
