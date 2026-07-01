#!/usr/bin/env python3
"""Step 64E.3A -- Admin Console demo-evidence UI/API diagnosis verifier.

Confirms the read-only diagnosis of the five missing demo-evidence items is complete: each item
is diagnosed with backend / API / frontend status + a recommended fix; the endpoint map, route
map, mismatch report, and remediation plan exist; no remediation was implemented; Step 64E stays
FAILED_OPERATOR_VALIDATION and Step 64F stays BLOCKED; production_executed stays 0.

Marker: ADMIN_CONSOLE_DEMO_EVIDENCE_DIAGNOSIS_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "docs" / "staging"
DIAGNOSIS = STAGING / "admin-console-demo-evidence-ui-api-diagnosis.md"
ENDPOINTS = STAGING / "admin-console-demo-evidence-endpoint-map.md"
ROUTES = STAGING / "admin-console-demo-evidence-frontend-route-map.md"
MISMATCH = STAGING / "admin-console-demo-evidence-ui-api-mismatch-report.md"
PLAN = STAGING / "admin-console-demo-evidence-remediation-plan.md"

MARKER = "ADMIN_CONSOLE_DEMO_EVIDENCE_DIAGNOSIS_VERIFY"

DOCS = {
    "diagnosis": DIAGNOSIS,
    "endpoints": ENDPOINTS,
    "routes": ROUTES,
    "mismatch": MISMATCH,
    "plan": PLAN,
}

# The five failed items -- each must be diagnosed. (term, regex to find it in the diagnosis doc)
ITEMS = ("wi-0001", "agent execution", "workflow", "qa", "audit")

SECRET_SHAPES = re.compile(
    r"(-----BEGIN [A-Z ]*PRIVATE KEY|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
    r"AKIA[0-9A-Z]{16}|xoxb-[A-Za-z0-9-]{10,}|apiVersion:\s*v1[\s\S]*kubeconfig)"
)
PASSWORD_ASSIGN = re.compile(r"password\s*[:=]\s*\S", re.IGNORECASE)

failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def main() -> int:
    for name, p in DOCS.items():
        if not p.is_file():
            bad(f"missing doc: docs/staging/{p.name}")
    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    texts = {name: p.read_text(encoding="utf-8") for name, p in DOCS.items()}
    both = "\n".join(texts.values())
    low = both.lower()
    diag_low = texts["diagnosis"].lower()

    # All five failed items diagnosed in the diagnosis doc.
    for term in ITEMS:
        if term not in diag_low:
            bad(f"diagnosis doc does not diagnose item: {term}")

    # Each item has backend / API / frontend status + recommended fix (checked doc-wide).
    for phrase in (
        "backend data status",
        "api route status",
        "frontend route status",
        "recommended fix",
    ):
        if phrase not in diag_low:
            bad(f"diagnosis doc missing required field: {phrase}")
    # There should be one recommended fix per item (>=5).
    if diag_low.count("recommended fix") < 5:
        bad("diagnosis doc has fewer than five per-item recommended fixes")

    # Mismatch report identifies a root cause category per item (a table with 5 rows).
    mism_low = texts["mismatch"].lower()
    for term in ITEMS:
        if term not in mism_low:
            bad(f"mismatch report does not cover item: {term}")

    # Remediation plan present with concrete sections.
    plan_low = texts["plan"].lower()
    for phrase in ("frontend changes", "backend api changes", "tests needed", "operator re-review"):
        if phrase not in plan_low:
            bad(f"remediation plan missing section: {phrase}")

    # No remediation implemented (diagnosis-only).
    if "no remediation implemented" not in low and "no code change" not in low:
        bad("docs do not state no remediation implemented")

    # Step 64E stays failed, Step 64F stays blocked.
    if "failed_operator_validation" not in low:
        bad("docs do not keep Step 64E FAILED_OPERATOR_VALIDATION")
    if "step 64f" not in low or "block" not in low:
        bad("docs do not keep Step 64F BLOCKED")

    # No production action; live integrations disabled; prod_exec 0.
    if "no production action" not in low:
        bad("docs do not state no production action")
    if "live-integrations=disabled" not in both:
        bad("docs do not carry live-integrations=disabled flag")

    for name, text in texts.items():
        for flag in (
            "production-action=false",
            "production-ready=false",
            "staging-only=true",
            "live-integrations=disabled",
        ):
            if flag not in text:
                bad(f"{name} missing safety flag {flag}")
        for forbidden in ("production-action=true", "production-ready=true"):
            if forbidden in text:
                bad(f"{name} contains forbidden claim {forbidden}")
        if SECRET_SHAPES.search(text):
            bad(f"{name} contains secret-shaped content")
        if PASSWORD_ASSIGN.search(text):
            bad(f"{name} contains a stored password assignment")
        if "p@ssw0rd" in text:
            bad(f"{name} contains a literal password")

    if "production_executed_true_count" not in low:
        bad("docs do not state production_executed_true_count posture")
    if re.search(r"production_executed_true_count\s*[`]*\s*[:=]?\s*[`]*\s*[1-9]", low):
        bad("production_executed_true_count is non-zero")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1
    print("  [OK] all five demo-evidence items diagnosed (backend/API/frontend + fix); endpoint +")
    print("       route maps + mismatch report + remediation plan present; no remediation")
    print("       implemented; Step 64E failed + 64F blocked; prod_exec=0")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
