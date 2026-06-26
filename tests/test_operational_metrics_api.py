"""Step 58 -- operational metrics API (14 GET endpoints)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "apps" / "orchestrator" / "src" / "operational_metrics_api.py"


def test_fourteen_get_endpoints() -> None:
    src = API.read_text(encoding="utf-8")
    assert 'prefix="/operations/metrics"' in src
    gets = re.findall(r'@router\.get\("(/[^"]*)"\)', src)
    names = {g.strip("/") for g in gets}
    assert {
        "overview",
        "delivery",
        "work-items",
        "dispatch",
        "agents",
        "workflows",
        "runtime",
        "gitops",
        "security",
        "approval",
        "audit",
        "safety",
        "freshness",
        "snapshot",
    } <= names
    assert len(gets) == 14
