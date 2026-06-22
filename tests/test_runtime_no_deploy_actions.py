"""Step 51.4 -- no deploy/sync/apply action anywhere in the runtime surface."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "apps" / "orchestrator" / "src" / "runtime_baseline_api.py"
MAIN = ROOT / "apps" / "orchestrator" / "src" / "main.py"


def test_runtime_api_has_no_write_route() -> None:
    src = API.read_text(encoding="utf-8")
    for verb in ("post", "put", "patch", "delete"):
        assert f"@router.{verb}" not in src


def test_runtime_api_no_cluster_mutation_words() -> None:
    src = API.read_text(encoding="utf-8")
    for w in ("kubectl", "helm install", "helm upgrade", "argocd app sync", "subprocess"):
        assert w not in src, w


def test_runtime_router_registered_once() -> None:
    main_src = MAIN.read_text(encoding="utf-8")
    assert main_src.count("runtime_baseline_router") >= 2  # import + include
    assert "app.include_router(runtime_baseline_router)" in main_src
