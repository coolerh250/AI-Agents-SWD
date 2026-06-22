"""Step 52.4 -- no identity mutation endpoints anywhere in the orchestrator."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "apps" / "orchestrator" / "src" / "identity_posture_api.py"


def test_identity_api_only_get_decorators() -> None:
    src = API.read_text(encoding="utf-8")
    verbs = re.findall(r"@router\.(get|post|put|patch|delete)", src)
    assert set(verbs) == {"get"}


def test_no_identity_login_or_callback_route_in_app() -> None:
    # Scan all orchestrator route decorators for an identity auth-flow path.
    src_dir = ROOT / "apps" / "orchestrator" / "src"
    pat = re.compile(
        r"@(router|app)\.(get|post|put|patch|delete)\(\s*[\"'][^\"']*"
        r"(identity/(login|callback|authorize|token|logout|connect)|oidc/callback)",
        re.IGNORECASE,
    )
    for p in src_dir.glob("*.py"):
        assert not pat.search(p.read_text(encoding="utf-8")), p.name


def test_no_break_glass_activation_route_in_app_or_sdk() -> None:
    # A read-only GET break-glass STATUS endpoint is allowed (it exposes the
    # disabled state); only an activation / mutation break-glass route is banned.
    for base in (ROOT / "apps" / "orchestrator" / "src", ROOT / "shared" / "sdk"):
        for p in base.rglob("*.py"):
            if "__pycache__" in p.parts:
                continue
            for line in p.read_text(encoding="utf-8").splitlines():
                low = line.lower()
                if "break" not in low or "glass" not in low:
                    continue
                is_route = "@router" in low or "@app." in low
                is_mutation = any(v in low for v in (".post", ".put", ".patch", ".delete"))
                is_activation = any(w in low for w in ("activate", "enable", "login"))
                if is_route and (is_mutation or is_activation):
                    raise AssertionError(f"break-glass activation route in {p}: {line.strip()}")
