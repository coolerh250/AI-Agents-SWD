#!/usr/bin/env python3
"""Step 64E.4B -- Product UI integration fix (test/QA) verifier.

Confirms the formal Admin Console product pages are code-wired to surface each demo-evidence type
(so acceptance no longer depends on the diagnostic Demo Evidence page), the test/QA docs exist, the
Demo Evidence page is kept diagnostic-only, and nothing claims a staging redeploy / image rebuild /
restart / production action (production_executed stays 0).

Marker: PRODUCT_UI_INTEGRATION_FIX_TEST_VERIFY: PASS | PASS_WITH_GAPS | FAIL
(The overall result declared in the test report is echoed.)
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "docs" / "staging"
REPORT = STAGING / "product-ui-integration-fix-test-report.md"
MATRIX = STAGING / "product-ui-formal-page-validation-matrix.md"
EVIDENCE = STAGING / "product-ui-test-qa-evidence.md"
GAPS = STAGING / "product-ui-known-gaps-before-staging-redeploy.md"

APP = ROOT / "apps" / "admin-console" / "src" / "App.tsx"
NAV = ROOT / "apps" / "admin-console" / "src" / "components" / "Nav.tsx"
PAGES = ROOT / "apps" / "admin-console" / "src" / "pages"
AGENT = PAGES / "AgentExecutions.tsx"
QACODE = PAGES / "QaCode.tsx"
AUDIT = PAGES / "AuditEvidence.tsx"
TASKGRAPH = PAGES / "TaskGraph.tsx"
SAFETY = PAGES / "SafetyCenter.tsx"
DELIVERY = PAGES / "MultiProjectDelivery.tsx"

MARKER = "PRODUCT_UI_INTEGRATION_FIX_TEST_VERIFY"

DOCS = {"report": REPORT, "matrix": MATRIX, "evidence": EVIDENCE, "gaps": GAPS}
# Evidence types that must be addressed on formal pages (per the validation matrix).
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
    for label, p in (
        ("AgentExecutions page", AGENT),
        ("QaCode page", QACODE),
        ("AuditEvidence page", AUDIT),
        ("App.tsx", APP),
        ("Nav.tsx", NAV),
    ):
        if not p.is_file():
            bad(f"missing source file: {label}")
    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    texts = {name: p.read_text(encoding="utf-8") for name, p in DOCS.items()}
    both = "\n".join(texts.values())
    low = both.lower()
    matrix_low = texts["matrix"].lower()

    # All evidence types addressed on formal pages (validation matrix).
    for term in ITEMS:
        if term not in matrix_low:
            bad(f"validation matrix does not address evidence type: {term}")

    # Code-backed: formal pages exist, wired to the read-only endpoints, and routed.
    app = APP.read_text(encoding="utf-8")
    for route in ("/agent-executions", "/qa-code", "/audit-evidence"):
        if route not in app:
            bad(f"App.tsx missing route {route}")
    agent = AGENT.read_text(encoding="utf-8")
    if "getAgentExecutions" not in agent:
        bad("AgentExecutions page does not call getAgentExecutions")
    qac = QACODE.read_text(encoding="utf-8")
    if "getQaRuns" not in qac or "getCodeWorkspaces" not in qac:
        bad("QaCode page does not call getQaRuns/getCodeWorkspaces")
    aud = AUDIT.read_text(encoding="utf-8")
    if "getDeliveryWorkItemEvents" not in aud:
        bad("AuditEvidence page does not call getDeliveryWorkItemEvents")
    if "getWorkflows" not in TASKGRAPH.read_text(encoding="utf-8"):
        bad("TaskGraph page does not render workflows (getWorkflows)")
    if "production_executed_true_count" not in SAFETY.read_text(encoding="utf-8"):
        bad("SafetyCenter page does not surface production_executed_true_count")
    delivery = DELIVERY.read_text(encoding="utf-8")
    if "loadItems" not in delivery or "list[0]" not in delivery:
        bad("MultiProjectDelivery does not auto-load the first project's work items")

    # Demo Evidence page kept diagnostic-only: labelled a Diagnostic and listed last in nav.
    nav = NAV.read_text(encoding="utf-8")
    demo_lines = [ln for ln in nav.splitlines() if "/demo-evidence" in ln]
    if not demo_lines or "diagnostic" not in demo_lines[0].lower():
        bad("Nav.tsx does not label /demo-evidence as a Diagnostic")
    last_route = re.findall(r'to:\s*"([^"]+)"', nav)
    if not last_route or last_route[-1] != "/demo-evidence":
        bad("Nav.tsx does not list /demo-evidence last (diagnostic-only placement)")
    if "diagnostic" not in low or "not" not in low:
        bad("docs do not preserve the Demo Evidence diagnostic-only posture")

    # Step 64E failed; Step 64F blocked.
    if "failed_staging_representativeness" not in low and "failed_operator_validation" not in low:
        bad("docs do not keep Step 64E failed")
    if "step 64f" not in low or "block" not in low:
        bad("docs do not keep Step 64F BLOCKED")

    # No staging redeploy / image rebuild / restart / production action claimed.
    for name, text in texts.items():
        tl = text.lower()
        if "no staging redeploy" not in tl:
            bad(f"{name} does not state no staging redeploy occurred")
        if "no image rebuild" not in tl:
            bad(f"{name} does not state no image rebuild occurred")
        if "no container restart" not in tl:
            bad(f"{name} does not state no container restart occurred")
        if "no production action" not in tl:
            bad(f"{name} does not state no production action occurred")
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
    print(
        "  [OK] formal pages wired to demo evidence (WI-0001/agent/workflow/qa-code/audit/safety);"
    )
    print("       Demo Evidence diagnostic-only (labelled + last); test/QA docs present;")
    print("       no staging redeploy / rebuild / restart / production action; prod_exec=0")
    print(f"{MARKER}: {result}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
