#!/usr/bin/env python3
"""Step 64D -- staging demo workflow verifier.

Confirms the demo workflow evidence (10.0.1.32) is documented: the six demo docs exist, record
the SaaS User Management Module project + Create user CRUD API work item, the Admin Console
evidence, the audit evidence, and delivery evidence (or a documented gap), and assert no
production action, live integrations disabled, and production_executed remains 0. Asserts no
secret/password/private-key value is committed.

Marker: STAGING_DEMO_WORKFLOW_VERIFY: PASS | PASS_WITH_GAPS | FAIL
(The overall result declared in the execution report is echoed.)
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "docs" / "staging"
REPORT = STAGING / "staging-demo-workflow-execution-report.md"
SEED = STAGING / "staging-demo-seed-data.md"
CONSOLE = STAGING / "staging-demo-admin-console-evidence.md"
AUDIT = STAGING / "staging-demo-audit-evidence.md"
DELIVERY = STAGING / "staging-demo-delivery-evidence.md"
GAPS = STAGING / "staging-demo-known-gaps.md"

MARKER = "STAGING_DEMO_WORKFLOW_VERIFY"

DOCS = {
    "report": REPORT,
    "seed": SEED,
    "console": CONSOLE,
    "audit": AUDIT,
    "delivery": DELIVERY,
    "gaps": GAPS,
}

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

    # Demo scenario documented.
    if "SaaS User Management Module" not in both:
        bad("demo project 'SaaS User Management Module' not documented")
    if "Create user CRUD API" not in both:
        bad("demo work item 'Create user CRUD API' not documented")

    # Admin Console evidence documented.
    if "admin console" not in CONSOLE.read_text(encoding="utf-8").lower():
        bad("admin console evidence not documented")
    if "/operations/" not in both:
        bad("Admin Console backing endpoints not documented")

    # Audit evidence documented.
    if "work_item_created" not in AUDIT.read_text(encoding="utf-8"):
        bad("audit evidence (work_item_created) not documented")

    # Delivery evidence or documented gap present.
    deliv = DELIVERY.read_text(encoding="utf-8").lower()
    if "delivery" not in deliv or not ("gap" in deliv or "gated" in deliv or "package" in deliv):
        bad("delivery evidence / gap not documented")

    # Agent pipeline documented in the report.
    rep_low = REPORT.read_text(encoding="utf-8").lower()
    for agent in ("intake", "requirement", "development", "qa", "devops"):
        if agent not in rep_low:
            bad(f"report does not document the {agent} stage")

    # Live integrations disabled + no production action.
    if "live-integrations=disabled" not in both:
        bad("docs do not carry live-integrations=disabled flag")
    if "no production action" not in low:
        bad("docs do not state no production action")

    # Machine-checkable safety flags on every doc.
    for name, text in texts.items():
        for flag in (
            "production-action=false",
            "production-ready=false",
            "staging-only=true",
            "live-integrations=disabled",
        ):
            if flag not in text:
                bad(f"{name} missing safety flag {flag}")
        for forbidden in (
            "production-action=true",
            "production-ready=true",
            "production-deploy=true",
        ):
            if forbidden in text:
                bad(f"{name} contains forbidden claim {forbidden}")

    # No secret material in any committed doc.
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

    # Echo the declared overall result.
    report = texts["report"]
    result = "PASS"
    if re.search(r"overall result:\s*\**pass_with_gaps", report, re.IGNORECASE):
        result = "PASS_WITH_GAPS"
    print("  [OK] demo workflow evidence recorded on 10.0.1.32; SaaS User Management / Create")
    print("       user CRUD API seeded + mock pipeline executed; audit + admin-console evidence;")
    print(
        "       live integrations disabled; no production action; no secret committed; prod_exec=0"
    )
    print(f"{MARKER}: {result}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
