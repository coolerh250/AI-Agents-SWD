#!/usr/bin/env python3
"""Step 62 -- Admin Console production readiness gate view verifier.

Marker: ADMIN_CONSOLE_PRODUCTION_READINESS_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADMIN = ROOT / "apps" / "admin-console"
STATIC = ADMIN / "static" / "index.html"
PAGE = ADMIN / "src" / "pages" / "ProductionReadiness.tsx"
OPS = ADMIN / "src" / "api" / "operations.ts"

SECTION = "Production Deployment Readiness Gate (Step 62)"
FORBIDDEN_BTN = re.compile(
    r"(production\s*deploy|deploy\s*now|argocd\s*sync|github\s*merge|merge\b|image\s*push|"
    r"restore|failover|production\s*approve|production\s*ready)",
    re.IGNORECASE,
)
failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def main() -> int:
    static_src = STATIC.read_text(encoding="utf-8")
    page = PAGE.read_text(encoding="utf-8") if PAGE.is_file() else ""
    ops = OPS.read_text(encoding="utf-8") if OPS.is_file() else ""

    if SECTION not in static_src:
        bad("static view missing the Step 62 production readiness section")
    if SECTION not in page:
        bad("React page missing the Step 62 production readiness section")
    if "getReadinessPolicy" not in ops or "/operations/readiness/" not in ops:
        bad("operations.ts missing readiness getters")

    for label, text in (("static", static_src), ("react", page)):
        block = text[text.find(SECTION) :] if SECTION in text else ""
        for mtch in re.finditer(r"<button[^>]*>([^<]*)</button>", block, re.IGNORECASE):
            if FORBIDDEN_BTN.search(mtch.group(1)):
                bad(f"{label} view has a forbidden control button: {mtch.group(1)}")
        if re.search(r"<input[^>]*type=[\"']checkbox[\"'][^>]*production", block, re.IGNORECASE):
            bad(f"{label} view exposes a production-ready toggle")

    if re.search(r"\.(post|put|patch|delete)\s*\(", page, re.IGNORECASE):
        bad("React production readiness page uses a mutation HTTP verb")

    if failures:
        print("ADMIN_CONSOLE_PRODUCTION_READINESS_VERIFY: FAIL")
        return 1
    print(
        "  [OK] production readiness view present (static + React); "
        "no deploy/sync/merge/restore/failover/prod control"
    )
    print("ADMIN_CONSOLE_PRODUCTION_READINESS_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
