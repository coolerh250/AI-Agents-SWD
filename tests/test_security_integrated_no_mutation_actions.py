"""Step 54.4 -- the integrated security layer performs no mutating / external action."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Files that make up the Step 54.4 integrated layer.
LAYER = [
    ROOT / "shared" / "sdk" / "security_integrated" / "posture.py",
    ROOT / "scripts" / "generate_security_evidence_package.py",
    ROOT / "scripts" / "generate_release_risk_summary.py",
    ROOT / "scripts" / "generate_security_readiness_report.py",
]
FORBIDDEN = ("import httpx", "import requests", "import subprocess", "os.system(", "socket.")


def test_no_network_or_subprocess_in_integrated_layer() -> None:
    for path in LAYER:
        src = path.read_text(encoding="utf-8")
        for token in FORBIDDEN:
            assert token not in src, f"{path.name} uses forbidden {token}"


def test_no_github_registry_or_gate_mutation() -> None:
    for path in LAYER:
        src = path.read_text(encoding="utf-8").lower()
        for token in (
            "git push",
            "registry login",
            "docker push",
            "argocd app sync",
            "enable_gate",
        ):
            assert token not in src, f"{path.name} references {token}"
