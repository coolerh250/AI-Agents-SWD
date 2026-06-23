"""Step 54.1 -- the security surface introduces no mutation/runtime-write action."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "apps" / "orchestrator" / "src" / "security_posture_api.py"
SDK = ROOT / "shared" / "sdk" / "security_foundation"


def test_api_has_no_mutation_decorators() -> None:
    src = API.read_text(encoding="utf-8")
    for verb in ("@router.post", "@router.put", "@router.patch", "@router.delete"):
        assert verb not in src


def test_sdk_does_not_run_scanners_or_network() -> None:
    # Precise code-level guard: no subprocess / HTTP client imported or used.
    # (Descriptive prose in docstrings naming what the SDK never does is fine.)
    for p in SDK.glob("*.py"):
        src = p.read_text(encoding="utf-8")
        assert "subprocess" not in src, p.name
        assert "import httpx" not in src, p.name
        assert "import requests" not in src, p.name
        assert "os.system" not in src, p.name


def test_no_run_scan_helper_in_orchestrator_security() -> None:
    src = API.read_text(encoding="utf-8")
    for token in ("run_scan", "push_image", "create_pr", "connect_scanner", "upload_source"):
        assert token not in src
