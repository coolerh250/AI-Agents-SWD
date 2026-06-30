"""Step 61 -- backup / restore / DR API surface (endpoints + prefix + no execution)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "apps" / "orchestrator" / "src" / "backup_restore_dr_api.py"


def test_prefix_and_get_endpoints() -> None:
    src = API.read_text(encoding="utf-8")
    assert 'prefix="/operations/dr"' in src
    gets = set(re.findall(r'@router\.get\("(/[^"]*)"\)', src))
    for required in (
        "/overview",
        "/policy",
        "/targets",
        "/artifacts",
        "/inventory",
        "/safety",
        "/limitations",
        "/cleanup-review",
        "/restore-plans",
        "/restore-validations",
        "/evidence",
        "/readiness",
    ):
        assert required in gets, required


def test_only_review_and_plan_posts() -> None:
    src = API.read_text(encoding="utf-8")
    posts = set(re.findall(r'@router\.post\("(/[^"]*)"\)', src))
    assert posts == {"/cleanup-reviews", "/restore-plans"}


def test_no_execute_failover_teardown_endpoint() -> None:
    src = API.read_text(encoding="utf-8")
    routes = re.findall(r'@router\.(?:get|post)\("(/[^"]*)"\)', src)
    for r in routes:
        assert "execute" not in r
        assert "failover" not in r
        assert "teardown" not in r
        assert "cloud-upload" not in r


def test_post_uses_auth_csrf_audit_reason() -> None:
    src = API.read_text(encoding="utf-8")
    assert "_authenticate(request)" in src
    assert "_require_csrf(request" in src
    assert "_audit(" in src
    assert "reason_required" in src


def test_no_real_execution_paths() -> None:
    # Guard against real execution -- not the safety field NAMES (e.g. argocd_sync_performed)
    # which legitimately assert the action did NOT happen.
    src = API.read_text(encoding="utf-8")
    for forbidden in (
        "subprocess",
        "kubectl ",
        "os.system",
        "shutil.rmtree",
        "docker push",
        "argocd app sync",
        "os.remove",
    ):
        assert forbidden not in src
