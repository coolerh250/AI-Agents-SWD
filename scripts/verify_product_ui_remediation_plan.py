#!/usr/bin/env python3
"""Step 64E.4A -- Product UI remediation plan verifier.

Confirms the formal-product-UI remediation planning docs exist and are consistent: the formal-page
evidence map maps each evidence type to its formal product page; the Demo Evidence page is declared
diagnostic-only (not a staging acceptance path); the test/QA remediation, staging redeploy, operator
re-review, and controlled external integration plans exist; Step 64E stays failed and Step 64F
blocked; and no implementation / production action is claimed (production_executed stays 0).

Marker: PRODUCT_UI_REMEDIATION_PLAN_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "docs" / "staging"

PLAN = STAGING / "product-ui-remediation-plan.md"
MAP = STAGING / "formal-admin-console-page-evidence-map.md"
REPRESENTATIVENESS = STAGING / "staging-representativeness-policy.md"
DIAGNOSTIC = STAGING / "demo-evidence-page-diagnostic-only-policy.md"
TESTQA = STAGING / "product-ui-test-qa-remediation-plan.md"
REDEPLOY = STAGING / "product-ui-staging-redeploy-plan.md"
REREVIEW = STAGING / "operator-product-ui-rereview-plan.md"
EXTERNAL = STAGING / "controlled-staging-external-integration-roadmap.md"

MARKER = "PRODUCT_UI_REMEDIATION_PLAN_VERIFY"

DOCS = {
    "remediation-plan": PLAN,
    "evidence-map": MAP,
    "representativeness-policy": REPRESENTATIVENESS,
    "diagnostic-only-policy": DIAGNOSTIC,
    "test-qa-plan": TESTQA,
    "redeploy-plan": REDEPLOY,
    "rereview-plan": REREVIEW,
    "external-integration-roadmap": EXTERNAL,
}

# evidence type -> formal product page (both must co-occur on one line of the evidence map).
EVIDENCE_MAP = (
    ("wi-0001", "projects / work items"),
    ("agent execution", "agent executions"),
    ("workflow", "workflows / task graph"),
    ("qa/code", "qa / code"),
    ("audit", "audit / evidence"),
    ("safety", "safety center"),
)

SECRET_SHAPES = re.compile(
    r"(-----BEGIN [A-Z ]*PRIVATE KEY|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
    r"AKIA[0-9A-Z]{16}|xoxb-[A-Za-z0-9-]{10,}|apiVersion:\s*v1[\s\S]*kubeconfig)"
)
PASSWORD_ASSIGN = re.compile(r"password\s*[:=]\s*\S", re.IGNORECASE)
# Demo Evidence page positively asserted as the staging acceptance path (a policy violation).
DEMO_AS_ACCEPTANCE = re.compile(
    r"demo evidence[^.\n]{0,60}\b(is|as)\b[^.\n]{0,60}(primary )?staging acceptance", re.IGNORECASE
)

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

    # Formal-page evidence map: each evidence type mapped to its formal page on one line.
    map_lines = [ln.lower() for ln in texts["evidence-map"].splitlines()]
    for evidence, page in EVIDENCE_MAP:
        if not any(evidence in ln and page in ln for ln in map_lines):
            bad(f"evidence map does not map {evidence!r} -> {page!r}")

    # Step 64E stays failed; Step 64F stays blocked.
    if "failed_staging_representativeness" not in low and "failed_operator_validation" not in low:
        bad(
            "docs do not keep Step 64E FAILED_STAGING_REPRESENTATIVENESS/FAILED_OPERATOR_VALIDATION"
        )
    if "step 64f" not in low or "block" not in low:
        bad("docs do not keep Step 64F BLOCKED")
    # Must not self-mark Step 64E as accepted/PASS.
    for name, text in texts.items():
        for line in text.splitlines():
            ll = line.lower()
            if "step 64e" in ll and "overall" in ll and "pass" in ll and "step 64e.4" not in ll:
                if not ("failed" in ll or " not " in ll):
                    bad(f"{name} marks Step 64E as PASS: {line.strip()[:80]}")

    # Demo Evidence page is diagnostic-only, not a staging acceptance path.
    diag_low = texts["diagnostic-only-policy"].lower()
    if "diagnostic" not in diag_low or "staging acceptance" not in diag_low:
        bad("diagnostic-only policy does not declare the Demo Evidence page diagnostic-only")
    if "not" not in diag_low:
        bad("diagnostic-only policy does not negate staging acceptance for the Demo Evidence page")
    for name, text in texts.items():
        for m in DEMO_AS_ACCEPTANCE.finditer(text):
            if "not" not in m.group(0).lower():
                bad(f"{name} treats Demo Evidence page as staging acceptance: {m.group(0)[:80]}")

    # The subordinate plans exist and are named as such.
    if "test" not in texts["test-qa-plan"].lower() or "64e.4b" not in texts["test-qa-plan"].lower():
        bad("test/QA remediation plan does not define the 64E.4B test phase")
    if "64e.4c" not in texts["redeploy-plan"].lower():
        bad("staging redeploy plan does not define the 64E.4C redeploy")
    if "64e.4d" not in texts["rereview-plan"].lower():
        bad("operator re-review plan does not define the 64E.4D re-review")
    for step in ("65a", "65b", "65c", "65d", "65e", "65f"):
        if step not in texts["external-integration-roadmap"].lower():
            bad(f"external integration roadmap missing {step.upper()}")

    # No implementation / no production action; prod_exec 0; safety flags; no secrets.
    for name, text in texts.items():
        tl = text.lower()
        if "no implementation" not in tl:
            bad(f"{name} does not state no implementation is claimed")
        if "no production action" not in tl:
            bad(f"{name} does not state no production action")
        if "production_executed_true_count=0" not in tl:
            bad(f"{name} does not document production_executed_true_count=0")
        for flag in (
            "production-action=false",
            "production-ready=false",
            "staging-only=true",
            "image-push=false",
            "live-integrations=disabled",
        ):
            if flag not in text:
                bad(f"{name} missing safety flag {flag}")
        for forbidden in ("production-action=true", "production-ready=true", "image-push=true"):
            if forbidden in text:
                bad(f"{name} contains forbidden claim {forbidden}")
        if SECRET_SHAPES.search(text):
            bad(f"{name} contains secret-shaped content")
        if PASSWORD_ASSIGN.search(text):
            bad(f"{name} contains a stored password assignment")
        if "p@ssw0rd" in text:
            bad(f"{name} contains a literal password")

    if re.search(r"production_executed_true_count\s*[`]*\s*[:=]?\s*[`]*\s*[1-9]", low):
        bad("production_executed_true_count is non-zero")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    print("  [OK] formal-page evidence map + representativeness/diagnostic policies + test/QA,")
    print("       redeploy, operator re-review, and external integration plans in place;")
    print("       Demo Evidence page diagnostic-only; Step 64E failed, Step 64F blocked;")
    print("       no implementation, no production action, prod_exec=0")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
