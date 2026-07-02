#!/usr/bin/env python3
"""Step 64E.4C -- Product UI staging redeploy verifier.

Confirms the staging-redeploy docs exist and record: an orchestrator-only rebuild/restart of the
Step 64E.4B tested UI on the staging host, technical validation of the formal-page routes/endpoints,
the Demo Evidence page kept diagnostic-only, and no production action / image push / volume deletion
(production_executed stays 0). Step 64E stays failed/pending operator re-review; Step 64F blocked.

Marker: PRODUCT_UI_STAGING_REDEPLOY_VERIFY: PASS | PASS_WITH_GAPS | FAIL
(The overall result declared in the redeploy report is echoed.)
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "docs" / "staging"
REPORT = STAGING / "product-ui-staging-redeploy-report.md"
TECH = STAGING / "product-ui-staging-technical-validation.md"
EVIDENCE = STAGING / "product-ui-formal-page-staging-evidence.md"
INSTRUCTIONS = STAGING / "product-ui-operator-rereview-instructions.md"
GAPS = STAGING / "product-ui-staging-known-gaps.md"

MARKER = "PRODUCT_UI_STAGING_REDEPLOY_VERIFY"

DOCS = {
    "report": REPORT,
    "technical-validation": TECH,
    "formal-page-evidence": EVIDENCE,
    "operator-rereview-instructions": INSTRUCTIONS,
    "known-gaps": GAPS,
}
# Formal-page evidence types that must appear in the staging evidence doc.
ITEMS = ("wi-0001", "agent execution", "workflow", "qa", "audit", "safety")

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

    # Formal-page evidence types recorded.
    ev_low = texts["formal-page-evidence"].lower()
    for term in ITEMS:
        if term not in ev_low:
            bad(f"formal-page evidence doc does not address: {term}")

    # Redeploy recorded: staging sync + orchestrator-only rebuild/restart + reachable console.
    report_low = texts["report"].lower()
    if (
        "ff-only" not in report_low
        and "fast-forward" not in report_low
        and "44f9a40" not in report_low
    ):
        bad("redeploy report does not document the staging repo sync")
    if "orchestrator" not in report_low:
        bad("redeploy report does not document an orchestrator rebuild/restart")
    if "/health" not in low or "/admin" not in low or "/operations/safety" not in low:
        bad("docs do not record Admin Console reachability (/health, /admin, /operations/safety)")

    # Demo Evidence diagnostic-only preserved (diagnostic + not an acceptance path).
    if "diagnostic" not in low or "not an acceptance path" not in low:
        bad("docs do not preserve the Demo Evidence diagnostic-only posture")

    # Step 64E failed/pending (not PASS); Step 64F blocked.
    if "failed_staging_representativeness" not in low and "pending operator" not in low:
        bad("docs do not keep Step 64E failed/pending operator re-review")
    if "step 64f" not in low or "block" not in low:
        bad("docs do not keep Step 64F BLOCKED")
    for name, text in texts.items():
        for line in text.splitlines():
            ll = line.lower()
            if "step 64e" in ll and "overall" in ll and "pass" in ll and "step 64e.4" not in ll:
                if not ("failed" in ll or " not " in ll or "pending" in ll):
                    bad(f"{name} marks Step 64E as PASS: {line.strip()[:80]}")

    # No image push / volume deletion documented across the set.
    if "no image push" not in low:
        bad("docs do not document no image push")
    if "no volume deletion" not in low and "no volume delete" not in low:
        bad("docs do not document no volume deletion")

    # No production action; prod_exec 0; safety flags; no secrets (per doc).
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

    result = "PASS"
    m = re.search(r"overall result:\s*\**(pass_with_gaps|fail)", texts["report"], re.IGNORECASE)
    if m:
        result = m.group(1).upper()
    print("  [OK] staging synced + orchestrator-only redeploy; formal-page routes/endpoints")
    print("       technically validated; Demo Evidence diagnostic-only; Step 64E pending operator")
    print("       re-review, Step 64F blocked; no production action / image push / volume deletion")
    print(f"{MARKER}: {result}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
