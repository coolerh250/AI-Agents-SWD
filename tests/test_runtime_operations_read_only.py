"""Step 51.4 -- runtime operations API is strictly read-only."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "apps" / "orchestrator" / "src" / "runtime_baseline_api.py"


def _src() -> str:
    return API.read_text(encoding="utf-8")


def test_no_mutation_routes() -> None:
    src = _src()
    for verb in ("@router.post", "@router.put", "@router.patch", "@router.delete"):
        assert verb not in src, verb


def test_no_deploy_sync_apply_install_routes() -> None:
    # inspect only @router decorator lines (route paths), not docstrings/comments
    routes = [ln for ln in _src().splitlines() if ln.strip().startswith("@router.")]
    for ln in routes:
        for word in ("deploy", "sync", "apply", "install"):
            assert word not in ln.lower(), ln


def test_no_subprocess_or_kubectl() -> None:
    src = _src()
    assert "subprocess" not in src
    assert "kubectl" not in src
