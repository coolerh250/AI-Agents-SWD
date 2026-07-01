#!/usr/bin/env python3
"""Step 64E-R -- operator walkthrough revalidation / status correction verifier.

Confirms Step 64E has been corrected to separate SOP document completeness (PASS) from operator
walkthrough validation (PENDING), overall PASS_WITH_OPERATOR_VALIDATION_PENDING, with Step 64F
paused pending operator validation and an explicit statement that Claude Code cannot
self-confirm operator acceptance. FAILs if any revalidation doc still marks Step 64E overall as
full PASS.

Marker: OPERATOR_WALKTHROUGH_REVALIDATION_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "docs" / "staging"

REPORT = STAGING / "operator-walkthrough-validation-report.md"
FORM = STAGING / "operator-walkthrough-confirmation-form.md"
NOTES = STAGING / "operator-walkthrough-revalidation-notes.md"

MARKER = "OPERATOR_WALKTHROUGH_REVALIDATION_VERIFY"
# The corrected Step 64E status is one of these resolved/pending values (never plain full PASS).
CORRECTED_STATUSES = ("PASS_WITH_OPERATOR_VALIDATION_PENDING", "FAILED_OPERATOR_VALIDATION")

DOCS = {"report": REPORT, "form": FORM, "notes": NOTES}

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
    report = texts["report"]
    report_low = report.lower()

    # Corrected split: document completeness PASS separate from operator validation status.
    if "document completeness" not in report_low or "pass" not in report_low:
        bad("validation report does not state SOP document completeness PASS")
    if "operator" not in report_low or not (
        "pending" in report_low or "not usable" in report_low or "completed" in report_low
    ):
        bad("validation report does not record operator walkthrough validation status")
    if not any(s in report for s in CORRECTED_STATUSES):
        bad("validation report does not declare a corrected Step 64E status (pending or failed)")

    # FAIL if any doc still marks Step 64E overall as full PASS (not the pending variant).
    # Skip negations ("is not full PASS") which reinforce the correction rather than claim it.
    for name, text in texts.items():
        for line in text.splitlines():
            ll = line.lower()
            if "overall" in ll and "step 64e" in ll and "pass" in ll:
                negation = " not " in ll or "not full" in ll or "must not" in ll
                if "pass_with_operator_validation_pending" not in ll and not negation:
                    bad(f"{name} marks Step 64E overall as full PASS: {line.strip()[:80]}")

    # Step 64F paused / blocked pending operator validation.
    if "step 64f" not in low:
        bad("docs do not mention Step 64F gating")
    if not ("pause" in low or "paused" in low or "blocked" in low or "should not proceed" in low):
        bad("docs do not state Step 64F is paused/blocked pending operator validation")

    # Claude Code cannot self-confirm operator acceptance.
    if "cannot self-confirm" not in low and "cannot self confirm" not in low:
        bad("docs do not state Claude Code cannot self-confirm operator acceptance")

    # Confirmation form has operator-fillable items.
    form = texts["form"]
    if "Confirmed: yes / no / not checked" not in form:
        bad("confirmation form lacks operator-fillable confirmation items")
    if "SaaS User Management Module" not in form or "Create user CRUD API" not in form:
        bad("confirmation form does not reference the demo project/work item")

    # No production action + live integrations disabled documented.
    if "no production action" not in low:
        bad("docs do not state no production action")
    if "live-integrations=disabled" not in both:
        bad("docs do not carry live-integrations=disabled flag")

    # Machine-checkable safety flags on every doc.
    for name, text in texts.items():
        for flag in (
            "production-action=false",
            "production-ready=false",
            "staging-only=true",
            "public-exposure=false",
            "live-integrations=disabled",
        ):
            if flag not in text:
                bad(f"{name} missing safety flag {flag}")
        for forbidden in (
            "production-action=true",
            "production-ready=true",
            "public-exposure=true",
        ):
            if forbidden in text:
                bad(f"{name} contains forbidden claim {forbidden}")

    # No secret material.
    for name, text in texts.items():
        if SECRET_SHAPES.search(text):
            bad(f"{name} contains secret-shaped content (private key / token / kubeconfig)")
        if PASSWORD_ASSIGN.search(text):
            bad(f"{name} contains a stored password assignment")
        if "p@ssw0rd" in text:
            bad(f"{name} contains a literal password")

    # production_executed must remain 0 documented.
    if "production_executed_true_count" not in low:
        bad("docs do not state production_executed_true_count posture")
    if re.search(r"production_executed_true_count\s*[`]*\s*[:=]?\s*[`]*\s*[1-9]", low):
        bad("production_executed_true_count is non-zero")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1
    print("  [OK] Step 64E corrected: doc completeness PASS, operator validation status recorded,")
    print("       overall not full PASS; Step 64F paused/blocked; Claude Code cannot self-confirm;")
    print("       prod_exec=0")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
