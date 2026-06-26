"""Step 57 -- multi-project write endpoints enforce auth + CSRF + reason + audit."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = (ROOT / "apps" / "orchestrator" / "src" / "multi_project_api.py").read_text(encoding="utf-8")


def test_every_write_authenticates_and_csrf() -> None:
    posts = re.findall(r"@router\.post", API)
    assert API.count("_authenticate(request)") >= len(posts)
    assert API.count("_require_csrf(request") >= len(posts)


def test_every_write_requires_reason_and_audits() -> None:
    posts = re.findall(r"@router\.post", API)
    assert API.count("reason_required") >= len(posts)
    assert "_audit(" in API


def test_reuses_operator_actions_auth() -> None:
    # Reuses the existing test-local auth/CSRF/audit (not a bespoke weaker one).
    assert "from operator_actions_api import" in API
