#!/usr/bin/env python3
"""Step 59 -- Admin Console sandbox GitHub draft PR view verifier.

Marker: ADMIN_CONSOLE_SANDBOX_GITHUB_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADMIN = ROOT / "apps" / "admin-console"
STATIC = ADMIN / "static" / "index.html"
PAGE = ADMIN / "src" / "pages" / "SandboxGithub.tsx"
OPS = ADMIN / "src" / "api" / "operations.ts"

SECTION = "Sandbox GitHub Draft PR (Step 59)"
# Forbidden interactive controls (buttons / inputs) -- not prose.
FORBIDDEN_BTN = re.compile(
    r"(merge|ready[\s-]*for[\s-]*review|workflow\s*dispatch|production\s*deploy)", re.IGNORECASE
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
        bad("static view missing the Step 59 sandbox GitHub section")
    if SECTION not in page:
        bad("React page missing the Step 59 sandbox GitHub section")
    if "getSandboxGithubPolicy" not in ops or "/operations/github/sandbox-draft-pr/" not in ops:
        bad("operations.ts missing sandbox GitHub getters")

    # No forbidden control buttons in either view.
    for label, text in (("static", static_src), ("react", page)):
        block = text[text.find(SECTION) :] if SECTION in text else ""
        for mtch in re.finditer(r"<button[^>]*>([^<]*)</button>", block, re.IGNORECASE):
            if FORBIDDEN_BTN.search(mtch.group(1)):
                bad(f"{label} view has a forbidden control button: {mtch.group(1)}")

    # No token input, no arbitrary owner/repo free-text input in the section.
    for label, text in (("static", static_src), ("react", page)):
        block = text[text.find(SECTION) :] if SECTION in text else ""
        if re.search(r"<input[^>]*(token|owner|repo)[^>]*>", block, re.IGNORECASE):
            bad(f"{label} view exposes a token/owner/repo input")

    # The React page must not use a mutation HTTP verb.
    if re.search(r"\.(post|put|patch|delete)\s*\(", page, re.IGNORECASE):
        bad("React sandbox GitHub page uses a mutation HTTP verb")

    if failures:
        print("ADMIN_CONSOLE_SANDBOX_GITHUB_VERIFY: FAIL")
        return 1
    print(
        "  [OK] sandbox GitHub view present (static + React); no merge/review/workflow/token control"
    )
    print("ADMIN_CONSOLE_SANDBOX_GITHUB_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
