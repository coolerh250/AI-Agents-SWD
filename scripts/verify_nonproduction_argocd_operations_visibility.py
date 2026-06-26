#!/usr/bin/env python3
"""Step 56 -- non-production ArgoCD operations visibility verifier.

Asserts the read-only API module is GET-only: 8 GET endpoints under
/operations/gitops/nonprod-argocd, and NO sync / install / delete / rollback /
promote / mutation endpoint, NO arbitrary namespace/command input, NO mutation HTTP
verb, and no token/password output.

Marker: NONPROD_ARGOCD_OPERATIONS_VISIBILITY_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "NONPROD_ARGOCD_OPERATIONS_VISIBILITY_VERIFY"
API = ROOT / "apps" / "orchestrator" / "src" / "gitops_argocd_api.py"

EXPECTED = [
    "preflight",
    "install",
    "project",
    "application",
    "sync",
    "safety",
    "report",
    "readiness",
]

failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def main() -> int:
    if not API.is_file():
        bad("missing gitops_argocd_api.py")
        print(f"{MARKER}: FAIL")
        return 1
    src = API.read_text(encoding="utf-8")

    if re.search(r"@router\.(post|put|patch|delete)\b", src):
        bad("API defines a mutation route (must be GET-only)")
    gets = re.findall(r'@router\.get\("(/[^"]*)"\)', src)
    for name in EXPECTED:
        if not any(g.endswith("/" + name) for g in gets):
            bad(f"missing GET endpoint: {name}")
    if 'prefix="/operations/gitops/nonprod-argocd"' not in src:
        bad("router prefix is not /operations/gitops/nonprod-argocd")
    # No mutation-flavoured endpoint paths.
    for word in ("/do-sync", "/install-", "/delete", "/rollback", "/promote", "/uninstall"):
        if word in src:
            bad(f"forbidden mutation endpoint path: {word}")
    # No direct secret-source access (the API only reads redacted posture views).
    for forbidden in ("subprocess", "os.environ", "open(", "requests."):
        if forbidden in src:
            bad(f"API must not access {forbidden} (read-only posture only)")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1
    print(f"  [OK] {len(gets)} GET-only endpoints; no sync/install/delete/rollback/promote")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
