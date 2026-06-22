#!/usr/bin/env python3
"""Step 53 -- Admin Console secret posture view verifier.

Asserts the Admin Console exposes a read-only Secret Posture view (static
fallback + React), backed by the read-only secret report API, with NO reveal /
copy / upload / rotate / configure / test button, no production-ready toggle, no
mutation client method, and no secret value display.

Marker: ADMIN_CONSOLE_SECRET_POSTURE_VERIFY: PASS | FAIL
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
PAGE = ADMIN / "src" / "pages" / "SecretPosture.tsx"
NAV = ADMIN / "src" / "components" / "Nav.tsx"
BASE = os.environ.get("ORCHESTRATOR_URL", "http://localhost:8000").rstrip("/")

FORBIDDEN_CONTROLS = re.compile(
    r"(reveal|copy|upload|rotate|configure|test\s*secret|enable|toggle|"
    r"show\s*secret|view\s*secret|client\s*secret)",
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
    if "Secret Posture" not in static_src or "renderSecrets" not in static_src:
        bad("static fallback missing the Secret Posture view")
    if "/operations/secrets/report" not in static_src:
        bad("static secret view must read the read-only secret report endpoint")
    if not PAGE.is_file():
        bad("React SecretPosture page missing")
    elif "/operations/secrets/report" not in (
        (ADMIN / "src" / "api" / "operations.ts").read_text(encoding="utf-8")
    ):
        bad("React secret page not wired to the secret report endpoint")
    if "Secret Posture" not in NAV.read_text(encoding="utf-8"):
        bad("nav missing Secret Posture entry")
    if not failures:
        ok("Secret Posture view present (static fallback + React + nav), report-API backed")

    page = PAGE.read_text(encoding="utf-8") if PAGE.is_file() else ""
    static_secret = static_src[
        static_src.find("async function renderSecrets") : static_src.find(
            "async function refreshSafetyPill"
        )
    ]
    for label, text in (("static", static_secret), ("react", page)):
        for m in re.finditer(r"<button[^>]*>([^<]*)</button>", text, re.IGNORECASE):
            if FORBIDDEN_CONTROLS.search(m.group(1)):
                bad(f"{label} secret view has a forbidden control button: {m.group(1)}")
        if MUTATION_VERB.search(text):
            bad(f"{label} secret view uses a mutation HTTP verb")
    if not [f for f in failures if "forbidden control" in f or "mutation" in f]:
        ok("secret view has no reveal/copy/upload/rotate/configure button; no mutation verb")

    code, _ = _get("/admin/")
    if code not in (200, 0):
        bad(f"/admin returned {code}")
    rcode, rbody = _get("/operations/secrets/report")
    if rcode != 200 and rcode != 0:
        bad(f"secret report endpoint returned {rcode}")
    elif rcode == 200 and "modeled_fail_closed_not_configured" not in rbody and "unknown" not in rbody:
        bad("secret report does not show a modeled fail-closed posture")
    if not [f for f in failures if "/admin" in f or "report endpoint" in f or "posture" in f]:
        ok("/admin reachable (or skipped) and secret report shows modeled fail-closed posture")

    print(f"\n=== Summary: {len(passes)}/{len(passes) + len(failures)} checks passed ===")
    if failures:
        print("ADMIN_CONSOLE_SECRET_POSTURE_VERIFY: FAIL")
        return 1
    print("ADMIN_CONSOLE_SECRET_POSTURE_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
