"""Step 56 -- non-production ArgoCD operations API is read-only."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "apps" / "orchestrator" / "src" / "gitops_argocd_api.py"


def test_no_mutation_routes() -> None:
    src = API.read_text(encoding="utf-8")
    assert re.search(r"@router\.(post|put|patch|delete)\b", src) is None


def test_no_sync_install_delete_endpoints() -> None:
    src = API.read_text(encoding="utf-8")
    for word in ("/do-sync", "/install-", "/delete", "/rollback", "/promote", "/uninstall"):
        assert word not in src


def test_no_direct_secret_source_access() -> None:
    # The API only reads redacted posture views -- no env / file / subprocess / http.
    src = API.read_text(encoding="utf-8")
    for forbidden in ("subprocess", "os.environ", "open(", "requests."):
        assert forbidden not in src
