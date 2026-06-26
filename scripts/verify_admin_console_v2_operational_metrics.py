#!/usr/bin/env python3
"""Step 58 -- Admin Console v2 operational metrics view verifier.

Marker: ADMIN_CONSOLE_V2_OPERATIONAL_METRICS_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADMIN = ROOT / "apps" / "admin-console"
STATIC = ADMIN / "static" / "index.html"
PAGE = ADMIN / "src" / "pages" / "OperationalMetrics.tsx"
OPS = ADMIN / "src" / "api" / "operations.ts"

SECTION = "Operational Metrics (Admin Console v2, Step 58)"
FORBIDDEN = re.compile(
    r"(deploy|argocd\s*sync|create\s*pr|pull\s*request|external\s*send|production\s*approve|"
    r"production\s*ready|connector)",
    re.IGNORECASE,
)
failures: list[str] = []
passes: list[str] = []


def ok(m: str) -> None:
    passes.append(m)
    print(f"  [PASS] {m}")


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def main() -> int:
    static_src = STATIC.read_text(encoding="utf-8")
    page = PAGE.read_text(encoding="utf-8") if PAGE.is_file() else ""
    ops = OPS.read_text(encoding="utf-8") if OPS.is_file() else ""

    if SECTION not in static_src:
        bad("static view missing the Step 58 metrics section")
    if SECTION not in page:
        bad("React page missing the Step 58 metrics section")
    if "getMetricsOverview" not in ops or "/operations/metrics/" not in ops:
        bad("operations.ts missing metrics getters")
    if not failures:
        ok("Step 58 metrics dashboard present (static + React), endpoint-backed")

    # No mutation buttons in either view.
    for label, text in (("static", static_src), ("react", page)):
        block = text[text.find(SECTION) :] if SECTION in text else ""
        for m in re.finditer(r"<button[^>]*>([^<]*)</button>", block, re.IGNORECASE):
            if FORBIDDEN.search(m.group(1)):
                bad(f"{label} view has a forbidden control button: {m.group(1)}")
    if re.search(r"\.(post|put|patch|delete)\s*\(", page, re.IGNORECASE):
        bad("React metrics page uses a mutation HTTP verb")
    if not [f for f in failures if "forbidden control" in f or "mutation" in f]:
        ok("no deploy/sync/PR/external send/production approve/production ready/connector control")

    print(f"\n=== Summary: {len(passes)}/{len(passes) + len(failures)} checks passed ===")
    if failures:
        print("ADMIN_CONSOLE_V2_OPERATIONAL_METRICS_VERIFY: FAIL")
        return 1
    print("ADMIN_CONSOLE_V2_OPERATIONAL_METRICS_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
