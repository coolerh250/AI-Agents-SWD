#!/usr/bin/env python3
"""Step 58 -- operational metrics API verifier (static, read-only invariants).

Marker: OPERATIONAL_METRICS_API_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "OPERATIONAL_METRICS_API_VERIFY"
API = ROOT / "apps" / "orchestrator" / "src" / "operational_metrics_api.py"

EXPECTED = [
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
]
failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def main() -> int:
    if not API.is_file():
        bad("missing operational_metrics_api.py")
        print(f"{MARKER}: FAIL")
        return 1
    src = API.read_text(encoding="utf-8")
    if re.search(r"@router\.(post|put|patch|delete)\b", src):
        bad("metrics API defines a mutation route (must be GET-only)")
    gets = re.findall(r'@router\.get\("(/[^"]*)"\)', src)
    for name in EXPECTED:
        if not any(g.endswith("/" + name) for g in gets):
            bad(f"missing GET endpoint: {name}")
    if 'prefix="/operations/metrics"' not in src:
        bad("router prefix is not /operations/metrics")
    # No generate/refresh/sync/deploy/PR/external-send endpoints; no mutation verbs.
    for word in ("/generate", "/refresh", "/sync", "/deploy", "/pr", "/send", "/install"):
        if re.search(rf'@router\.\w+\("[^"]*{re.escape(word)}', src):
            bad(f"forbidden endpoint path fragment: {word}")
    # No direct cluster mutation / external call / arbitrary path read.
    for forbidden in ("subprocess", "kubectl", "helm ", "httpx", "requests.", "open("):
        if forbidden in src:
            bad(f"API must not use {forbidden}")
    if failures:
        print(f"{MARKER}: FAIL")
        return 1
    print(
        f"  [OK] {len(gets)} GET-only endpoints; no mutation/generate/sync; no cluster/external call"
    )
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
