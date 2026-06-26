"""Step 59 -- sandbox GitHub API exposes no forbidden routes / side effects."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "apps" / "orchestrator" / "src" / "sandbox_github_api.py"


def test_no_merge_review_workflow_routes() -> None:
    src = API.read_text(encoding="utf-8")
    routes = re.findall(r'@router\.\w+\("([^"]*)"\)', src)
    for r in routes:
        assert not re.search(r"(merge|ready-for-review|workflow|dispatch)", r, re.IGNORECASE)


def test_no_put_patch_delete() -> None:
    src = API.read_text(encoding="utf-8")
    assert re.search(r"@router\.(put|patch|delete)\b", src) is None


def test_no_cluster_or_subprocess() -> None:
    src = API.read_text(encoding="utf-8")
    for forbidden in ("subprocess", "kubectl", "helm", "argocd"):
        assert forbidden not in src
