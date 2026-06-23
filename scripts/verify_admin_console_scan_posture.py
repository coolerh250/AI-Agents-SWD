#!/usr/bin/env python3
"""Step 54.2 -- Admin Console scan posture view verifier.

Asserts the Admin Console Security view renders a read-only scan baseline section
(static + React) backed by the scan status endpoint, with NO run-scan / upload /
connect / configure scanner / create-PR / release-gate button and no mutation.

Marker: ADMIN_CONSOLE_SCAN_POSTURE_VERIFY: PASS | FAIL
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

FORBIDDEN = re.compile(
    r"(run\s*scan|upload\s*source|connect\s*scanner|configure\s*scanner|"
    r"create\s*pr|release\s*gate|approve\s*release)",
    re.IGNORECASE,
)
MUTATION_VERB = re.compile(r"\.(post|put|patch|delete)\s*\(", re.IGNORECASE)

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

    if "Local Scan Toolchain Baseline" not in static_src:
        bad("static Security view missing the scan baseline section")
    if "/operations/security/scans/status" not in static_src:
        bad("static scan section not wired to the scan status endpoint")
    if "Local Scan Toolchain Baseline" not in page:
        bad("React Security page missing the scan baseline section")
    if "/operations/security/scans/status" not in ops:
        bad("React scan section not wired to the scan status endpoint")
    if not failures:
        ok("scan posture section present (static + React), status-endpoint backed")

    # only inspect the scan block in the static view
    block = static_src[
        static_src.find("Local Scan Toolchain Baseline") : static_src.find(
            "async function refreshSafetyPill"
        )
    ]
    for label, text in (("static", block), ("react", page)):
        for m in re.finditer(r"<button[^>]*>([^<]*)</button>", text, re.IGNORECASE):
            if FORBIDDEN.search(m.group(1)):
                bad(f"{label} scan view has a forbidden control button: {m.group(1)}")
    if MUTATION_VERB.search(page):
        bad("React Security page uses a mutation HTTP verb")
    if not [f for f in failures if "forbidden control" in f or "mutation" in f]:
        ok("no run-scan/upload/connect/configure/create-PR/release-gate button; no mutation verb")

    print(f"\n=== Summary: {len(passes)}/{len(passes) + len(failures)} checks passed ===")
    if failures:
        print("ADMIN_CONSOLE_SCAN_POSTURE_VERIFY: FAIL")
        return 1
    print("ADMIN_CONSOLE_SCAN_POSTURE_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
