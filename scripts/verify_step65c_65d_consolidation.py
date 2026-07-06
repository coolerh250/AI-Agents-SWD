#!/usr/bin/env python3
"""Step 65D-C -- 65C / 65D integration status consolidation verifier.

Confirms the consolidation docs reconcile Step 65C (PASS_WITH_GAPS) and Step 65D (PASS), record the
GitHub sandbox as validated with its token gap resolved, keep notification/LLM pending 65E/65F, and
assert no new external mutation and no secret values (production_executed stays 0).

Marker: STEP65C_65D_CONSOLIDATION_VERIFY: PASS | PASS_WITH_GAPS | FAIL
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "docs" / "staging"
CONSOLIDATION = STAGING / "step65c-65d-integration-status-consolidation.md"
GAP_MAP = STAGING / "step65c-65d-gap-closure-map.md"
SAFETY = STAGING / "step65c-65d-current-safety-posture.md"
NEXT_GATES = STAGING / "step65c-65d-next-gates.md"

MARKER = "STEP65C_65D_CONSOLIDATION_VERIFY"

DOCS = {
    "consolidation": CONSOLIDATION,
    "gap-closure-map": GAP_MAP,
    "current-safety-posture": SAFETY,
    "next-gates": NEXT_GATES,
}

SECRET_SHAPES = re.compile(
    r"(-----BEGIN [A-Z ]*PRIVATE KEY|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
    r"AKIA[0-9A-Z]{16}|xoxb-[A-Za-z0-9-]{10,}|sk-ant-[A-Za-z0-9_-]{20,})"
)
PASSWORD_ASSIGN = re.compile(r"password\s*[:=]\s*\S", re.IGNORECASE)
TOKEN_ASSIGN = re.compile(
    r"(token|api[_-]?key|secret|webhook)\s*[:=]\s*[\"']?[A-Za-z0-9/+]{16,}", re.I
)

# (needle, human message) required somewhere across the four docs (lowercased match).
REQUIRED = [
    ("step 65c: pass_with_gaps", "Step 65C PASS_WITH_GAPS not documented"),
    ("step 65d: pass", "Step 65D PASS not documented"),
    ("github sandbox integration: validated", "GitHub sandbox VALIDATED not documented"),
    ("notification integration: pending_65e", "notification PENDING_65E not documented"),
    ("llm integration: pending_65f", "LLM PENDING_65F not documented"),
    ("github sandbox token gap: resolved_by_65d", "GitHub token gap resolution not documented"),
    ("no full 65d-r", "no-full-65D-R statement not documented"),
    ("no new external write", "no-new-external-write not documented"),
    ("no notification send", "no-notification-send not documented"),
    ("no llm call", "no-LLM-call not documented"),
    ("no production action", "no-production-action not documented"),
    ("no secret values", "no-secret-values not documented"),
    ("production_executed_true_count=0", "production_executed_true_count=0 not documented"),
]

failures: list[str] = []
gaps: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def gap(m: str) -> None:
    gaps.append(m)
    print(f"  [GAP] {m}")


def main() -> int:
    for name, p in DOCS.items():
        if not p.is_file():
            bad(f"missing doc: docs/staging/{p.name} ({name})")
    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    texts = {name: p.read_text(encoding="utf-8") for name, p in DOCS.items()}
    low = "\n".join(texts.values()).lower()

    for needle, msg in REQUIRED:
        if needle not in low:
            bad(msg)

    # No new GitHub write must be explicit somewhere.
    if "no new github write" not in low and "no new external write" not in low:
        bad("no-new-GitHub-write not documented")

    # Discord/LLM references tracked as present-but-not-validated (a tracked gap, not a failure).
    if "configured reference present / not yet validated" not in low:
        gap(
            "Discord/LLM references not explicitly marked 'configured reference present / not yet "
            "validated' (tracked)"
        )

    # No secret values anywhere.
    for name, text in texts.items():
        if SECRET_SHAPES.search(text):
            bad(f"{name} contains secret-shaped content")
        if PASSWORD_ASSIGN.search(text):
            bad(f"{name} contains a stored password assignment")
        if TOKEN_ASSIGN.search(text):
            bad(f"{name} contains a stored token/key/secret value")

    # Safety flags present; forbidden true-claims absent.
    for name, text in texts.items():
        for flag in ("production-action=false", "github-merge=false", "image-push=false"):
            if flag not in text:
                bad(f"{name} missing safety flag {flag}")
        for forbidden in ("production-action=true", "github-merge=true", "image-push=true"):
            if forbidden in text:
                bad(f"{name} contains forbidden claim {forbidden}")

    # production_executed must never be recorded non-zero.
    if re.search(r"production_executed_true_count\s*[`]*\s*[:=]?\s*[`]*\s*[1-9]", low):
        bad("production_executed_true_count is non-zero")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    print("  [OK] 65C (PASS_WITH_GAPS) + 65D (PASS) consolidated; GitHub sandbox validated (token")
    print("       gap resolved); notification/LLM pending 65E/65F; no new external write, no")
    print("       notification send, no LLM call, no production action; prod_exec=0; no secrets")
    if gaps:
        print(f"{MARKER}: PASS_WITH_GAPS")
        return 0
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
