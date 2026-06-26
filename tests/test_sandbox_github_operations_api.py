"""Step 59 -- sandbox GitHub API surface (endpoints + prefix)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "apps" / "orchestrator" / "src" / "sandbox_github_api.py"


def test_prefix_and_get_endpoints() -> None:
    src = API.read_text(encoding="utf-8")
    assert 'prefix="/operations/github"' in src
    gets = set(re.findall(r'@router\.get\("(/[^"]*)"\)', src))
    for required in (
        "/sandbox-draft-pr/policy",
        "/sandbox-draft-pr/allowlist",
        "/sandbox-draft-pr/safety",
        "/sandbox-draft-pr/readiness",
        "/sandbox-draft-pr/requests",
        "/sandbox-draft-pr/{request_id}",
        "/sandbox-draft-pr",
    ):
        assert required in gets, required


def test_single_controlled_post() -> None:
    src = API.read_text(encoding="utf-8")
    posts = re.findall(r'@router\.post\("(/[^"]*)"\)', src)
    # exactly one write endpoint: the controlled sandbox draft PR request
    assert posts == ["/sandbox-draft-pr"]


def test_post_uses_auth_csrf_audit() -> None:
    src = API.read_text(encoding="utf-8")
    assert "_authenticate(request)" in src
    assert "_require_csrf(request" in src
    assert "_audit(" in src
    assert "reason_required" in src
