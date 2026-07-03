#!/usr/bin/env python3
"""Step 65C -- Staging secret & credential setup verifier.

Confirms the credential-setup docs exist and record: the secret-backend choice, the secret
*reference* names (never values) for GitHub / notification / LLM, the safe-default kill switches, and
the masked validation -- while asserting no secret value is present, no integration was enabled, no
external live action occurred, and production_executed stays 0.

Marker: STAGING_SECRET_CREDENTIAL_SETUP_VERIFY: PASS | PASS_WITH_GAPS | FAIL
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "docs" / "staging"
REPORT = STAGING / "staging-secret-credential-setup-report.md"
REFMAP = STAGING / "staging-secret-reference-map.md"
KILLSWITCH = STAGING / "staging-secret-kill-switch-record.md"
VALIDATION = STAGING / "staging-secret-validation-result.md"
GAPS = STAGING / "staging-secret-known-gaps.md"
HANDBACK = STAGING / "staging-secret-operator-handback.md"

MARKER = "STAGING_SECRET_CREDENTIAL_SETUP_VERIFY"

DOCS = {
    "setup-report": REPORT,
    "reference-map": REFMAP,
    "kill-switch-record": KILLSWITCH,
    "validation-result": VALIDATION,
    "known-gaps": GAPS,
    "operator-handback": HANDBACK,
}
# Safe kill-switch defaults that must be documented.
SAFE_FLAGS = (
    "github_dry_run=true",
    "run_real_github_test=false",
    "run_real_discord_test=false",
    "enable_real_llm_network_call=false",
    "llm_provider=mock",
)
# Forbidden live actions must be documented as not performed.
NO_ACTIONS = (
    "no github write",
    "no notification send",
    "no llm call",
    "no workflow execution",
    "no production action",
)

SECRET_SHAPES = re.compile(
    r"(-----BEGIN [A-Z ]*PRIVATE KEY|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
    r"AKIA[0-9A-Z]{16}|xoxb-[A-Za-z0-9-]{10,}|sk-ant-[A-Za-z0-9_-]{20,}|sk-[A-Za-z0-9]{20,})"
)
PASSWORD_ASSIGN = re.compile(r"password\s*[:=]\s*\S", re.IGNORECASE)
# A stored token/key/secret value (12+ chars after =). Reference names / <placeholders> are fine.
TOKEN_ASSIGN = re.compile(
    r"(token|api[_-]?key|secret|webhook)\s*[:=]\s*[\"']?[A-Za-z0-9/+]{12,}", re.I
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
    ref_low = texts["reference-map"].lower()
    kill_low = texts["kill-switch-record"].lower()

    # Secret references documented (names, per integration).
    if "github_token" not in ref_low:
        bad("reference map does not document a GitHub secret reference")
    if "discord_bot_token" not in ref_low:
        bad("reference map does not document a notification secret reference")
    if "anthropic_api_key" not in ref_low and "llm_api_key" not in ref_low:
        bad("reference map does not document an LLM secret reference")
    if "env-file" not in low:
        bad("docs do not document the secret backend (env-file)")

    # Safe kill switches documented.
    for flag in SAFE_FLAGS:
        if flag not in kill_low:
            bad(f"kill-switch record missing safe default: {flag}")

    # No live actions; status.
    for phrase in NO_ACTIONS:
        if phrase not in low:
            bad(f"docs do not state {phrase!r}")

    # Per-doc: no production action / prod_exec 0 / flags / NO SECRET VALUES.
    for name, text in texts.items():
        tl = text.lower()
        if "no production action" not in tl:
            bad(f"{name} does not state no production action")
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
        if TOKEN_ASSIGN.search(text):
            bad(f"{name} contains a stored token/key/secret value")

    if re.search(r"production_executed_true_count\s*[`]*\s*[:=]?\s*[`]*\s*[1-9]", low):
        bad("production_executed_true_count is non-zero")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    # Pending out-of-band secret values -> PASS_WITH_GAPS.
    result = "PASS_WITH_GAPS" if "pending" in low else "PASS"
    print("  [OK] env-file backend; GitHub/notification/LLM references (names only); safe kill")
    print("       switches; no secret values; no integration enabled; no external live action;")
    print("       prod_exec=0")
    print(f"{MARKER}: {result}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
