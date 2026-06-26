"""Step 58 -- operational metrics API is read-only with no side effects."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "apps" / "orchestrator" / "src" / "operational_metrics_api.py"


def test_no_mutation_routes() -> None:
    src = API.read_text(encoding="utf-8")
    assert re.search(r"@router\.(post|put|patch|delete)\b", src) is None


def test_no_generate_refresh_sync_deploy_endpoints() -> None:
    src = API.read_text(encoding="utf-8")
    for frag in ("/generate", "/refresh", "/sync", "/deploy", "/pr", "/send", "/install"):
        assert not re.search(rf'@router\.\w+\("[^"]*{re.escape(frag)}', src)


def test_no_cluster_or_external_call() -> None:
    src = API.read_text(encoding="utf-8")
    for forbidden in ("subprocess", "kubectl", "httpx", "requests.", "open("):
        assert forbidden not in src
