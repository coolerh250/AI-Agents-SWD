#!/usr/bin/env python3
"""Step 64F.3 -- Controlled orchestrator rebuild/redeploy rehearsal verifier.

Confirms the rehearsal docs exist and record a git ff-only sync + orchestrator-only build + up -d of
the staging runtime, with the forbidden actions (full-stack rebuild / full-stack restart / down /
down -v / teardown / restore / rollback / workflow re-run / image push / production action)
documented as NOT executed, safety preserved (production_executed stays 0), Step 64E PASS and Step
64F REBUILD_REDEPLOY_REHEARSAL_COMPLETED.

Marker: CONTROLLED_ORCHESTRATOR_REBUILD_REDEPLOY_REHEARSAL_VERIFY: PASS | PASS_WITH_GAPS | FAIL
(The overall result declared in the rehearsal report is echoed.)
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "docs" / "staging"
REPORT = STAGING / "deployment-management-rebuild-redeploy-rehearsal-report.md"
EVIDENCE = STAGING / "deployment-management-rebuild-redeploy-before-after-evidence.md"
VALIDATION = STAGING / "deployment-management-rebuild-redeploy-validation-result.md"
GAPS = STAGING / "deployment-management-rebuild-redeploy-known-gaps.md"
SAFETY = STAGING / "deployment-management-rebuild-redeploy-safety-record.md"

MARKER = "CONTROLLED_ORCHESTRATOR_REBUILD_REDEPLOY_REHEARSAL_VERIFY"

DOCS = {
    "report": REPORT,
    "before-after-evidence": EVIDENCE,
    "validation-result": VALIDATION,
    "known-gaps": GAPS,
    "safety-record": SAFETY,
}
# Forbidden actions that must be documented as NOT executed.
NOT_EXECUTED = (
    "no full-stack rebuild",
    "no full-stack restart",
    "no teardown",
    "no restore",
    "no rollback",
    "no workflow re-run",
    "no image push",
    "no production action",
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
    report_low = texts["report"].lower()

    # Orchestrator-only build + redeploy is the documented action.
    if "build orchestrator" not in report_low:
        bad("report does not record the orchestrator-only build command")
    if "up -d orchestrator" not in report_low:
        bad("report does not record the orchestrator-only up -d command")
    if "ff-only" not in low and "fast-forward" not in low:
        bad("docs do not document the git ff-only sync")

    # Forbidden actions documented as NOT executed.
    for phrase in NOT_EXECUTED:
        if phrase not in low:
            bad(f"docs do not state {phrase!r}")
    if "down -v" not in low or "no down and no down -v occurred" not in low:
        bad("docs do not document that down / down -v was not executed")

    # Validation recorded: reachability + safety + no data loss.
    if "/health" not in low or "/admin" not in low or "/operations/safety" not in low:
        bad("docs do not record health/admin/safety validation")
    if "no data loss" not in low:
        bad("docs do not confirm no data loss")

    # Status.
    if "step 64e" not in low or "pass" not in low:
        bad("docs do not record Step 64E: PASS")
    if "rebuild_redeploy_rehearsal_completed" not in low:
        bad("docs do not record Step 64F REBUILD_REDEPLOY_REHEARSAL_COMPLETED")

    # production_executed stays 0 (documented across the set).
    if not any(t in low for t in ("production_executed_true_count=0", "prod_exec=0", "remained 0")):
        bad("docs do not document production_executed_true_count=0")

    # Safety posture per doc; flags; no secrets.
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

    result = "PASS"
    m = re.search(r"overall result:\s*\**(pass_with_gaps|fail)", texts["report"], re.IGNORECASE)
    if m:
        result = m.group(1).upper()
    print("  [OK] orchestrator-only rebuild/redeploy rehearsal recorded; forbidden actions not")
    print("       executed; health/admin/safety validated, no data loss, prod_exec=0; Step 64E")
    print("       PASS, Step 64F REBUILD_REDEPLOY_REHEARSAL_COMPLETED")
    print(f"{MARKER}: {result}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
