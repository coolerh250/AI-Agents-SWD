#!/usr/bin/env python3
"""Step 54.4 -- Admin Console integrated security view verifier.

Marker: ADMIN_CONSOLE_SECURITY_INTEGRATED_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADMIN = ROOT / "apps" / "admin-console"
STATIC = ADMIN / "static" / "index.html"
PAGE = ADMIN / "src" / "pages" / "SecurityPosture.tsx"
OPS = ADMIN / "src" / "api" / "operations.ts"

SECTION = "Threat Model / Release Risk / Evidence (Step 54.4)"
ENDPOINT = "/operations/security/step54/status"
FORBIDDEN = re.compile(
    r"(generate\s*evidence|approve\s*release|enable\s*gate|create\s*pr|"
    r"sync\s*argocd|deploy|push\s*image|sign\s*image)",
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
        bad("static Security view missing the Step 54.4 integrated section")
    if ENDPOINT not in static_src:
        bad("static integrated section not wired to step54/status endpoint")
    if SECTION not in page:
        bad("React Security page missing the Step 54.4 integrated section")
    if "getSecurityStep54Status" not in ops or ENDPOINT not in ops:
        bad("operations.ts missing the step54 status getter")
    if not failures:
        ok("integrated section present (static + React), step54-status backed")

    # Buttons must not offer a mutation / approval / deploy control.
    block = static_src[static_src.find(SECTION) :] if SECTION in static_src else ""
    for label, text in (("static", block), ("react", page)):
        for m in re.finditer(r"<button[^>]*>([^<]*)</button>", text, re.IGNORECASE):
            if FORBIDDEN.search(m.group(1)):
                bad(f"{label} view has a forbidden control button: {m.group(1)}")
    if re.search(r"\.(post|put|patch|delete)\s*\(", page, re.IGNORECASE):
        bad("React Security page uses a mutation HTTP verb")
    if not [f for f in failures if "forbidden control" in f or "mutation" in f]:
        ok(
            "no generate-evidence / approve-release / enable-gate / deploy / sync button; no mutation"
        )

    print(f"\n=== Summary: {len(passes)}/{len(passes) + len(failures)} checks passed ===")
    if failures:
        print("ADMIN_CONSOLE_SECURITY_INTEGRATED_VERIFY: FAIL")
        return 1
    print("ADMIN_CONSOLE_SECURITY_INTEGRATED_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
