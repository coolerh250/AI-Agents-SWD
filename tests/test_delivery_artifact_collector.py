"""Stage 49 -- artifact collector links sources without raw bodies."""

from __future__ import annotations

from shared.sdk.delivery_package.artifact_collector import build_package_artifacts


def _evidence() -> dict:
    return {
        "project_id": "p1",
        "workspace_id": "w1",
        "design_review_session_id": "d1",
        "project": {"title": "Todo"},
        "work_items": [{"id": "wi1"}],
        "review": {"decision": "go"},
        "pilot": {"id": "pilot1", "status": "completed"},
        "workspace_report": {
            "files": [{"relative_path": "app/main.py", "content_hash": "h", "size_bytes": 5}],
            "test_runs": [{"test_type": "pytest", "status": "passed", "tests_passed": 5}],
        },
        "qa": {"status": "passed"},
        "safety": {"status": "safe"},
        "acceptance_summary": {"total": 10, "satisfied": 10, "failed": 0},
    }


def test_links_all_sources() -> None:
    arts = build_package_artifacts(_evidence())
    types = {a.artifact_type for a in arts}
    for expected in (
        "project_brief",
        "task_graph",
        "design_review_summary",
        "workspace_report",
        "generated_code_manifest",
        "qa_evidence_report",
        "safety_evidence_report",
        "acceptance_evaluations",
        "mini_delivery_report",
    ):
        assert expected in types


def test_manifest_carries_hashes_not_bodies() -> None:
    arts = build_package_artifacts(_evidence())
    manifest = next(a for a in arts if a.artifact_type == "generated_code_manifest")
    for f in manifest.content["files"]:
        assert set(f) <= {"relative_path", "content_hash", "size_bytes"}
