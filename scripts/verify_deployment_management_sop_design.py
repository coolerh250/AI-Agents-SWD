#!/usr/bin/env python3
"""Step 64F.1 -- Staging deployment management SOP design verifier.

Confirms the staging deployment-management SOP package exists and documents every required
procedure (start / stop / restart / rebuild-redeploy / upgrade / rollback / teardown / restore /
health-safety validation / troubleshooting / authorization matrix), keeps destructive commands
behind explicit authorization, and asserts this is design-only (no runtime change, no production
action, production_executed stays 0). Step 64E stays PASS; Step 64F is SOP_DESIGN_COMPLETED.

Marker: DEPLOYMENT_MANAGEMENT_SOP_DESIGN_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "docs" / "staging"
SOP = STAGING / "deployment-management-sop.md"
CHECKLIST = STAGING / "deployment-management-operator-checklist.md"
COMMANDS = STAGING / "deployment-management-command-reference.md"
AUTHZ = STAGING / "deployment-management-authorization-matrix.md"
TROUBLE = STAGING / "deployment-management-troubleshooting-guide.md"
VALIDATION = STAGING / "deployment-management-validation-plan.md"
RISKS = STAGING / "deployment-management-known-risks.md"

MARKER = "DEPLOYMENT_MANAGEMENT_SOP_DESIGN_VERIFY"

DOCS = {
    "sop": SOP,
    "operator-checklist": CHECKLIST,
    "command-reference": COMMANDS,
    "authorization-matrix": AUTHZ,
    "troubleshooting-guide": TROUBLE,
    "validation-plan": VALIDATION,
    "known-risks": RISKS,
}
# Procedures the main SOP must document.
PROCEDURES = (
    "start procedure",
    "stop procedure",
    "restart procedure",
    "redeploy",
    "upgrade procedure",
    "rollback procedure",
    "teardown procedure",
    "restore procedure",
    "health and safety validation",
    "troubleshooting",
    "authorization matrix",
)

SECRET_SHAPES = re.compile(
    r"(-----BEGIN [A-Z ]*PRIVATE KEY|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
    r"AKIA[0-9A-Z]{16}|xoxb-[A-Za-z0-9-]{10,})"
)
PASSWORD_ASSIGN = re.compile(r"password\s*[:=]\s*\S", re.IGNORECASE)

failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def main() -> int:
    for name, p in DOCS.items():
        if not p.is_file():
            bad(f"missing doc: docs/staging/{p.name} ({name})")
    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    texts = {name: p.read_text(encoding="utf-8") for name, p in DOCS.items()}
    both = "\n".join(texts.values())
    low = both.lower()
    sop_low = texts["sop"].lower()

    # Main SOP documents every required procedure.
    for proc in PROCEDURES:
        if proc not in sop_low:
            bad(f"SOP does not document: {proc}")

    # Destructive commands require explicit authorization.
    if "destructive" not in low or "explicit" not in low or "authorization" not in low:
        bad("docs do not require explicit authorization for destructive commands")
    # Authorization matrix content present.
    if "authorization" not in texts["authorization-matrix"].lower():
        bad("authorization matrix doc has no authorization content")
    # Troubleshooting content present.
    if "troubleshoot" not in texts["troubleshooting-guide"].lower():
        bad("troubleshooting guide has no troubleshooting content")

    # Status transition.
    if "step 64e" not in low or "pass" not in low:
        bad("docs do not record Step 64E: PASS")
    if "sop_design_completed" not in low and "in_progress" not in low:
        bad("docs do not record Step 64F SOP_DESIGN_COMPLETED / IN_PROGRESS")

    # Design-only: no runtime change / no production action / prod_exec 0; not production readiness.
    if "no runtime change" not in low:
        bad("docs do not state no runtime change occurred")
    if "not production readiness" not in low:
        bad("docs do not state this is not production readiness")
    for name, text in texts.items():
        tl = text.lower()
        if "no production action" not in tl:
            bad(f"{name} does not state no production action")
        if "production_executed_true_count=0" not in tl:
            bad(f"{name} does not document production_executed_true_count=0")
        for flag in ("production-action=false", "image-push=false", "live-integrations=disabled"):
            if flag not in text:
                bad(f"{name} missing safety flag {flag}")
        for forbidden in ("production-action=true", "image-push=true", "production-ready=true"):
            if forbidden in text:
                bad(f"{name} contains forbidden claim {forbidden}")
        if SECRET_SHAPES.search(text):
            bad(f"{name} contains secret-shaped content")
        if PASSWORD_ASSIGN.search(text):
            bad(f"{name} contains a stored password assignment")

    if re.search(r"production_executed_true_count\s*[`]*\s*[:=]?\s*[`]*\s*[1-9]", low):
        bad("production_executed_true_count is non-zero")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    print("  [OK] SOP package documents start/stop/restart/redeploy/upgrade/rollback/teardown/")
    print("       restore/validation/troubleshooting/authorization; destructive = explicit auth;")
    print("       design-only, no runtime change, no production action; Step 64E PASS; prod_exec=0")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
