"""Unit tests for the github timeline rendering in progress.py.

Pure dict-shape assertions — no cluster required.
"""

from __future__ import annotations

import pytest

from progress import build_github_summary, build_progress  # type: ignore


def _wf_with_github(status: str, dry_run: bool, pr_url: str = "") -> dict:
    return {
        "task_id": "tt",
        "stage": "completed",
        "state": {
            "task_id": "tt",
            "workflow_id": "wf-tt",
            "execution_result": {
                "github": {
                    "status": status,
                    "dry_run": dry_run,
                    "pr_url": pr_url,
                    "branch": "ai-agents/tt",
                    "issue_url": "",
                    "checks_status": "success" if status == "success" else "unknown",
                    "event_type": ("github.pr.dry_run" if dry_run else "github.pr.created"),
                }
            },
        },
        "execution_result": {"status": "completed"},
        "approval_status": "none",
        "updated_at": "2026-05-27T03:00:00+00:00",
    }


def test_build_github_summary_returns_none_when_absent():
    workflow = {
        "task_id": "noop",
        "stage": "completed",
        "state": {"task_id": "noop", "execution_result": {}},
        "execution_result": {},
    }
    assert build_github_summary(workflow) is None


def test_build_github_summary_passes_through_fields():
    summary = build_github_summary(
        _wf_with_github("success", True, pr_url="https://github.com/owner/repo/pull/5")
    )
    assert summary is not None
    assert summary["status"] == "success"
    assert summary["dry_run"] is True
    assert summary["pr_url"] == "https://github.com/owner/repo/pull/5"
    assert summary["checks_status"] == "success"


@pytest.mark.parametrize(
    "status,dry_run,expected_phase",
    [
        ("success", True, "github.demo_pr.dry_run"),
        ("success", False, "github.demo_pr.created"),
        ("failed", True, "github.demo_pr.failed"),
        ("disabled", True, "github.demo_pr.skipped"),
    ],
)
def test_timeline_phase_per_status(status, dry_run, expected_phase):
    progress = build_progress(_wf_with_github(status, dry_run, "url-x"), executions=[])
    phases = [entry.get("phase") for entry in progress["agent_timeline"]]
    assert expected_phase in phases


def test_progress_pr_url_and_status_match_summary():
    wf = _wf_with_github("success", True, pr_url="https://github.com/owner/repo/pull/9")
    progress = build_progress(wf, executions=[])
    assert progress["pr_url"] == "https://github.com/owner/repo/pull/9"
    assert progress["github_status"] == "success"
    assert progress["github_dry_run"] is True


def test_progress_without_github_block_keeps_empty_fields():
    workflow = {
        "task_id": "noop",
        "stage": "completed",
        "state": {"task_id": "noop", "workflow_id": "wf", "execution_result": {}},
        "execution_result": {},
        "approval_status": "none",
        "updated_at": "2026-05-27T00:00:00+00:00",
    }
    progress = build_progress(workflow, executions=[])
    assert progress["pr_url"] == ""
    assert progress["github_status"] == ""
    assert progress["github_dry_run"] is None
    assert progress["github"] is None
    # No spurious github timeline entry should be added.
    phases = [entry.get("phase") for entry in progress["agent_timeline"]]
    assert not any(p and p.startswith("github.") for p in phases)
