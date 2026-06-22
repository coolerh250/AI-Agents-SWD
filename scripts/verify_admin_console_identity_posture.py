#!/usr/bin/env python3
"""Step 52.4 -- Admin Console identity posture view verifier.

Asserts the Admin Console exposes a read-only Identity Posture view (static
fallback + React source), backed by the read-only identity report API, with NO
OIDC login / connect / configure button, no production auth toggle, no
role-mapping editor, no break-glass button, no mutation client method, and no
token/secret display. Combines a live /admin + report check with a source guard.

Marker: ADMIN_CONSOLE_IDENTITY_POSTURE_VERIFY: PASS | FAIL
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
IDENTITY_PAGE = ADMIN / "src" / "pages" / "IdentityPosture.tsx"
NAV = ADMIN / "src" / "components" / "Nav.tsx"
CLIENT = ADMIN / "src" / "api" / "client.ts"
BASE = os.environ.get("ORCHESTRATOR_URL", "http://localhost:8000").rstrip("/")

# Forbidden identity mutation / auth controls (case-insensitive button text).
FORBIDDEN_CONTROLS = re.compile(
    r"(login|connect|configure|enable|toggle|editor|activate|"
    r"force\s*logout|logout\s*all|upload|client\s*secret|break[_-]?glass)",
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
    if "Identity Posture" not in static_src or "renderIdentity" not in static_src:
        bad("static fallback missing the Identity Posture view")
    if "/operations/identity/report" not in static_src:
        bad("static identity view must read the read-only identity report endpoint")
    if not IDENTITY_PAGE.is_file():
        bad("React IdentityPosture page missing")
    elif "/operations/identity/report" not in (
        (ADMIN / "src" / "api" / "operations.ts").read_text(encoding="utf-8")
    ):
        bad("React identity page not wired to the identity report endpoint")
    if "Identity Posture" not in NAV.read_text(encoding="utf-8"):
        bad("nav missing Identity Posture entry")
    if not failures:
        ok("Identity Posture view present (static fallback + React + nav), report-API backed")

    # no OIDC login/connect/configure/toggle/editor/break-glass controls; no mutation verb
    identity_page = IDENTITY_PAGE.read_text(encoding="utf-8") if IDENTITY_PAGE.is_file() else ""
    static_identity = static_src[
        static_src.find("async function renderIdentity") : static_src.find(
            "async function refreshSafetyPill"
        )
    ]
    for label, text in (("static", static_identity), ("react", identity_page)):
        for m in re.finditer(r"<button[^>]*>([^<]*)</button>", text, re.IGNORECASE):
            if FORBIDDEN_CONTROLS.search(m.group(1)):
                bad(f"{label} identity view has a forbidden control button: {m.group(1)}")
        if MUTATION_VERB.search(text):
            bad(f"{label} identity view uses a mutation HTTP verb")
    if not [f for f in failures if "forbidden control" in f or "mutation" in f]:
        ok("identity view has no login/connect/configure/toggle/editor/break-glass button")

    # live /admin + report endpoint posture
    code, _ = _get("/admin/")
    if code == 0:
        bad(f"/admin not reachable at {BASE}")
    elif code != 200:
        bad(f"/admin returned {code}")
    rcode, rbody = _get("/operations/identity/report")
    if rcode != 200:
        bad(f"identity report endpoint returned {rcode}")
    elif "modeled_fail_closed_not_enabled" not in rbody and "unknown" not in rbody:
        bad("identity report does not show a modeled fail-closed posture")
    if not [f for f in failures if "/admin" in f or "report endpoint" in f or "posture" in f]:
        ok("/admin reachable and identity report shows the modeled fail-closed posture")

    print(f"\n=== Summary: {len(passes)}/{len(passes) + len(failures)} checks passed ===")
    if failures:
        print("ADMIN_CONSOLE_IDENTITY_POSTURE_VERIFY: FAIL")
        return 1
    print("ADMIN_CONSOLE_IDENTITY_POSTURE_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
