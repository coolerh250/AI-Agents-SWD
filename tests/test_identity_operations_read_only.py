"""Step 52.4 -- identity operations API is strictly read-only."""

from __future__ import annotations

from pathlib import Path

import identity_posture_api as ip

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "apps" / "orchestrator" / "src" / "identity_posture_api.py"


def test_all_routes_get_only() -> None:
    for route in ip.router.routes:
        assert set(getattr(route, "methods", None) or set()) <= {"GET", "HEAD"}, getattr(
            route, "path", "?"
        )


def test_no_mutation_verb_in_source() -> None:
    src = SRC.read_text(encoding="utf-8")
    for verb in ("@router.post", "@router.put", "@router.patch", "@router.delete"):
        assert verb not in src


def test_no_auth_flow_or_mutation_route_decorators() -> None:
    src = SRC.read_text(encoding="utf-8")
    route_lines = [ln for ln in src.splitlines() if ln.strip().startswith("@router.")]
    for ln in route_lines:
        low = ln.lower()
        for word in (
            "login",
            "callback",
            "authorize",
            "token",
            "logout",
            "connect",
            "apply",
            "activate",
        ):
            assert word not in low, ln


def test_no_http_client_or_subprocess() -> None:
    src = SRC.read_text(encoding="utf-8")
    assert "subprocess" not in src
    assert "import requests" not in src and "import httpx" not in src
