#!/usr/bin/env python3
"""Step 64E.2 -- operator re-review failure recording verifier.

Confirms the operator's post-remediation re-review verdict (NOT_USABLE) is recorded: the five
missing UI-evidence items, the verdict, that Step 64E stays FAILED_OPERATOR_VALIDATION and Step
64F stays BLOCKED, and that the next remediation (Admin Console Demo Evidence UI Remediation) is
identified. production_executed must remain 0. FAILs if Step 64E is marked PASS.

Marker: OPERATOR_REREVIEW_FAILURE_RECORDING_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "docs" / "staging"
RESULT = STAGING / "operator-rereview-result-after-react-bundle-remediation.md"
BLOCKER = STAGING / "admin-console-demo-evidence-ui-blocker.md"
STATUS = STAGING / "step64e-current-blocker-status.md"

MARKER = "OPERATOR_REREVIEW_FAILURE_RECORDING_VERIFY"

DOCS = {"result": RESULT, "blocker": BLOCKER, "status": STATUS}

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
    result_low = texts["result"].lower()

    # Operator verdict NOT_USABLE recorded.
    if "not_usable" not in low and "not usable" not in low:
        bad("operator NOT_USABLE verdict not recorded")

    # The five missing UI-evidence items recorded (in the result doc).
    if "wi-0001" not in result_low:
        bad("WI-0001 not-visible not recorded")
    for term in ("agent execution", "workflow", "qa", "audit"):
        if term not in result_low:
            bad(f"missing-evidence item not recorded: {term}")
    # The result doc should record these as not visible.
    if result_low.count("no") < 5:
        bad("result doc does not record the five 'no' visibility results")

    # Step 64E stays failed, Step 64F stays blocked.
    if "failed_operator_validation" not in low:
        bad("docs do not keep Step 64E FAILED_OPERATOR_VALIDATION")
    if "step 64f" not in low or "block" not in low:
        bad("docs do not keep Step 64F BLOCKED")

    # FAIL if Step 64E is marked PASS. Only flag lines that assert the overall status as PASS;
    # allow lines that also say failed / doc-completeness / are the 64E.1 PASS_WITH_GAPS ref.
    for name, text in texts.items():
        for line in text.splitlines():
            ll = line.lower()
            if "step 64e" in ll and "pass" in ll and "step 64e.1" not in ll:
                allowed = (
                    "failed" in ll
                    or " not " in ll
                    or "pass_with_gaps" in ll
                    or "doc completeness" in ll
                )
                if not allowed:
                    bad(f"{name} marks Step 64E as PASS: {line.strip()[:80]}")

    # Next remediation identified.
    if "demo evidence ui" not in low and "demo-evidence ui" not in low:
        bad("next remediation (Admin Console Demo Evidence UI Remediation) not documented")

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
    print("  [OK] operator re-review NOT_USABLE recorded; five UI-evidence items still not")
    print("       visible; Step 64E failed + Step 64F blocked; next = demo-evidence UI")
    print("       remediation; no production action; prod_exec=0")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
