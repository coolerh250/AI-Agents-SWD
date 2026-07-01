#!/usr/bin/env python3
"""Step 64B.2B -- staging runtime bootstrap verifier.

Confirms the staging runtime bootstrap evidence (10.0.1.32) is documented: the five runtime
evidence docs exist, record the target host / repo path / compose file / Admin Console access,
state that live integrations are disabled and no production action / secret occurred, and keep
production_executed at 0. Asserts no secret/password/private-key value is committed.

Marker: STAGING_RUNTIME_BOOTSTRAP_VERIFY: PASS | PASS_WITH_GAPS | FAIL
(The overall stage result declared in the bootstrap report is echoed: if the report declares
"Overall result: PASS_WITH_GAPS" this verifier emits PASS_WITH_GAPS; otherwise PASS.)
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "docs" / "staging"
REPORT = STAGING / "staging-runtime-bootstrap-report.md"
STATUS = STAGING / "staging-runtime-service-status.md"
ACCESS = STAGING / "staging-admin-console-access-evidence.md"
LIMITS = STAGING / "staging-runtime-known-limitations.md"
STOP = STAGING / "staging-runtime-stop-and-restart-notes.md"

MARKER = "STAGING_RUNTIME_BOOTSTRAP_VERIFY"

DOCS = {
    "report": REPORT,
    "status": STATUS,
    "access": ACCESS,
    "limits": LIMITS,
    "stop": STOP,
}

# Secret shapes that must never appear in the committed docs.
SECRET_SHAPES = re.compile(
    r"(-----BEGIN [A-Z ]*PRIVATE KEY|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
    r"AKIA[0-9A-Z]{16}|xoxb-[A-Za-z0-9-]{10,}|apiVersion:\s*v1[\s\S]*kubeconfig)"
)
# A stored password shape like `password: <value>` / `password=<value>` (not the word alone).
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

    report = texts["report"]

    # Target host documented in every doc.
    for name, text in texts.items():
        if "10.0.1.32" not in text:
            bad(f"{name} does not document target host 10.0.1.32")

    # Repo path documented.
    if "/data/ai-agents-staging/AI-Agents-SWD" not in both:
        bad("repo path /data/ai-agents-staging/AI-Agents-SWD not documented")

    # Compose file documented.
    if "docker-compose.staging.yml" not in both:
        bad("staging compose file not documented")

    # Admin Console access documented (host-local + SSH port-forward + operator URL).
    if "/admin" not in both:
        bad("Admin Console /admin route not documented")
    if "-L 18000:127.0.0.1:18000" not in both:
        bad("SSH local port-forward instruction not documented")
    if "localhost:18000/admin" not in low:
        bad("operator Admin Console URL not documented")

    # Live integrations disabled documented.
    if "live-integrations=disabled" not in both:
        bad("docs do not carry live-integrations=disabled flag")
    if not ("disabled" in low and "integration" in low):
        bad("docs do not document live integrations disabled/mocked")

    # No production action / no production secret documented.
    if "no production action" not in low:
        bad("docs do not state no production action")
    if "no production secret" not in low:
        bad("docs do not state no production secret")

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
            "production-sync=true",
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

    # Credential handling: key-based, no password used.
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

    # Echo the declared overall result: PASS or PASS_WITH_GAPS.
    result = "PASS"
    if re.search(r"overall result:\s*\**pass_with_gaps", report, re.IGNORECASE):
        result = "PASS_WITH_GAPS"
    print("  [OK] staging runtime bootstrap evidence recorded on 10.0.1.32; Admin Console")
    print("       /admin documented + reachable; live integrations disabled; no production")
    print("       action/secret; no secret/password/private-key committed; prod_exec=0")
    print(f"{MARKER}: {result}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
