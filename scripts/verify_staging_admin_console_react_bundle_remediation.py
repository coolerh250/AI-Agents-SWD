#!/usr/bin/env python3
"""Step 64E.1 -- staging Admin Console React bundle remediation verifier.

Confirms the remediation that builds the full React/Vite Admin Console bundle into the
orchestrator image is documented and code-backed, while asserting that operator re-review is
still required (Step 64E stays failed/pending, Step 64F stays blocked), no production action /
secret occurred, live integrations are disabled, and production_executed stays 0.

Marker: STAGING_ADMIN_CONSOLE_REACT_BUNDLE_REMEDIATION_VERIFY: PASS | FAIL | PASS_WITH_GAPS
(The overall result declared in the remediation report is echoed.)
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "docs" / "staging"
REPORT = STAGING / "staging-admin-console-react-bundle-remediation-report.md"
VALIDATION = STAGING / "staging-admin-console-remediation-validation.md"
REREVIEW = STAGING / "staging-admin-console-operator-rereview-plan.md"
GAPS = STAGING / "staging-admin-console-remediation-known-gaps.md"
DEPLOY_GAP = STAGING / "staging-admin-console-deployment-gap.md"
DOCKERFILE = ROOT / "apps" / "orchestrator" / "Dockerfile"

MARKER = "STAGING_ADMIN_CONSOLE_REACT_BUNDLE_REMEDIATION_VERIFY"

DOCS = {"report": REPORT, "validation": VALIDATION, "rereview": REREVIEW, "gaps": GAPS}

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
    if not DEPLOY_GAP.is_file():
        bad("missing docs/staging/staging-admin-console-deployment-gap.md (must be updated)")
    if not DOCKERFILE.is_file():
        bad("missing apps/orchestrator/Dockerfile")
    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    texts = {name: p.read_text(encoding="utf-8") for name, p in DOCS.items()}
    both = "\n".join(texts.values())
    low = both.lower()
    dockerfile = DOCKERFILE.read_text(encoding="utf-8")
    deploy_gap = DEPLOY_GAP.read_text(encoding="utf-8")

    # Dockerfile actually builds the React/Vite bundle into the image.
    if "admin-console-build" not in dockerfile or "npm run build" not in dockerfile:
        bad("Dockerfile has no Admin Console build stage (npm run build)")
    if "admin_console_static/dist" not in dockerfile:
        bad("Dockerfile does not copy the built bundle into admin_console_static/dist")

    # React/Vite build remediation documented.
    if not ("vite" in low or "react" in low) or "bundle" not in low:
        bad("docs do not document the React/Vite bundle remediation")

    # Static fallback no longer documented as the primary deployed UI.
    if "fallback" not in low:
        bad("docs do not address the static fallback")
    # The deployment-gap doc should now note remediation (not still 'served always').
    if "remediat" not in deploy_gap.lower():
        bad("deployment-gap doc not updated to reference remediation")

    # Step 64E stays failed/pending, Step 64F stays blocked, operator re-review required.
    if "failed_operator_validation" not in low and "pending" not in low:
        bad("docs do not keep Step 64E failed/pending")
    if "step 64f" not in low or "block" not in low:
        bad("docs do not keep Step 64F blocked")
    if "re-review" not in low and "re review" not in low and "rereview" not in low:
        bad("docs do not require operator re-review")
    # Must NOT self-mark Step 64E usable/PASS.
    for name, text in texts.items():
        for line in text.splitlines():
            ll = line.lower()
            if "step 64e" in ll and "overall" in ll and "pass" in ll:
                if "failed_operator_validation" not in ll and " not " not in ll:
                    bad(f"{name} marks Step 64E overall PASS: {line.strip()[:80]}")

    # No production action / secret; live integrations disabled; prod_exec 0.
    if "no production action" not in low:
        bad("docs do not state no production action")
    if "no production secret" not in low:
        bad("docs do not state no production secret")
    if "live-integrations=disabled" not in both:
        bad("docs do not carry live-integrations=disabled flag")

    # Machine-checkable safety flags.
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

    # No secret material.
    for name, text in texts.items():
        if SECRET_SHAPES.search(text):
            bad(f"{name} contains secret-shaped content (private key / token / kubeconfig)")
        if PASSWORD_ASSIGN.search(text):
            bad(f"{name} contains a stored password assignment")
        if "p@ssw0rd" in text:
            bad(f"{name} contains a literal password")

    # production_executed must remain 0.
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
    print("  [OK] Admin Console React/Vite bundle build added to the orchestrator image;")
    print("       operator re-review still required (Step 64E failed/pending, 64F blocked);")
    print("       no production action/secret; no image push; prod_exec=0")
    print(f"{MARKER}: {result}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
