"""Step 55 -- non-production runtime smoke API is read-only."""

from __future__ import annotations

from pathlib import Path

import runtime_baseline_api as m

ROOT = Path(__file__).resolve().parents[1]
API_SRC = ROOT / "apps" / "orchestrator" / "src" / "runtime_baseline_api.py"
FORBIDDEN_TOKENS = {"deploy", "install", "cleanup", "exec", "sync", "apply", "uninstall", "delete"}


def test_router_get_only() -> None:
    methods: set[str] = set()
    for r in m.router.routes:
        methods |= set(getattr(r, "methods", set()))
    assert methods <= {"GET", "HEAD"}


def test_no_mutation_decorators() -> None:
    src = API_SRC.read_text(encoding="utf-8")
    for verb in ("@router.post", "@router.put", "@router.patch", "@router.delete"):
        assert verb not in src


def test_nonprod_smoke_routes_have_no_forbidden_tokens() -> None:
    for r in m.router.routes:
        path = getattr(r, "path", "")
        if "nonprod-smoke" not in path:
            continue
        tokens = set(path.lower().replace("-", "/").replace("_", "/").split("/"))
        assert not (FORBIDDEN_TOKENS & tokens), path
