#!/usr/bin/env python3
"""Step 57 -- Admin Console multi-project view verifier.

Marker: ADMIN_CONSOLE_MULTI_PROJECT_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADMIN = ROOT / "apps" / "admin-console"
STATIC = ADMIN / "static" / "index.html"
PAGE = ADMIN / "src" / "pages" / "MultiProjectDelivery.tsx"
OPS = ADMIN / "src" / "api" / "operations.ts"
ACTION = ADMIN / "src" / "operator" / "actionClient.ts"

SECTION = "Multi-project Delivery"
FORBIDDEN = re.compile(
    r"(production deploy|deploy to production|pull request|github pr|argocd sync|external send|"
    r"production approve|production[- ]ready toggle|promote)",
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
    action = ACTION.read_text(encoding="utf-8") if ACTION.is_file() else ""

    if SECTION not in static_src:
        bad("static view missing Multi-project Delivery section")
    if "/operations/delivery/projects" not in static_src:
        bad("static view not wired to delivery endpoint")
    if SECTION not in page:
        bad("React page missing Multi-project Delivery section")
    if "getDeliveryProjects" not in ops:
        bad("operations.ts missing delivery getters")
    for fn in ("createProject", "createWorkItem", "dispatchWorkItem"):
        if fn not in action:
            bad(f"actionClient missing write method: {fn}")
    if not failures:
        ok("multi-project section present (static + React); reads + audited writes wired")

    # No forbidden control buttons in the React page or static section. Scope the
    # static block to the renderMultiProject function (the nav label also contains
    # SECTION and would otherwise pull in unrelated sections' buttons).
    start = static_src.find("function renderMultiProject")
    end = static_src.find("async function renderProjects", start)
    block = static_src[start:end] if start >= 0 else ""
    for label, text in (("react", page), ("static", block)):
        for m in re.finditer(r"<button[^>]*>([^<]*)</button>", text, re.IGNORECASE):
            if FORBIDDEN.search(m.group(1)):
                bad(f"{label} view has a forbidden button: {m.group(1)}")
    # Writes go through the CSRF-bearing actionClient, not the GET-only client.
    if re.search(r"\bclient\.(post|put|patch|delete)\b", page):
        bad("page must not add a mutation to the read-only client")
    if not [f for f in failures if "forbidden button" in f]:
        ok("no production deploy / GitHub PR / ArgoCD sync / external send / promote button")

    print(f"\n=== Summary: {len(passes)}/{len(passes) + len(failures)} checks passed ===")
    if failures:
        print("ADMIN_CONSOLE_MULTI_PROJECT_VERIFY: FAIL")
        return 1
    print("ADMIN_CONSOLE_MULTI_PROJECT_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
