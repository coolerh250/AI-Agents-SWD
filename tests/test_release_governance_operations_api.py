"""Step 60 -- release governance API surface (endpoints + prefix)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "apps" / "orchestrator" / "src" / "release_governance_api.py"


def test_prefix_and_get_endpoints() -> None:
    src = API.read_text(encoding="utf-8")
    assert 'prefix="/operations/release"' in src
    gets = set(re.findall(r'@router\.get\("(/[^"]*)"\)', src))
    for required in (
        "/overview",
        "/policy",
        "/safety",
        "/limitations",
        "/candidates",
        "/candidates/{candidate_id}",
        "/candidates/{candidate_id}/evidence",
        "/candidates/{candidate_id}/readiness",
        "/readiness-summary",
        "/deployment-intents",
        "/deployment-intents/{intent_id}",
    ):
        assert required in gets, required


def test_only_governance_posts() -> None:
    src = API.read_text(encoding="utf-8")
    posts = set(re.findall(r'@router\.post\("(/[^"]*)"\)', src))
    assert posts == {"/candidates", "/candidates/{candidate_id}/deployment-intents"}


def test_post_uses_auth_csrf_audit_reason() -> None:
    src = API.read_text(encoding="utf-8")
    assert "_authenticate(request)" in src
    assert "_require_csrf(request" in src
    assert "_audit(" in src
    assert "reason_required" in src


def test_no_deploy_or_cluster_calls() -> None:
    # Guard against real execution paths -- not the safety field NAMES (e.g.
    # ``argocd_sync_performed``) which legitimately assert the action did NOT happen.
    src = API.read_text(encoding="utf-8")
    for forbidden in (
        "subprocess",
        "kubectl ",
        "os.system",
        "httpx",
        "docker push",
        "argocd app sync",
    ):
        assert forbidden not in src
