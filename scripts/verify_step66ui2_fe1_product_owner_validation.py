#!/usr/bin/env python3
"""Step 66UI.2-FE.1-V -- Product Owner UI validation record verifier.

Confirms the Product Owner UI validation record and test report for Step
66UI.2-FE.1 exist, state the VISIBLE_WITH_ACCEPTED_GAP result, record the
Demo Evidence direct-route deferral as an accepted, non-blocking gap, record
the Delivery Package placement conflict as closed, do not claim merge
authorization, and do not claim any runtime/backend/API/database/workflow
change or production/external action.

This is a documentation-only verifier: it reads files on the current
checkout (main) and does not touch the frontend branch, any runtime, or any
remote host.

Marker: STEP66UI2_FE1_PRODUCT_OWNER_VALIDATION_VERIFY: PASS | PASS_WITH_GAPS | FAIL
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REVIEW_DOCS = {
    "product-owner-ui-validation-record": ROOT
    / "docs"
    / "frontend"
    / "66ui2-navigation-ia"
    / "product-owner-ui-validation-record.md",
    "fe1-product-owner-validation": ROOT
    / "docs"
    / "test"
    / "step66ui2-fe1-product-owner-validation.md",
}

MARKER = "STEP66UI2_FE1_PRODUCT_OWNER_VALIDATION_VERIFY"

SECRET_SHAPES = re.compile(
    r"(-----BEGIN [A-Z ]*PRIVATE KEY|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
    r"AKIA[0-9A-Z]{16}|xoxb-[A-Za-z0-9-]{10,}|sk-ant-[A-Za-z0-9_-]{20,})"
)
INFRA_SHAPES = re.compile(r"(10\.0\.1\.31|aiagent-swd|itadmin)", re.IGNORECASE)

FORBIDDEN_CLAIM_PATTERNS = (
    re.compile(r"workflow dispatch is enabled", re.IGNORECASE),
    re.compile(r"workflow resume is enabled", re.IGNORECASE),
    re.compile(r"production action is enabled", re.IGNORECASE),
    re.compile(r"external action is enabled", re.IGNORECASE),
    re.compile(r"merge authorization is granted", re.IGNORECASE),
    re.compile(r"merged into main", re.IGNORECASE),
)
NEGATION_CUES = (
    "no ",
    "not ",
    "never ",
    "cannot ",
    "must not",
    "does not",
    "won't",
    "will not",
    "n't ",
    "without ",
    "prohibit",
)
NEGATION_WINDOW = 160

failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower())


def _unnegated_matches(name: str, text: str) -> list[str]:
    hits = []
    for pattern in FORBIDDEN_CLAIM_PATTERNS:
        for m in pattern.finditer(text):
            start = max(0, m.start() - NEGATION_WINDOW)
            context = text[start : m.start()].lower()
            if any(cue in context for cue in NEGATION_CUES):
                continue
            hits.append(f"{name} contains a forbidden capability claim: {pattern.pattern}")
    return hits


def main() -> int:
    for name, p in REVIEW_DOCS.items():
        if not p.is_file():
            bad(f"missing review doc: {p} ({name})")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    texts = {name: p.read_text(encoding="utf-8") for name, p in REVIEW_DOCS.items()}
    combined_low = _norm("\n".join(texts.values()))

    if "visible_with_accepted_gap" not in combined_low:
        bad("VISIBLE_WITH_ACCEPTED_GAP result not recorded")

    if "demo evidence" not in combined_low or "accepted_deferred_non_blocking" not in combined_low:
        bad("Demo Evidence direct-route deferral not recorded as ACCEPTED_DEFERRED_NON_BLOCKING")

    if "blocks fe.1: no" not in combined_low:
        bad("Demo Evidence gap not recorded as non-blocking to FE.1")

    if "delivery package" not in combined_low or "closed" not in combined_low:
        bad("Delivery Package placement conflict not recorded as closed")

    if "explicit merge authorization still required" not in combined_low:
        bad("Explicit merge-authorization-still-required statement missing")

    if "not yet granted" not in combined_low:
        bad("Merge authorization not explicitly stated as not yet granted")

    for name, text in texts.items():
        text_low = _norm(text)
        if "no runtime code changed" not in text_low and "runtime code changed: no" not in text_low:
            bad(f"{name} missing 'no runtime code changed' statement")
        if "backend changed: no" not in text_low and "no backend changed" not in text_low:
            bad(f"{name} missing 'no backend changed' statement")
        if "database changed: no" not in text_low and "no database changed" not in text_low:
            bad(f"{name} missing 'no database changed' statement")
        if "workflow changed: no" not in text_low and "no workflow" not in text_low:
            bad(f"{name} missing workflow-not-changed statement")
        if "no production action" not in text_low and "production action: no" not in text_low:
            bad(f"{name} missing 'no production action' statement")
        if "no external action" not in text_low and "external action: no" not in text_low:
            bad(f"{name} missing 'no external action' statement")
        if "pr not merged" not in text_low and "does not merge" not in text_low:
            bad(f"{name} missing PR-not-merged statement")

    for name, text in texts.items():
        if SECRET_SHAPES.search(text):
            bad(f"{name} contains secret-shaped content")
        if INFRA_SHAPES.search(text):
            bad(f"{name} contains a real internal infrastructure identifier")
        for hit in _unnegated_matches(name, text):
            bad(hit)

    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    print("  [OK] Product Owner validation record + test report present; VISIBLE_WITH_ACCEPTED_GAP")
    print(
        "       recorded; Demo Evidence deferral accepted-non-blocking; Delivery Package conflict"
    )
    print("       closed; merge authorization explicitly not claimed; no runtime/backend/database/")
    print("       workflow change or production/external action claimed; no sensitive identifiers")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
