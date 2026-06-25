"""Step 54.4 -- integrated security operations API is read-only."""

from __future__ import annotations

from pathlib import Path

import security_posture_api as sp

ROOT = Path(__file__).resolve().parents[1]
API_SRC = ROOT / "apps" / "orchestrator" / "src" / "security_posture_api.py"
OWN = ("/threat-model/", "/release-risk/", "/evidence/", "/readiness/", "/step54/")
FORBIDDEN_TOKENS = {
    "generate",
    "approve",
    "deploy",
    "gate",
    "sync",
    "enable",
    "push",
    "login",
    "sign",
    "attest",
    "upload",
    "connect",
}


def test_router_get_only() -> None:
    methods: set[str] = set()
    for r in sp.router.routes:
        methods |= set(getattr(r, "methods", set()))
    assert methods <= {"GET", "HEAD"}


def test_no_mutation_decorators_in_source() -> None:
    src = API_SRC.read_text(encoding="utf-8")
    for verb in ("@router.post", "@router.put", "@router.patch", "@router.delete"):
        assert verb not in src


def test_integrated_routes_have_no_forbidden_tokens() -> None:
    for r in sp.router.routes:
        path = getattr(r, "path", "")
        if not any(mark in path for mark in OWN):
            continue
        tokens = set(path.lower().replace("-", "/").replace("_", "/").split("/"))
        assert not (FORBIDDEN_TOKENS & tokens), f"forbidden token in {path}"
