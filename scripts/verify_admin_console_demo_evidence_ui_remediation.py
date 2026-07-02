#!/usr/bin/env python3
"""Step 64E.3B -- Admin Console demo-evidence UI remediation verifier.

Confirms the remediation docs + code addressing all five demo-evidence items exist and are
code-backed (Demo Evidence page + route + the two read-only endpoints), while asserting operator
re-review is still required (Step 64E stays failed, Step 64F blocked), no production action, and
production_executed stays 0.

Marker: ADMIN_CONSOLE_DEMO_EVIDENCE_UI_REMEDIATION_VERIFY: PASS | PASS_WITH_GAPS | FAIL
(The overall result declared in the remediation report is echoed.)
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "docs" / "staging"
REPORT = STAGING / "admin-console-demo-evidence-ui-remediation-report.md"
VALIDATION = STAGING / "admin-console-demo-evidence-ui-validation.md"
CHECKLIST = STAGING / "admin-console-demo-evidence-operator-rereview-checklist.md"
GAPS = STAGING / "admin-console-demo-evidence-known-gaps-after-remediation.md"

PAGE = ROOT / "apps" / "admin-console" / "src" / "pages" / "DemoEvidence.tsx"
APP = ROOT / "apps" / "admin-console" / "src" / "App.tsx"
NAV = ROOT / "apps" / "admin-console" / "src" / "components" / "Nav.tsx"
OPS = ROOT / "apps" / "orchestrator" / "src" / "operations.py"

MARKER = "ADMIN_CONSOLE_DEMO_EVIDENCE_UI_REMEDIATION_VERIFY"

DOCS = {"report": REPORT, "validation": VALIDATION, "checklist": CHECKLIST, "gaps": GAPS}

# The five evidence types must each be addressed in the remediation report.
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
    for label, p in (
        ("DemoEvidence page", PAGE),
        ("App.tsx", APP),
        ("Nav.tsx", NAV),
        ("operations.py", OPS),
    ):
        if not p.is_file():
            bad(f"missing source file: {label}")
    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    texts = {name: p.read_text(encoding="utf-8") for name, p in DOCS.items()}
    both = "\n".join(texts.values())
    low = both.lower()
    report_low = texts["report"].lower()

    # All five evidence types addressed in the remediation report.
    for term in ITEMS:
        if term not in report_low:
            bad(f"remediation report does not address item: {term}")

    # Code-backed: Demo Evidence page + route + nav + the two endpoints.
    if "/demo-evidence" not in APP.read_text(encoding="utf-8"):
        bad("App.tsx has no /demo-evidence route")
    if "Demo Evidence" not in NAV.read_text(encoding="utf-8"):
        bad("Nav.tsx has no Demo Evidence nav entry")
    ops = OPS.read_text(encoding="utf-8")
    if "/agent-executions" not in ops or "/workflows" not in ops:
        bad("operations.py missing the read-only agent-executions/workflows endpoints")
    page = PAGE.read_text(encoding="utf-8")
    for getter in (
        "getAgentExecutions",
        "getWorkflows",
        "getQaRuns",
        "getCodeWorkspaces",
        "getDeliveryWorkItems",
    ):
        if getter not in page:
            bad(f"DemoEvidence page does not use {getter}")

    # Operator re-review required; Step 64E failed; Step 64F blocked.
    if "re-review" not in low and "rereview" not in low:
        bad("docs do not require operator re-review")
    if "failed_operator_validation" not in low:
        bad("docs do not keep Step 64E FAILED_OPERATOR_VALIDATION")
    if "step 64f" not in low or "block" not in low:
        bad("docs do not keep Step 64F BLOCKED")
    # Must not self-mark Step 64E PASS.
    for name, text in texts.items():
        for line in text.splitlines():
            ll = line.lower()
            if "step 64e" in ll and "overall" in ll and "pass" in ll and "step 64e.3" not in ll:
                allowed = "failed" in ll or " not " in ll or "pass_with_gaps" in ll
                if not allowed:
                    bad(f"{name} marks Step 64E as PASS: {line.strip()[:80]}")

    # No production action; live integrations disabled; no image push; prod_exec 0.
    if "no production action" not in low:
        bad("docs do not state no production action")
    if "live-integrations=disabled" not in both:
        bad("docs do not carry live-integrations=disabled flag")

    for name, text in texts.items():
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

    if "production_executed_true_count" not in low:
        bad("docs do not state production_executed_true_count posture")
    if re.search(r"production_executed_true_count\s*[`]*\s*[:=]?\s*[`]*\s*[1-9]", low):
        bad("production_executed_true_count is non-zero")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    result = "PASS"
    m = re.search(r"overall result:\s*\**(pass_with_gaps|fail)", texts["report"], re.IGNORECASE)
    if m:
        result = m.group(1).upper()
    print("  [OK] Demo Evidence page + route + nav + read-only endpoints in place; all five items")
    print("       addressed; operator re-review required (Step 64E failed, 64F blocked);")
    print("       no production action; no image push; prod_exec=0")
    print(f"{MARKER}: {result}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
