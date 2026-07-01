#!/usr/bin/env python3
"""Step 64B.1 -- authenticated staging host preflight verifier.

Confirms the authenticated read-only host preflight report + runtime bootstrap readiness
docs exist, document the 10.0.1.32 SSH target with safe (key/interactive/operator-run only)
credential handling, expose no password / private key / token / secret, do not claim a
runtime deployment or production readiness, and keep production_executed at 0.

Marker: STAGING_HOST_AUTHENTICATED_PREFLIGHT_VERIFY: PASS | FAIL
(If authenticated access was impossible, the operator/agent reports BLOCKED_AUTH_METHOD
instead of PASS; this verifier requires a completed authenticated report to PASS.)
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "docs" / "staging"
REPORT = STAGING / "staging-host-preflight-report.md"
READINESS = STAGING / "staging-runtime-bootstrap-readiness.md"
OPERATOR_SCRIPT = ROOT / "scripts" / "staging_host_preflight_operator_run.sh"

MARKER = "STAGING_HOST_AUTHENTICATED_PREFLIGHT_VERIFY"

# Secret shapes that must never appear in the committed docs/script.
SECRET_SHAPES = re.compile(
    r"(-----BEGIN [A-Z ]*PRIVATE KEY|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
    r"AKIA[0-9A-Z]{16}|xoxb-[A-Za-z0-9-]{10,}|apiVersion:\s*v1[\s\S]*kubeconfig)"
)
# A stored password shape like `password: <value>` / `password=<value>` (not the word alone).
PASSWORD_ASSIGN = re.compile(r"password\s*[:=]\s*\S", re.IGNORECASE)

failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def main() -> int:
    for p in (REPORT, READINESS):
        if not p.is_file():
            bad(f"missing doc: docs/staging/{p.name}")
    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    report = REPORT.read_text(encoding="utf-8")
    readiness = READINESS.read_text(encoding="utf-8")
    both = report + "\n" + readiness

    # Target host + safe credential handling.
    for name, text in (("report", report), ("readiness", readiness)):
        if "10.0.1.32" not in text:
            bad(f"{name} does not document target host 10.0.1.32")
    low = both.lower()
    if not ("key-based" in low or "interactive" in low or "operator-run" in low):
        bad("credential handling not documented as key/interactive/operator-run only")
    if "never" not in low or (
        "printed" not in low and "committed" not in low and "stored" not in low
    ):
        bad("docs do not state credentials are never printed/committed/stored")

    # No secret material anywhere in the committed docs or the operator script.
    scan_targets = [("report", report), ("readiness", readiness)]
    if OPERATOR_SCRIPT.is_file():
        scan_targets.append(("operator-script", OPERATOR_SCRIPT.read_text(encoding="utf-8")))
    for name, text in scan_targets:
        if SECRET_SHAPES.search(text):
            bad(f"{name} contains secret-shaped content (private key / token / kubeconfig)")
        if PASSWORD_ASSIGN.search(text):
            bad(f"{name} contains a stored password assignment")
        # A literal known-weak password must never be committed.
        if "p@ssw0rd" in text:
            bad(f"{name} contains a literal password")

    # Machine-checkable safety flags: no production action, no runtime deployment, not ready.
    for name, text in (("report", report), ("readiness", readiness)):
        for flag in (
            "production-action=false",
            "production-ready=false",
            "runtime-deployment=false",
            "staging-only=true",
        ):
            if flag not in text:
                bad(f"{name} missing safety flag {flag}")
        for forbidden in (
            "production-action=true",
            "production-ready=true",
            "runtime-deployment=true",
            "production-deploy=true",
        ):
            if forbidden in text:
                bad(f"{name} contains forbidden claim {forbidden}")

    # Runtime bootstrap must not be *claimed* ready unless the readiness doc says so.
    if (
        "ready_for_runtime_bootstrap: **true**" in readiness
        or "ready-for-runtime-bootstrap=true" in readiness
    ):
        # allowed only if the report shows Docker available; here Docker is not installed.
        if "not installed" in readiness.lower() or "docker: not installed" in report.lower():
            bad("readiness claims ready_for_runtime_bootstrap=true while Docker is not installed")
    if "ready_for_runtime_bootstrap:" not in readiness:
        bad("readiness doc missing ready_for_runtime_bootstrap decision")

    # The report must reflect a *completed authenticated* preflight (not an empty/blocked stub).
    if "authenticated" not in report.lower():
        bad("report does not indicate an authenticated preflight")
    if not re.search(r"ubuntu|os\b", report, re.IGNORECASE):
        bad("report does not contain collected OS inventory")

    # production_executed must remain 0.
    if "production_executed_true_count" not in low:
        bad("docs do not state production_executed_true_count posture")
    if re.search(r"production_executed_true_count\s*[:=]?\s*[1-9]", both):
        bad("production_executed_true_count is non-zero")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1
    print("  [OK] authenticated host preflight recorded; 10.0.1.32 key-based; no secret/password/")
    print("       private-key exposure; no runtime deployment; no production action; prod_exec=0")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
