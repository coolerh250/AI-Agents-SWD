#!/usr/bin/env python3
"""Step 61 -- Admin Console backup / restore / DR view verifier.

Marker: ADMIN_CONSOLE_BACKUP_DR_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADMIN = ROOT / "apps" / "admin-console"
STATIC = ADMIN / "static" / "index.html"
PAGE = ADMIN / "src" / "pages" / "BackupDr.tsx"
OPS = ADMIN / "src" / "api" / "operations.ts"

SECTION = "Backup / Restore / DR Operations (Step 61)"
# Forbidden interactive controls (button labels), not prose.
FORBIDDEN_BTN = re.compile(
    r"(execute\s*cleanup|execute\s*restore|run\s*cleanup|run\s*restore|failover|"
    r"teardown|argocd\s*sync|cloud\s*upload|production\s*restore|production\s*ready)",
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
        bad("static view missing the Step 61 backup/restore/DR section")
    if SECTION not in page:
        bad("React page missing the Step 61 backup/restore/DR section")
    if "getDrPolicy" not in ops or "/operations/dr/" not in ops:
        bad("operations.ts missing backup/restore/DR getters")

    # No forbidden control buttons in either view.
    for label, text in (("static", static_src), ("react", page)):
        block = text[text.find(SECTION) :] if SECTION in text else ""
        for mtch in re.finditer(r"<button[^>]*>([^<]*)</button>", block, re.IGNORECASE):
            if FORBIDDEN_BTN.search(mtch.group(1)):
                bad(f"{label} view has a forbidden control button: {mtch.group(1)}")
        if re.search(r"<input[^>]*type=[\"']checkbox[\"'][^>]*production", block, re.IGNORECASE):
            bad(f"{label} view exposes a production-ready toggle")

    # The React page must not use a mutation HTTP verb.
    if re.search(r"\.(post|put|patch|delete)\s*\(", page, re.IGNORECASE):
        bad("React backup/restore/DR page uses a mutation HTTP verb")

    if failures:
        print("ADMIN_CONSOLE_BACKUP_DR_VERIFY: FAIL")
        return 1
    print(
        "  [OK] backup/restore/DR view present (static + React); "
        "no execute/failover/teardown/sync/prod control"
    )
    print("ADMIN_CONSOLE_BACKUP_DR_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
