"""Step 56 -- non-production ArgoCD operations API (8 GET endpoints)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "apps" / "orchestrator" / "src" / "gitops_argocd_api.py"


def test_eight_get_endpoints_under_prefix() -> None:
    src = API.read_text(encoding="utf-8")
    assert 'prefix="/operations/gitops/nonprod-argocd"' in src
    gets = re.findall(r'@router\.get\("(/[^"]*)"\)', src)
    names = {g.strip("/") for g in gets}
    assert {
        "preflight",
        "install",
        "project",
        "application",
        "sync",
        "safety",
        "report",
        "readiness",
    } <= names
    assert len(gets) == 8


def test_endpoints_call_posture_views() -> None:
    src = API.read_text(encoding="utf-8")
    for view in (
        "preflight_view",
        "install_view",
        "project_view",
        "application_view",
        "sync_view",
        "safety_view",
        "report_view",
        "readiness_view",
    ):
        assert f"posture.{view}" in src
