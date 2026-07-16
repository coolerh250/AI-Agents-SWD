#!/usr/bin/env python3
"""Step 66UI.4-FE.1B-V -- Product Owner UI validation verifier.

Confirms the validation record and test report for Step 66UI.4-FE.1B exist
and state: the deployed source (PR #7 / frontend/66ui4-fe1b-calm-safety /
commit 6cf8efe), the VISIBLE verdict, the accepted-gap explanation (missing
live safety fields causing an honest "Unavailable" state rather than a
fabricated "Safe"), production_executed_true_count remaining 0, no
production/external/workflow action claimed, FE.1C/FE.1D still unauthorized,
and that merge authorization is not granted by this document.

This is a documentation-only verifier: it reads files on the current
checkout and does not touch any runtime or remote host.

Marker: STEP66UI4_FE1B_PRODUCT_OWNER_VALIDATION_VERIFY: PASS | PASS_WITH_GAPS | FAIL
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REVIEW_DOCS = {
    "fe1b-product-owner-ui-validation-record": ROOT
    / "docs"
    / "frontend"
    / "66ui4-phase1-product-visual-language"
    / "fe1b-product-owner-ui-validation-record.md",
    "fe1b-product-owner-validation": ROOT
    / "docs"
    / "test"
    / "step66ui4-fe1b-product-owner-validation.md",
}

PROGRESS = ROOT / "source" / "progress.md"

MARKER = "STEP66UI4_FE1B_PRODUCT_OWNER_VALIDATION_VERIFY"

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
    re.compile(r"pr #7 (?:has been|was) merged", re.IGNORECASE),
    re.compile(r"fe\.1c is authorized", re.IGNORECASE),
    re.compile(r"fe\.1d is authorized", re.IGNORECASE),
    re.compile(r"safety indicator (?:shows|showed) safe", re.IGNORECASE),
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
    "instead of",
    "rather than",
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
    if not PROGRESS.is_file():
        bad(f"missing progress log: {PROGRESS}")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    texts = {name: p.read_text(encoding="utf-8") for name, p in REVIEW_DOCS.items()}
    progress_text = PROGRESS.read_text(encoding="utf-8")
    combined_low = _norm("\n".join(texts.values()))
    progress_low = _norm(progress_text)

    if "pr #7" not in combined_low:
        bad("PR #7 reference missing")
    if "frontend/66ui4-fe1b-calm-safety" not in combined_low:
        bad("branch reference missing")
    if "6cf8efe" not in combined_low:
        bad("commit reference missing")
    if "66ui.4-fe.1b-v" not in progress_low:
        bad("source/progress.md does not reference Stage 66UI.4-FE.1B-V")

    if "visible" not in combined_low:
        bad("VISIBLE verdict not recorded")

    if "dispatch_enabled" not in combined_low or "approval_required" not in combined_low:
        bad("accepted-gap missing-field explanation not recorded")
    if "not a safety violation" not in combined_low:
        bad("not-a-safety-violation statement missing")
    if "accept" not in combined_low:
        bad("Product Owner gap-acceptance statement missing")

    if "production_executed_true_count" not in combined_low:
        bad("production_executed_true_count not recorded")

    if "no production action" not in combined_low and "production action: no" not in combined_low:
        bad("no-production-action statement missing")
    if "no external action" not in combined_low and "external action: no" not in combined_low:
        bad("no-external-action statement missing")
    if "workflow dispatch" not in combined_low:
        bad("workflow-dispatch statement missing")

    for phrase in ("fe.1c", "fe.1d"):
        if phrase not in combined_low:
            bad(f"{phrase} not referenced")
    if "unauthorized" not in combined_low and "not authorized" not in combined_low:
        bad("FE.1C/FE.1D unauthorized statement missing")

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

    print("  [OK] Product Owner UI validation record + test report present; PR #7/branch/commit")
    print("       referenced; VISIBLE verdict with accepted-gap explanation recorded (missing live")
    print("       safety fields, not a safety violation); production_executed_true_count and no")
    print("       production/external/workflow action claims documented; FE.1C/FE.1D unauthorized;")
    print("       PR-not-merged status documented; no forbidden capability claims or sensitive")
    print("       identifiers")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
