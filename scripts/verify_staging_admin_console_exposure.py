#!/usr/bin/env python3
"""Step 64C -- staging admin console exposure verifier.

Confirms the Admin Console exposure / operator-access evidence (10.0.1.32) is documented: the
five docs exist, record the target host / operator URL / SSH port-forward method / page
inventory / safety posture, assert no public exposure and live integrations disabled, and keep
production_executed at 0. Asserts no secret/password/private-key value is committed.

Marker: STAGING_ADMIN_CONSOLE_EXPOSURE_VERIFY:
    PASS | PASS_WITH_OPERATOR_CONFIRMATION_PENDING | FAIL
(The overall result declared in the exposure report is echoed.)
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "docs" / "staging"
REPORT = STAGING / "staging-admin-console-exposure-report.md"
ACCESS = STAGING / "staging-operator-access-validation.md"
INVENTORY = STAGING / "staging-admin-console-page-inventory.md"
LOGIN = STAGING / "staging-operator-first-login-guide.md"
GAPS = STAGING / "staging-admin-console-known-gaps.md"

MARKER = "STAGING_ADMIN_CONSOLE_EXPOSURE_VERIFY"

DOCS = {
    "report": REPORT,
    "access": ACCESS,
    "inventory": INVENTORY,
    "login": LOGIN,
    "gaps": GAPS,
}

# Expected Admin Console page groups (spec §6) — must appear in the inventory.
EXPECTED_PAGE_GROUPS = (
    "/safety",
    "/metrics",
    "/production-readiness",
    "/controlled-rollout-review",
    "/release-governance",
    "/backup-dr",
    "/sandbox-github",
)

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

    # Target host documented in every doc.
    for name, text in texts.items():
        if "10.0.1.32" not in text:
            bad(f"{name} does not document target host 10.0.1.32")

    # Operator URL + SSH port-forward documented.
    if "localhost:18000/admin" not in low:
        bad("operator URL http://localhost:18000/admin not documented")
    if "-L 18000:127.0.0.1:18000" not in both:
        bad("SSH local port-forward instruction not documented")

    # Admin Console route documented.
    if "/admin" not in both:
        bad("Admin Console /admin route not documented")

    # Page inventory includes the expected page groups.
    inv = texts["inventory"]
    for route in EXPECTED_PAGE_GROUPS:
        if route not in inv:
            bad(f"page inventory missing expected route {route}")

    # No public exposure documented.
    if "public-exposure=false" not in both:
        bad("docs do not carry public-exposure=false flag")
    if "no public exposure" not in low:
        bad("docs do not state no public exposure")

    # Live integrations disabled documented.
    if "live-integrations=disabled" not in both:
        bad("docs do not carry live-integrations=disabled flag")
    if not ("disabled" in low and "integration" in low):
        bad("docs do not document live integrations disabled/mocked")

    # No production action documented.
    if "no production action" not in low:
        bad("docs do not state no production action")

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

    # Credential handling: key-based.
    if "key-based" not in low:
        bad("docs do not document key-based SSH access")

    # production_executed must remain 0.
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
    if re.search(
        r"overall result:\s*\**pass_with_operator_confirmation_pending", report, re.IGNORECASE
    ):
        result = "PASS_WITH_OPERATOR_CONFIRMATION_PENDING"
    print("  [OK] admin console exposure evidence recorded on 10.0.1.32; operator URL + SSH")
    print("       port-forward documented; no public exposure; live integrations disabled;")
    print("       no production action; no secret/password/private-key committed; prod_exec=0")
    print(f"{MARKER}: {result}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
