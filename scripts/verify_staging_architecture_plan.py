#!/usr/bin/env python3
"""Step 64A -- staging architecture & deployment plan verifier.

Planning + inventory only: confirms the docs/staging/ planning set exists, is explicitly
staging-only / non-production, documents the 10.0.1.32 SSH target with interactive-only
credential handling, and never claims production readiness or allows a production action.

Marker: STAGING_ARCHITECTURE_PLAN_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "docs" / "staging"

MARKER = "STAGING_ARCHITECTURE_PLAN_VERIFY"
DOCS = (
    "staging-architecture.md",
    "staging-deployment-plan.md",
    "staging-access-plan.md",
    "staging-scope-and-non-goals.md",
    "staging-service-inventory.md",
    "staging-admin-console-plan.md",
    "staging-demo-workflow-plan.md",
    "staging-information-request.md",
    "staging-risk-and-safety-plan.md",
    "staging-step64-roadmap.md",
)

# Machine-checkable safety flags every staging doc must carry as `=true` / `=false`.
REQUIRED_TRUE = ("staging-only", "non-production")
REQUIRED_FALSE = (
    "production-action",
    "production-deploy",
    "production-sync",
    "production-secret",
    "external-write",
    "github-merge",
    "image-push",
    "production-ready",
    "credential-storage",
)
# Docs that must document the 10.0.1.32 SSH staging target + interactive credential handling.
HOST_DOCS = (
    "staging-access-plan.md",
    "staging-deployment-plan.md",
    "staging-service-inventory.md",
    "staging-information-request.md",
    "staging-risk-and-safety-plan.md",
)

failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def main() -> int:
    for name in DOCS:
        p = STAGING / name
        if not p.is_file():
            bad(f"missing doc: docs/staging/{name}")
            continue
        text = p.read_text(encoding="utf-8")
        low = text.lower()

        # Every doc must carry the staging-only + no-production-action statements.
        if "staging only" not in low:
            bad(f"{name} omits the staging-only statement")
        if "no production action" not in low:
            bad(f"{name} omits the no-production-action statement")

        # Machine-checkable flags.
        for flag in REQUIRED_TRUE:
            if f"{flag}=true" not in text:
                bad(f"{name} missing safety flag {flag}=true")
        for flag in REQUIRED_FALSE:
            if f"{flag}=false" not in text:
                bad(f"{name} missing safety flag {flag}=false")
            if f"{flag}=true" in text:
                bad(f"{name} sets forbidden {flag}=true")

        # Forbidden affirmative claims (machine flags must never assert these).
        for forbidden in (
            "production-ready=true",
            "production-action=true",
            "production-deploy=true",
            "production-sync=true",
            "production-secret=true",
            "external-write=true",
            "github-merge=true",
            "image-push=true",
            "credential-storage=true",
        ):
            if forbidden in text:
                bad(f"{name} contains forbidden claim {forbidden}")

    # Staging target host + SSH + interactive credential handling.
    for name in HOST_DOCS:
        p = STAGING / name
        if not p.is_file():
            continue
        low = p.read_text(encoding="utf-8").lower()
        if "10.0.1.32" not in low:
            bad(f"{name} does not document staging target host 10.0.1.32")
        if "ssh" not in low:
            bad(f"{name} does not document SSH access method")
        if "interactive" not in low:
            bad(f"{name} does not document interactive credential handling")
        if "never stored" not in low and "not stored" not in low:
            bad(f"{name} does not state credentials are never stored")

    # Information request must not hide operator requirements.
    info = STAGING / "staging-information-request.md"
    if info.is_file():
        low = info.read_text(encoding="utf-8").lower()
        for need in (
            "ssh username",
            "sudo",
            "docker",
            "port",
            "browser",
            "port forward",
            "http",
            "github / slack / llm",
            "retention",
            "cleanup",
        ):
            if need not in low:
                bad(f"information request omits operator requirement: {need}")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1
    print(f"  [OK] {len(DOCS)} staging planning docs present; staging-only; 10.0.1.32 SSH target;")
    print("       interactive credential handling; no production action; production-ready=false")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
