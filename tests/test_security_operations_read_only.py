"""Step 54.1 -- security operations API is strictly read-only."""

from __future__ import annotations

import re
from pathlib import Path

import security_posture_api as sp

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "apps" / "orchestrator" / "src" / "security_posture_api.py"

# mutating verbs that must never appear as a route-path token ('scan' is a
# legitimate read-only noun: scan-policies / dependency-scan / secret-scan).
FORBIDDEN_TOKENS = {
    "run",
    "connect",
    "upload",
    "configure",
    "push",
    "create",
    "toggle",
    "login",
    "write",
    "delete",
    "sync",
    "deploy",
    "apply",
    "install",
    "provider",
    "reveal",
}


def test_all_routes_get_only() -> None:
    for route in sp.router.routes:
        assert set(getattr(route, "methods", None) or set()) <= {"GET", "HEAD"}, getattr(
            route, "path", "?"
        )


def test_no_mutation_verb_in_source() -> None:
    src = SRC.read_text(encoding="utf-8")
    for verb in ("@router.post", "@router.put", "@router.patch", "@router.delete"):
        assert verb not in src


def test_no_forbidden_operation_route() -> None:
    src = SRC.read_text(encoding="utf-8")
    route_lines = [ln for ln in src.splitlines() if ln.strip().startswith("@router.")]
    for ln in route_lines:
        m = re.search(r"@router\.\w+\(\s*[\"']([^\"']*)", ln)
        tokens = set(re.split(r"[/_-]", (m.group(1) if m else "").lower()))
        assert not (FORBIDDEN_TOKENS & tokens), ln


def test_no_scanner_or_network_client() -> None:
    src = SRC.read_text(encoding="utf-8")
    assert "subprocess" not in src
    assert "httpx" not in src
    assert "requests" not in src
