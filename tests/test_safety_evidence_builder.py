"""Stage 48 -- safety evidence builder."""

from __future__ import annotations

from shared.sdk.mini_delivery_pilot.safety_evidence_builder import build_safety_report

_SAFE_WS = {
    "production_executed": False,
    "github_write_performed": False,
    "repo_write_performed": False,
    "deployment_performed": False,
    "real_llm_used": False,
}


def test_safe_when_all_flags_false() -> None:
    s = build_safety_report(workspace_result=_SAFE_WS)
    assert s.status == "safe"
    assert s.production_executed_count == 0
    assert s.pr_created is False
    assert s.chain_of_thought_persisted is False
    assert s.findings == []


def test_blocked_when_github_write() -> None:
    ws = {**_SAFE_WS, "github_write_performed": True}
    s = build_safety_report(workspace_result=ws)
    assert s.status == "blocked"
    assert s.github_write_performed is True
    assert any(f["flag"] == "github_write_performed" for f in s.findings)


def test_blocked_when_deploy() -> None:
    s = build_safety_report(workspace_result={**_SAFE_WS, "deployment_performed": True})
    assert s.status == "blocked"


def test_secret_leak_detected_blocks() -> None:
    s = build_safety_report(
        workspace_result=_SAFE_WS,
        report_text_blobs=["token ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ012345"],
    )
    assert s.secret_leak_detected is True
    assert s.status == "blocked"
