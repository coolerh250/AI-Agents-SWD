#!/usr/bin/env python3
"""Step 65I -- Staging functional acceptance report verifier.

Confirms the 65I acceptance docs consolidate the whole Step 65 track (GitHub / Discord / LLM-with-
governance-gap / fresh-E2E / failure-governance), record the operator-visible evidence, classify all
remaining gaps, present the PASS / PASS_WITH_ACCEPTED_GAPS / FAIL operator decision options, keep
staging acceptance separate from production readiness, and assert Claude Code does not decide the
verdict -- with no new execution / external / production action (production_executed stays 0).

Marker: STAGING_FUNCTIONAL_ACCEPTANCE_REPORT_VERIFY: PASS | PASS_WITH_GAPS | FAIL
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "docs" / "staging"
REPORT = STAGING / "staging-functional-acceptance-report.md"
EVIDENCE = STAGING / "staging-functional-acceptance-evidence-summary.md"
GAPS = STAGING / "staging-functional-acceptance-gap-register.md"
DECISION = STAGING / "staging-functional-acceptance-decision-template.md"
PROD_SEP = STAGING / "staging-functional-acceptance-production-readiness-separation.md"
NEXT = STAGING / "staging-functional-acceptance-next-actions.md"

MARKER = "STAGING_FUNCTIONAL_ACCEPTANCE_REPORT_VERIFY"

DOCS = {
    "acceptance-report": REPORT,
    "evidence-summary": EVIDENCE,
    "gap-register": GAPS,
    "decision-template": DECISION,
    "production-readiness-separation": PROD_SEP,
    "next-actions": NEXT,
}

SECRET_SHAPES = re.compile(
    r"(-----BEGIN [A-Z ]*PRIVATE KEY|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
    r"AKIA[0-9A-Z]{16}|xoxb-[A-Za-z0-9-]{10,}|sk-ant-[A-Za-z0-9_-]{20,})"
)
PASSWORD_ASSIGN = re.compile(r"password\s*[:=]\s*\S", re.IGNORECASE)
TOKEN_ASSIGN = re.compile(
    r"(token|api[_-]?key|secret|webhook)\s*[:=]\s*[\"']?[A-Za-z0-9/+]{16,}", re.I
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
    low = "\n".join(texts.values()).lower()

    # All Step 65 stages summarized.
    for stage in ("65a", "65b", "65c", "65d", "65e", "65f", "65g", "65h"):
        if stage not in low:
            bad(f"docs do not summarize stage {stage.upper()}")

    # Integration + E2E + failure/governance results.
    if "github sandbox" not in low or "validated" not in low:
        bad("docs do not document GitHub validated")
    if "discord" not in low:
        bad("docs do not document Discord validated")
    if "validated_with_governance_gap" not in low and "governance gap" not in low:
        bad("docs do not document the LLM governance gap")
    if "fresh" not in low or "e2e" not in low:
        bad("docs do not document fresh E2E validated")
    if "completed_with_gaps" not in low:
        bad("docs do not document failure/governance COMPLETED_WITH_GAPS")

    # Operator-visible evidence.
    if "operator" not in low or "visible" not in low:
        bad("docs do not document operator-visible evidence")

    # Gap classification.
    for cls in (
        "accepted_staging_gap",
        "operator_ux_gap",
        "production_readiness_gap",
        "deferred_scope",
    ):
        if cls not in low:
            bad(f"docs do not include gap class {cls.upper()}")

    # Decision options + production-readiness separation.
    if "pass_with_accepted_gaps" not in low or "fail" not in low:
        bad("docs do not present the PASS / PASS_WITH_ACCEPTED_GAPS / FAIL options")
    if "production readiness" not in low or "not production readiness" not in low:
        bad("docs do not separate staging acceptance from production readiness")
    if "claude code does not decide" not in low and "does not choose" not in low:
        bad("docs do not state Claude Code must not decide the final verdict")

    # This-stage posture.
    if "no new workflow" not in low:
        bad("docs do not state no new workflow execution")
    if "no external action" not in low and "no external" not in low:
        bad("docs do not state no external action")
    if "no production action" not in low:
        bad("docs do not state no production action")

    for name, text in texts.items():
        tl = text.lower()
        if "production_executed_true_count=0" not in tl:
            bad(f"{name} does not document production_executed_true_count=0")

    if re.search(r"production_executed_true_count\s*[`]*\s*[:=]?\s*[`]*\s*[1-9]", low):
        bad("production_executed_true_count is non-zero")

    for name, text in texts.items():
        if SECRET_SHAPES.search(text):
            bad(f"{name} contains secret-shaped content")
        if PASSWORD_ASSIGN.search(text):
            bad(f"{name} contains a stored password assignment")
        if TOKEN_ASSIGN.search(text):
            bad(f"{name} contains a stored token/key/secret value")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    print("  [OK] Step 65 track consolidated (GitHub/Discord/LLM-gov-gap/E2E/failure-governance);")
    print("       operator-visible evidence; gaps classified (no blocking); PASS/PWG/FAIL options;")
    print("       staging vs production separated; Claude Code does not decide; prod_exec=0")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
