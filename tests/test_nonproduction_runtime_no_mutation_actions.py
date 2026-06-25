"""Step 55 -- the read-only runtime smoke layer performs no mutating / cluster action."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Read-only layer (SDK + API). The verifier scripts legitimately probe the cluster
# (kubectl detection) and are intentionally excluded here.
READ_ONLY_LAYER = [
    ROOT / "shared" / "sdk" / "runtime_smoke" / "posture.py",
    ROOT / "apps" / "orchestrator" / "src" / "runtime_baseline_api.py",
]
# The read-only layer must not shell out or make network calls. (kubectl/helm appear
# only as route names / descriptive comments and are not invoked here.)
FORBIDDEN = ("import subprocess", "import httpx", "import requests", "os.system(", "subprocess.run")


def test_read_only_layer_no_cluster_or_subprocess() -> None:
    for path in READ_ONLY_LAYER:
        src = path.read_text(encoding="utf-8")
        for token in FORBIDDEN:
            assert token not in src, f"{path.name} uses forbidden {token}"


def test_runner_never_targets_production() -> None:
    runner = (ROOT / "scripts" / "run_nonproduction_helm_smoke.sh").read_text(encoding="utf-8")
    # Guardrails refuse production namespaces / values and ArgoCD sync.
    assert "production substring" in runner
    assert "argocd" in runner.lower()
    assert "git push" not in runner.lower()
    assert "registry login" not in runner.lower()
