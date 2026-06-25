#!/usr/bin/env python3
"""Step 55 -- Admin Console non-production runtime smoke view verifier.

Marker: ADMIN_CONSOLE_NONPROD_RUNTIME_SMOKE_VERIFY: PASS | FAIL
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

SECTION = "Non-production Runtime Smoke (Step 55)"
ENDPOINT = "/operations/runtime/nonprod-smoke/readiness"
FORBIDDEN = re.compile(
    r"(deploy|helm\s*install|cleanup|kubectl\s*exec|argocd\s*sync|uninstall|create\s*namespace)",
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
        bad("static Runtime view missing the Step 55 smoke section")
    if ENDPOINT not in static_src:
        bad("static smoke section not wired to the readiness endpoint")
    if SECTION not in page:
        bad("React Runtime page missing the Step 55 smoke section")
    if "getNonprodSmokeReadiness" not in ops or ENDPOINT not in ops:
        bad("operations.ts missing the nonprod smoke readiness getter")
    if not failures:
        ok("Step 55 smoke section present (static + React), readiness-endpoint backed")

    block = static_src[static_src.find(SECTION) :] if SECTION in static_src else ""
    for label, text in (("static", block), ("react", page)):
        for m in re.finditer(r"<button[^>]*>([^<]*)</button>", text, re.IGNORECASE):
            if FORBIDDEN.search(m.group(1)):
                bad(f"{label} view has a forbidden control button: {m.group(1)}")
    if re.search(r"\.(post|put|patch|delete)\s*\(", page, re.IGNORECASE):
        bad("React Runtime page uses a mutation HTTP verb")
    if not [f for f in failures if "forbidden control" in f or "mutation" in f]:
        ok("no deploy / helm-install / cleanup / exec / sync button; no mutation")

    print(f"\n=== Summary: {len(passes)}/{len(passes) + len(failures)} checks passed ===")
    if failures:
        print("ADMIN_CONSOLE_NONPROD_RUNTIME_SMOKE_VERIFY: FAIL")
        return 1
    print("ADMIN_CONSOLE_NONPROD_RUNTIME_SMOKE_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
