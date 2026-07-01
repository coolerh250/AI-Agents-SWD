#!/usr/bin/env python3
"""Step 64E -- operator walkthrough SOP verifier.

Confirms the operator-facing SOP package exists and documents: the SSH tunnel + operator URL,
the demo project / work item, Admin Console navigation, safety checks, known gaps, the
do-not-execute list, troubleshooting, and an acceptance checklist -- while asserting no
production action, live integrations disabled, and production_executed_true_count=0. Asserts no
secret/password/private-key value is committed.

Marker: OPERATOR_WALKTHROUGH_SOP_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "docs" / "staging"

SOP = STAGING / "operator-walkthrough-sop.md"
NAV = STAGING / "operator-admin-console-navigation-guide.md"
DEMO = STAGING / "operator-demo-workflow-review-guide.md"
SAFETY = STAGING / "operator-safety-check-guide.md"
GAPS = STAGING / "operator-known-gaps-and-limitations.md"
DONOT = STAGING / "operator-do-not-execute-list.md"
TROUBLE = STAGING / "operator-access-troubleshooting.md"
ACCEPT = STAGING / "operator-acceptance-checklist.md"

MARKER = "OPERATOR_WALKTHROUGH_SOP_VERIFY"

DOCS = {
    "sop": SOP,
    "nav": NAV,
    "demo": DEMO,
    "safety": SAFETY,
    "gaps": GAPS,
    "donot": DONOT,
    "trouble": TROUBLE,
    "accept": ACCEPT,
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

    # SSH tunnel + operator URL documented (in the SOP at least).
    if "-L 18000:127.0.0.1:18000" not in both:
        bad("SSH local port-forward tunnel command not documented")
    if "localhost:18000/admin" not in low:
        bad("operator URL http://localhost:18000/admin not documented")

    # Demo project + work item documented.
    if "SaaS User Management Module" not in both:
        bad("demo project not documented")
    if "Create user CRUD API" not in both:
        bad("demo work item not documented")

    # Admin Console navigation documented.
    if "admin console" not in NAV.read_text(encoding="utf-8").lower():
        bad("admin console navigation not documented")

    # Known gaps documented (both the PyYAML gap and the delivery gate).
    gaps_low = GAPS.read_text(encoding="utf-8").lower()
    if "yaml" not in gaps_low:
        bad("known gaps do not mention the PyYAML gateway gap")
    if "gated" not in gaps_low and "operator auth" not in gaps_low:
        bad("known gaps do not mention the delivery/release gate")

    # Do-not-execute list present.
    donot_low = DONOT.read_text(encoding="utf-8").lower()
    if "production deploy" not in donot_low or "down -v" not in donot_low:
        bad("do-not-execute list incomplete")

    # Acceptance checklist present (checkbox style).
    if "- [ ]" not in ACCEPT.read_text(encoding="utf-8"):
        bad("acceptance checklist has no checklist items")

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
    print("  [OK] operator walkthrough SOP package complete; SSH tunnel + operator URL + demo")
    print("       review + safety check + known gaps + do-not-execute + acceptance documented;")
    print("       no production action; live integrations disabled; no secret; prod_exec=0")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
