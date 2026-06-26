#!/usr/bin/env python3
"""Step 56 -- Admin Console non-production ArgoCD view verifier.

Marker: ADMIN_CONSOLE_NONPROD_ARGOCD_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADMIN = ROOT / "apps" / "admin-console"
STATIC = ADMIN / "static" / "index.html"
PAGE = ADMIN / "src" / "pages" / "RuntimeBaseline.tsx"
OPS = ADMIN / "src" / "api" / "operations.ts"

SECTION = "Non-production ArgoCD Manual Sync (Step 56)"
ENDPOINT = "/operations/gitops/nonprod-argocd/"
FORBIDDEN = re.compile(
    r"(sync|install|delete|rollback|promote|prune|self.?heal|uninstall)",
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
        bad("static Runtime view missing the Step 56 ArgoCD section")
    if ENDPOINT not in static_src:
        bad("static ArgoCD section not wired to a nonprod-argocd endpoint")
    if SECTION not in page:
        bad("React Runtime page missing the Step 56 ArgoCD section")
    if "getNonprodArgocdSync" not in ops or ENDPOINT not in ops:
        bad("operations.ts missing the nonprod ArgoCD getters")
    if not failures:
        ok("Step 56 ArgoCD section present (static + React), endpoint-backed")

    # No mutation buttons in either view (any button label mentioning a mutation).
    for label, text in (("static", static_src), ("react", page)):
        for m in re.finditer(r"<button[^>]*>([^<]*)</button>", text, re.IGNORECASE):
            if FORBIDDEN.search(m.group(1)):
                bad(f"{label} view has a forbidden control button: {m.group(1)}")
    if re.search(r"\.(post|put|patch|delete)\s*\(", page, re.IGNORECASE):
        bad("React Runtime page uses a mutation HTTP verb")
    if not [f for f in failures if "forbidden control" in f or "mutation" in f]:
        ok("no sync / install / delete / rollback / promote button; no mutation verb")

    print(f"\n=== Summary: {len(passes)}/{len(passes) + len(failures)} checks passed ===")
    if failures:
        print("ADMIN_CONSOLE_NONPROD_ARGOCD_VERIFY: FAIL")
        return 1
    print("ADMIN_CONSOLE_NONPROD_ARGOCD_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
