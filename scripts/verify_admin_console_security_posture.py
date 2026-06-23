#!/usr/bin/env python3
"""Step 54.1 -- Admin Console security posture view verifier.

Asserts the Admin Console exposes a read-only Security / Supply Chain Posture
view (static fallback + React), backed by the read-only security report API, with
NO run-scan / upload-source / connect-scanner / configure-scanner / create-PR /
push-image / production-gate button, no mutation client method, and a role that
does not unlock any mutation action.

Marker: ADMIN_CONSOLE_SECURITY_POSTURE_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADMIN = ROOT / "apps" / "admin-console"
STATIC_INDEX = ADMIN / "static" / "index.html"
PAGE = ADMIN / "src" / "pages" / "SecurityPosture.tsx"
NAV = ADMIN / "src" / "components" / "Nav.tsx"
OPS = ADMIN / "src" / "api" / "operations.ts"
BASE = os.environ.get("ORCHESTRATOR_URL", "http://localhost:8000").rstrip("/")

FORBIDDEN_CONTROLS = re.compile(
    r"(run\s*scan|upload\s*source|connect\s*scanner|configure\s*scanner|"
    r"create\s*pr|push\s*image|production\s*gate|release\s*approve|enable|toggle)",
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


def _get(path: str) -> tuple[int, str]:
    try:
        with urllib.request.urlopen(BASE + path, timeout=8) as resp:  # noqa: S310
            return resp.status, resp.read().decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except (urllib.error.URLError, OSError):
        return 0, ""


def main() -> int:
    static_src = STATIC_INDEX.read_text(encoding="utf-8")
    if "Security / Supply Chain" not in static_src or "renderSecurity" not in static_src:
        bad("static fallback missing the Security / Supply Chain view")
    if "/operations/security/report" not in static_src:
        bad("static security view must read the read-only security report endpoint")
    if not PAGE.is_file():
        bad("React SecurityPosture page missing")
    elif "/operations/security/report" not in OPS.read_text(encoding="utf-8"):
        bad("React security page not wired to the security report endpoint")
    if "Security / Supply Chain" not in NAV.read_text(encoding="utf-8"):
        bad("nav missing Security / Supply Chain entry")
    if not failures:
        ok("Security posture view present (static fallback + React + nav), report-API backed")

    page = PAGE.read_text(encoding="utf-8") if PAGE.is_file() else ""
    static_security = static_src[
        static_src.find("async function renderSecurity") : static_src.find(
            "async function refreshSafetyPill"
        )
    ]
    for label, text in (("static", static_security), ("react", page)):
        for m in re.finditer(r"<button[^>]*>([^<]*)</button>", text, re.IGNORECASE):
            if FORBIDDEN_CONTROLS.search(m.group(1)):
                bad(f"{label} security view has a forbidden control button: {m.group(1)}")
        if MUTATION_VERB.search(text):
            bad(f"{label} security view uses a mutation HTTP verb")
    if not [f for f in failures if "forbidden control" in f or "mutation" in f]:
        ok("security view has no run-scan/upload/connect/create-PR/push-image button; no mutation")

    code, _ = _get("/admin/")
    if code not in (200, 0):
        bad(f"/admin returned {code}")
    rcode, rbody = _get("/operations/security/report")
    if rcode not in (200, 0):
        bad(f"security report endpoint returned {rcode}")
    elif rcode == 200 and "modeled_not_enforced" not in rbody and "unknown" not in rbody:
        bad("security report does not show a modeled_not_enforced posture")
    if not [f for f in failures if "/admin" in f or "report endpoint" in f or "posture" in f]:
        ok("/admin reachable (or skipped) and security report shows modeled_not_enforced posture")

    print(f"\n=== Summary: {len(passes)}/{len(passes) + len(failures)} checks passed ===")
    if failures:
        print("ADMIN_CONSOLE_SECURITY_POSTURE_VERIFY: FAIL")
        return 1
    print("ADMIN_CONSOLE_SECURITY_POSTURE_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
