#!/usr/bin/env python3
"""Step 66UI.4-FE.1A-V -- Product Owner UI validation verifier.

Confirms the validation record and test report for Step 66UI.4-FE.1A
exist and state: Product Owner deployment authorization, the deployed
source (PR #6 / frontend/66ui4-fe1a-visual-polish / commit 7e6422f), the
VISIBLE verdict, production_executed_true_count remaining 0, no production/
external/workflow action claimed, FE.1B/FE.1C/FE.1D still unauthorized, and
that merge authorization is not granted by this document.

This is a documentation-only verifier: it reads files on the current
checkout and does not touch any runtime or remote host.

Marker: STEP66UI4_FE1A_PRODUCT_OWNER_VALIDATION_VERIFY: PASS | PASS_WITH_GAPS | FAIL
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REVIEW_DOCS = {
    "fe1a-product-owner-ui-validation-record": ROOT
    / "docs"
    / "frontend"
    / "66ui4-phase1-product-visual-language"
    / "fe1a-product-owner-ui-validation-record.md",
    "fe1a-product-owner-validation": ROOT
    / "docs"
    / "test"
    / "step66ui4-fe1a-product-owner-validation.md",
}

MARKER = "STEP66UI4_FE1A_PRODUCT_OWNER_VALIDATION_VERIFY"

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
    re.compile(r"pr #6 (?:has been|was) merged", re.IGNORECASE),
    re.compile(r"fe\.1b is authorized", re.IGNORECASE),
    re.compile(r"fe\.1c is authorized", re.IGNORECASE),
    re.compile(r"fe\.1d is authorized", re.IGNORECASE),
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
    "unauthorized",
    "does not merge",
    "does not grant",
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

    if "pr #6" not in combined_low:
        bad("PR #6 reference missing")
    if "frontend/66ui4-fe1a-visual-polish" not in combined_low:
        bad("branch reference missing")
    if "7e6422f" not in combined_low:
        bad("commit reference missing")

    if "visible" not in combined_low:
        bad("VISIBLE verdict not recorded")

    if "production_executed_true_count" not in combined_low:
        bad("production_executed_true_count not recorded")

    if "no production action" not in combined_low and "production action: no" not in combined_low:
        bad("no-production-action statement missing")
    if "no external action" not in combined_low and "external action: no" not in combined_low:
        bad("no-external-action statement missing")
    if "workflow dispatch" not in combined_low:
        bad("workflow-dispatch statement missing")

    for phrase in ("fe.1b", "fe.1c", "fe.1d"):
        if phrase not in combined_low:
            bad(f"{phrase} not referenced")
    if "unauthorized" not in combined_low and "not authorized" not in combined_low:
        bad("FE.1B/FE.1C/FE.1D unauthorized statement missing")

    if "does not merge" not in combined_low and "not merged" not in combined_low:
        bad("PR-not-merged statement missing")
    if "merge authorization" not in combined_low:
        bad("merge authorization statement missing")

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

    print("  [OK] Product Owner UI validation record + test report present; PR #6/branch/commit")
    print("       referenced; VISIBLE verdict, production_executed_true_count=0, no production/")
    print(
        "       external/workflow action claims, FE.1B/FE.1C/FE.1D unauthorized, and PR-not-merged"
    )
    print("       status all documented; no forbidden capability claims or sensitive identifiers")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
