"""Step 54.3 -- the SBOM / container surface introduces no mutation / external action."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "apps" / "orchestrator" / "src" / "security_posture_api.py"
SDK = ROOT / "shared" / "sdk" / "container_security"
RUNNERS = [
    ROOT / "scripts" / "run_local_sbom_baseline.py",
    ROOT / "scripts" / "run_local_image_policy_scan.py",
]


def test_api_no_mutation_or_external_route() -> None:
    src = API.read_text(encoding="utf-8")
    for verb in ("@router.post", "@router.put", "@router.patch", "@router.delete"):
        assert verb not in src
    for tok in (
        "generate_sbom",
        "scan_image",
        "registry_login",
        "push_image",
        "sign_image",
        "attest_image",
    ):
        assert tok not in src


def test_sdk_no_network_subprocess() -> None:
    for p in SDK.glob("*.py"):
        s = p.read_text(encoding="utf-8")
        assert "subprocess" not in s, p.name
        assert "import httpx" not in s, p.name
        assert "import requests" not in s, p.name
        assert "urllib.request" not in s, p.name


def test_runners_no_registry_or_network_client() -> None:
    for p in RUNNERS:
        s = p.read_text(encoding="utf-8")
        assert "import httpx" not in s, p.name
        assert "import requests" not in s, p.name
        assert "urllib.request" not in s, p.name
        assert "subprocess" not in s, p.name  # SBOM/image runners do not spawn anything
