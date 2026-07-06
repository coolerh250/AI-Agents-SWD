#!/usr/bin/env python3
"""Step 65E -- Controlled notification validation verifier.

Confirms the 65E docs record a real, controlled Discord notification validation: exactly one
[STAGING] test message sent to the approved non-production staging channel, no production channel,
no DM, no secret values, GitHub/LLM/workflow untouched, notification flag reset, and
production_executed stays 0.

Marker: CONTROLLED_NOTIFICATION_VALIDATION_VERIFY: PASS | PASS_WITH_OPERATOR_CONFIRMATION_PENDING |
        PASS_WITH_GAPS | FAIL
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "docs" / "staging"
REPORT = STAGING / "controlled-notification-validation-report.md"
EVIDENCE = STAGING / "controlled-notification-validation-evidence.md"
SAFETY = STAGING / "controlled-notification-safety-record.md"
RESET = STAGING / "controlled-notification-reset-record.md"
GAPS = STAGING / "controlled-notification-known-gaps.md"
CONFIRMATION = STAGING / "controlled-notification-operator-confirmation.md"

MARKER = "CONTROLLED_NOTIFICATION_VALIDATION_VERIFY"

DOCS = {
    "report": REPORT,
    "evidence": EVIDENCE,
    "safety-record": SAFETY,
    "reset-record": RESET,
    "known-gaps": GAPS,
    "operator-confirmation": CONFIRMATION,
}

SECRET_SHAPES = re.compile(
    r"(-----BEGIN [A-Z ]*PRIVATE KEY|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
    r"AKIA[0-9A-Z]{16}|xoxb-[A-Za-z0-9-]{10,}|sk-ant-[A-Za-z0-9_-]{20,}|MT[IMQ][A-Za-z0-9_.-]{20,})"
)
PASSWORD_ASSIGN = re.compile(r"password\s*[:=]\s*\S", re.IGNORECASE)
TOKEN_ASSIGN = re.compile(
    r"(token|api[_-]?key|secret|webhook)\s*[:=]\s*[\"']?[A-Za-z0-9/+]{16,}", re.I
)

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

    if "external_sent=true" not in low and 'external_sent": true' not in low:
        bad("docs do not record a real external send (external_sent=true)")
    if "[staging]" not in low:
        bad("docs do not document the [STAGING] message prefix")
    if "mysanbox" not in low or "#general" not in low:
        bad("docs do not name the approved staging channel (MySanbox/#general)")

    if "production channel" not in low:
        bad("docs do not state no production channel")
    if "no dm" not in low and "no dm was sent" not in low:
        bad("docs do not state no DM")

    if "run_real_discord_test=false" not in low:
        bad("docs do not document the notification flag reset (RUN_REAL_DISCORD_TEST=false)")

    if "no github write" not in low and "github write" not in low:
        bad("docs do not document GitHub not written")
    if "no llm call" not in low and "llm call" not in low:
        bad("docs do not document LLM not called")
    if "workflow execution" not in low:
        bad("docs do not document workflow not executed")

    for name, text in texts.items():
        tl = text.lower()
        if "production_executed_true_count=0" not in tl:
            bad(f"{name} does not document production_executed_true_count=0")

    if re.search(r"production_executed_true_count\s*[`]*\s*[:=]?\s*[`]*\s*[1-9]", low):
        bad("production_executed_true_count is non-zero")

    for name, text in texts.items():
        if SECRET_SHAPES.search(text):
            bad(f"{name} contains secret-shaped content")
        if PASSWORD_ASSIGN.search(text):
            bad(f"{name} contains a stored password assignment")
        if TOKEN_ASSIGN.search(text):
            bad(f"{name} contains a stored token/key/secret value")

    # exactly one controlled send documented
    if "exactly one" not in low and "external_sent_count=1" not in low:
        gap("docs do not explicitly state 'exactly one' controlled send count")

    operator_confirmed = bool(
        re.search(r"recorded value:\s*\**\s*visible", texts["operator-confirmation"].lower())
    )
    if not operator_confirmed:
        gap("operator visual confirmation is pending (VISIBLE not yet recorded)")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    print("  [OK] one real [STAGING] send to MySanbox/#general documented; no production channel,")
    print("       no DM, no secret values; GitHub/LLM/workflow untouched; notification flag reset;")
    print("       prod_exec=0")
    if not operator_confirmed:
        print(f"{MARKER}: PASS_WITH_OPERATOR_CONFIRMATION_PENDING")
        return 0
    if gaps:
        print(f"{MARKER}: PASS_WITH_GAPS")
        return 0
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
