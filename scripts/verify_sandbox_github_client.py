#!/usr/bin/env python3
"""Step 59 -- sandbox GitHub client verifier (SDK, no network).

Marker: SANDBOX_GITHUB_CLIENT_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
MARKER = "SANDBOX_GITHUB_CLIENT_VERIFY"

failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def main() -> int:
    from shared.sdk.sandbox_github import SandboxGitHubClient
    from shared.sdk.sandbox_github.client import SandboxGitHubClient as C

    # The client must NOT expose merge / ready-for-review / workflow-dispatch methods.
    forbidden_methods = [
        a
        for a in dir(C)
        if any(
            t in a.lower() for t in ("merge", "ready_for_review", "workflow", "dispatch_workflow")
        )
    ]
    if forbidden_methods:
        bad(f"client exposes forbidden method(s): {forbidden_methods}")

    client = SandboxGitHubClient(actor="verifier", role="operator", reason="client verify")

    # Allowlisted repo, dry_run -> planned, with a sandbox branch and audit events.
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
    if res.status != "planned":
        bad(f"dry_run on allowlisted repo must be planned (got {res.status}: {res.reason})")
    if not (res.branch_name or "").startswith("sandbox/ai-agents/"):
        bad(f"plan branch must be a sandbox branch: {res.branch_name}")
    if not any(e["event_type"] == "sandbox_github_draft_pr_requested" for e in res.audit_events):
        bad("missing requested audit event")
    if res.to_dict().get("production_executed") is not False:
        bad("result production_executed must be false")

    # Unknown repo -> blocked.
    res2 = client.request_draft_pr(
        repository_key="not-a-repo",
        project_id="p",
        project_key="X",
        work_item_id="w",
        work_item_key="WI-1",
        work_item_title="t",
        correlation_id="c1234",
    )
    if res2.status != "blocked" or res2.reason != "repository_not_allowlisted":
        bad(f"unknown repo must be blocked: {res2.status}/{res2.reason}")

    # production_effect -> blocked (never a PR).
    res3 = client.request_draft_pr(
        repository_key="ai-agents-sandbox",
        project_id="p",
        project_key="X",
        work_item_id="w",
        work_item_key="WI-1",
        work_item_title="t",
        correlation_id="c1234",
        production_effect=True,
    )
    if res3.status != "blocked" or res3.reason != "production_effect_requires_approval":
        bad(f"production_effect must be blocked: {res3.status}/{res3.reason}")

    # live_sandbox without enablement/credential -> blocked, never created.
    res4 = client.request_draft_pr(
        repository_key="ai-agents-sandbox",
        project_id="p",
        project_key="X",
        work_item_id="w",
        work_item_key="WI-1",
        work_item_title="t",
        correlation_id="c1234",
        requested_mode="live_sandbox",
    )
    if res4.status == "created":
        bad("live_sandbox must NOT create without explicit enablement + credential")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1
    print("  [OK] client: dry_run plan ok; unknown/production/live blocked; no merge methods")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
