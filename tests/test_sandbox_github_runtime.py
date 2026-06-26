"""Step 59 -- sandbox draft PR runtime (client end-to-end audit + result invariants)."""

from __future__ import annotations

from shared.sdk.sandbox_github import SandboxGitHubClient
from shared.sdk.sandbox_github.audit import EVENTS


def test_dry_run_audit_sequence_and_invariants() -> None:
    client = SandboxGitHubClient(actor="tester", role="operator", reason="runtime test")
    res = client.request_draft_pr(
        repository_key="ai-agents-sandbox",
        project_id="pid",
        project_key="DEMO",
        work_item_id="wid",
        work_item_key="WI-0001",
        work_item_title="Add a thing",
        correlation_id="corr12345678",
        requested_mode="dry_run",
    )
    assert res.status == "planned"
    # every audit event is a known type and carries production_executed=false + no token.
    for ev in res.audit_events:
        assert ev["event_type"] in EVENTS
        assert ev["production_executed"] is False
        assert "token" not in ev or ev["token"] == "[redacted]"
    d = res.to_dict()
    assert d["merge_performed"] is False
    assert d["ready_for_review_performed"] is False
    assert d["workflow_dispatch_performed"] is False
    assert d["non_sandbox_repo_write_performed"] is False


def test_blocked_request_records_block_event() -> None:
    client = SandboxGitHubClient(actor="tester", role="operator", reason="runtime test")
    res = client.request_draft_pr(
        repository_key="not-allowed",
        project_id="pid",
        project_key="DEMO",
        work_item_id="wid",
        work_item_key="WI-0001",
        work_item_title="x",
        correlation_id="corr12345678",
    )
    assert res.status == "blocked"
    assert any(e["event_type"] == "sandbox_github_draft_pr_blocked" for e in res.audit_events)
