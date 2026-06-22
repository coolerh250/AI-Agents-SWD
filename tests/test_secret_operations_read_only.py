"""Step 53 -- secret operations API is strictly read-only."""

from __future__ import annotations

from pathlib import Path

import secret_posture_api as sp

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "apps" / "orchestrator" / "src" / "secret_posture_api.py"


def test_all_routes_get_only() -> None:
    for route in sp.router.routes:
        assert set(getattr(route, "methods", None) or set()) <= {"GET", "HEAD"}, getattr(
            route, "path", "?"
        )


def test_no_mutation_verb_in_source() -> None:
    src = SRC.read_text(encoding="utf-8")
    for verb in ("@router.post", "@router.put", "@router.patch", "@router.delete"):
        assert verb not in src


def test_no_value_or_mutation_route_decorators() -> None:
    import re

    src = SRC.read_text(encoding="utf-8")
    route_lines = [ln for ln in src.splitlines() if ln.strip().startswith("@router.")]
    forbidden = {"read", "value", "write", "rotate", "configure", "provider", "reveal"}
    for ln in route_lines:
        m = re.search(r"@router\.\w+\(\s*[\"']([^\"']*)", ln)
        path = m.group(1) if m else ""
        tokens = set(re.split(r"[/_-]", path.lower()))
        assert not (forbidden & tokens), ln  # 'readiness'/'rotation' are not 'read'/'rotate'


def test_no_store_client_or_subprocess() -> None:
    src = SRC.read_text(encoding="utf-8")
    assert "subprocess" not in src
    assert "hvac" not in src
