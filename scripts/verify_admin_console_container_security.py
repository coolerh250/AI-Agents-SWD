#!/usr/bin/env python3
"""Step 54.3 -- Admin Console SBOM / container security view verifier.

Marker: ADMIN_CONSOLE_CONTAINER_SECURITY_VERIFY: PASS | FAIL
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
    r"(generate\s*sbom|pull\s*image|scan\s*image|login\s*registry|push\s*image|"
    r"sign\s*image|attest\s*image|approve\s*image)",
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

    if "SBOM / Image Digest / Container Security" not in static_src:
        bad("static Security view missing the SBOM/container section")
    if "/operations/security/sbom/status" not in static_src:
        bad("static SBOM section not wired to the sbom status endpoint")
    if "SBOM / Image Digest / Container Security" not in page:
        bad("React Security page missing the SBOM/container section")
    if "/operations/security/sbom/status" not in ops:
        bad("React SBOM section not wired to the sbom status endpoint")
    if not failures:
        ok("SBOM/container section present (static + React), status-endpoint backed")

    block = static_src[
        static_src.find("SBOM / Image Digest / Container Security") : static_src.find(
            "async function refreshSafetyPill"
        )
    ]
    for label, text in (("static", block), ("react", page)):
        for m in re.finditer(r"<button[^>]*>([^<]*)</button>", text, re.IGNORECASE):
            if FORBIDDEN.search(m.group(1)):
                bad(f"{label} view has a forbidden control button: {m.group(1)}")
    if re.search(r"\.(post|put|patch|delete)\s*\(", page, re.IGNORECASE):
        bad("React Security page uses a mutation HTTP verb")
    if not [f for f in failures if "forbidden control" in f or "mutation" in f]:
        ok("no generate-SBOM / pull / scan / login / push / sign / attest button; no mutation")

    print(f"\n=== Summary: {len(passes)}/{len(passes) + len(failures)} checks passed ===")
    if failures:
        print("ADMIN_CONSOLE_CONTAINER_SECURITY_VERIFY: FAIL")
        return 1
    print("ADMIN_CONSOLE_CONTAINER_SECURITY_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
