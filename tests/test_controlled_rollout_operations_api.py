"""Step 63A -- controlled rollout API surface (endpoints + prefix + no action)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "apps" / "orchestrator" / "src" / "controlled_rollout_review_api.py"


def test_prefix_and_get_endpoints() -> None:
    src = API.read_text(encoding="utf-8")
    assert 'prefix="/operations/readiness/controlled-rollout"' in src
    gets = set(re.findall(r'@router\.get\("(/[^"]*)"\)', src))
    for required in (
        "/policy",
        "/criteria",
        "/production-target",
        "/credentials",
        "/gitops",
        "/approval-channel",
        "/rollback-dr",
        "/scope",
        "/risks",
        "/decision-package",
        "/recommendation",
        "/safety",
    ):
        assert required in gets, required


def test_only_operator_review_request_post() -> None:
    src = API.read_text(encoding="utf-8")
    posts = set(re.findall(r'@router\.post\("(/[^"]*)"\)', src))
    assert posts == {"/operator-review-requests"}


def test_no_production_action_endpoint() -> None:
    src = API.read_text(encoding="utf-8")
    routes = re.findall(r'@router\.(?:get|post)\("(/[^"]*)"\)', src)
    for r in routes:
        for forbidden in (
            "/rollout",
            "/deploy",
            "/sync",
            "/approve",
            "/release",
            "/restore",
            "/failover",
            "/merge",
            "/image-push",
        ):
            assert r != forbidden, f"forbidden endpoint present: {r}"


def test_post_uses_auth_csrf_audit_reason() -> None:
    src = API.read_text(encoding="utf-8")
    assert "_authenticate(request)" in src
    assert "_require_csrf(request" in src
    assert "_audit(" in src
    assert "reason_required" in src


def test_no_real_execution_paths() -> None:
    src = API.read_text(encoding="utf-8")
    for forbidden in ("subprocess", "kubectl ", "os.system", "docker push", "argocd app sync"):
        assert forbidden not in src
