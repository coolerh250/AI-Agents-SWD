"""Step 54.2 -- the scan surface introduces no mutation / external action."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "apps" / "orchestrator" / "src" / "security_posture_api.py"
SDK = ROOT / "shared" / "sdk" / "security_findings"
RUNNERS = [
    ROOT / "scripts" / "run_local_secret_scan.py",
    ROOT / "scripts" / "run_local_sast_scan.py",
    ROOT / "scripts" / "run_local_dependency_scan.py",
]


def test_api_has_no_mutation_decorators() -> None:
    src = API.read_text(encoding="utf-8")
    for verb in ("@router.post", "@router.put", "@router.patch", "@router.delete"):
        assert verb not in src
    for tok in ("run_scan", "connect_scanner", "upload_source", "push_image", "create_pr"):
        assert tok not in src


def test_sdk_no_network_or_subprocess() -> None:
    for p in SDK.glob("*.py"):
        src = p.read_text(encoding="utf-8")
        assert "subprocess" not in src, p.name
        assert "import httpx" not in src, p.name
        assert "import requests" not in src, p.name
        assert "urllib.request" not in src, p.name


def test_runners_do_not_upload_or_use_network() -> None:
    # the runners may use subprocess to spawn *local* sibling runners, but must not
    # import an HTTP client / requests / urllib for network calls.
    for p in RUNNERS:
        src = p.read_text(encoding="utf-8")
        assert "import httpx" not in src, p.name
        assert "import requests" not in src, p.name
        assert "urllib.request" not in src, p.name
        assert "upload" not in src.lower() or "no source upload" in src.lower()
