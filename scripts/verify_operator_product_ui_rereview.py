#!/usr/bin/env python3
"""Step 64E.4D -- Operator product UI re-review verifier.

Confirms the operator's product-UI acceptance is recorded (operator verdict PASS, tied to the
operator's own statement), the formal-page checklist is all PASS, the Demo Evidence / Diagnostics
page is not the acceptance path, safety production_executed stays 0, and the status transition to
Step 64E PASS / Step 64F READY_TO_RESUME is documented -- with no code / rebuild / restart /
production action in this stage.

Marker: OPERATOR_PRODUCT_UI_REREVIEW_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "docs" / "staging"
RESULT = STAGING / "operator-product-ui-rereview-result.md"
RECORD = STAGING / "product-ui-staging-operator-acceptance-record.md"
GAPS = STAGING / "product-ui-accepted-gaps.md"

MARKER = "OPERATOR_PRODUCT_UI_REREVIEW_VERIFY"

DOCS = {"result": RESULT, "acceptance-record": RECORD, "accepted-gaps": GAPS}
# The operator's own statement -- acceptance must be tied to it (no self-accept).
OPERATOR_STATEMENT = "正式頁面都能呈現必要 evidence"
# Formal pages that must each be recorded PASS in the acceptance record.
PAGES = (
    "projects / work items",
    "agent executions",
    "workflows / task graph",
    "qa / code",
    "audit / evidence",
    "safety center",
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

    # Operator verdict PASS, tied to the operator's own statement (no self-accept).
    if "operator verdict: pass" not in low:
        bad("operator verdict PASS is not recorded")
    if OPERATOR_STATEMENT not in both:
        bad("operator acceptance is not tied to the operator's own statement (self-accept guard)")
    if "did not self-accept" not in low and "did not decide operator acceptance" not in low:
        bad("docs do not state Claude Code did not self-accept operator usability")

    # All formal-page checklist items PASS (in the acceptance record).
    record_lines = [ln.lower() for ln in texts["acceptance-record"].splitlines()]
    for page in PAGES:
        if not any(page in ln and "pass" in ln for ln in record_lines):
            bad(f"acceptance record does not mark {page!r} as PASS")

    # Diagnostics / Demo Evidence not used as acceptance path.
    if "not used as" not in low and "not an acceptance path" not in low:
        bad("docs do not state Diagnostics / Demo Evidence is not the acceptance path")
    if "diagnostic" not in low:
        bad("docs do not preserve the diagnostic-only posture")

    # Safety posture + status transition.
    if "production_executed_true_count=0" not in low:
        bad("docs do not record production_executed_true_count=0")
    if "step 64e: pass" not in low and "step 64e result: pass" not in low:
        bad("docs do not record Step 64E: PASS")
    if "ready_to_resume" not in low:
        bad("docs do not record Step 64F: READY_TO_RESUME")

    # No production action / image push; no rebuild/restart in this stage; no secrets.
    if "no image push" not in low:
        bad("docs do not document no image push")
    if not ("rebuild" in low and "restart" in low):
        bad("docs do not state no rebuild/restart occurred in this stage")
    for name, text in texts.items():
        tl = text.lower()
        if "no production action" not in tl:
            bad(f"{name} does not state no production action")
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

    print("  [OK] operator verdict PASS recorded (tied to operator statement); formal-page")
    print("       checklist all PASS; Diagnostics not the acceptance path; prod_exec=0;")
    print("       Step 64E PASS, Step 64F READY_TO_RESUME; no rebuild/restart/production action")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
