"""Step 54.3 -- SBOM / container security operations API is strictly read-only."""

from __future__ import annotations

import re
from pathlib import Path

import security_posture_api as sp

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "apps" / "orchestrator" / "src" / "security_posture_api.py"
FORBIDDEN_TOKENS = {
    "generate",
    "scan",
    "login",
    "push",
    "pull",
    "sign",
    "attest",
    "connect",
    "upload",
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


def test_no_forbidden_sbom_image_route() -> None:
    src = SRC.read_text(encoding="utf-8")
    for ln in [x for x in src.splitlines() if x.strip().startswith("@router.")]:
        m = re.search(r"@router\.\w+\(\s*[\"']([^\"']*)", ln)
        path = m.group(1) if m else ""
        if "/sbom/" not in path and "/images/" not in path:
            continue
        tokens = set(re.split(r"[/_-]", path.lower()))
        assert not (FORBIDDEN_TOKENS & tokens), ln
