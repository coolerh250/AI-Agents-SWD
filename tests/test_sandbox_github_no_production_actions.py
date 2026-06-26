"""Step 59 -- the sandbox GitHub flow performs no production / merge / non-sandbox action."""

from __future__ import annotations

from pathlib import Path

from shared.sdk.sandbox_github import sandbox_github_safety_fields

ROOT = Path(__file__).resolve().parents[1]
SDK = ROOT / "shared" / "sdk" / "sandbox_github"
CLIENT = (SDK / "client.py").read_text(encoding="utf-8")
API = (ROOT / "apps" / "orchestrator" / "src" / "sandbox_github_api.py").read_text(encoding="utf-8")


def test_client_only_creates_draft_never_merges() -> None:
    # draft must be true at PR creation; never a merge / workflow / deployment call.
    assert '"draft": True' in CLIENT
    for forbidden in ("/merge", "update_branch", "merge_method", "/dispatches", "/deployments"):
        assert forbidden not in CLIENT


def test_no_production_or_argocd_or_kubectl() -> None:
    for blob in (CLIENT, API):
        for forbidden in ("kubectl", "argocd", "helm", "production_executed=true"):
            assert forbidden not in blob


def test_safety_posture_all_dangerous_off() -> None:
    f = sandbox_github_safety_fields()
    assert f["sandbox_github_production_ready"] is False
    assert f["sandbox_github_non_sandbox_repo_write_performed"] is False
    assert f["sandbox_github_token_exposed"] is False
