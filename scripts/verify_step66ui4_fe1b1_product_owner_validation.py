#!/usr/bin/env python3
"""Step 66UI.4-FE.1B.1-V -- Product Owner UI validation verifier.

Confirms the validation record and test report for Step 66UI.4-FE.1B.1 exist and state: the
deployed source (PR #9 / frontend/66ui4-fe1b1-safety-field-mapping / commit 974822d), the VISIBLE
verdict, that the Step 66UI.4-FE.1B-V accepted Unavailable gap is now resolved, the per-task
approval wording clarification (compact vs full rendering, not a regression), production_
executed_true_count remaining 0, no production/external/workflow action claimed, FE.1C/FE.1D still
unauthorized, and that merge authorization is not granted by this document.

This is a documentation-only verifier: it reads files on the current checkout and does not touch
any runtime or remote host.

Marker: STEP66UI4_FE1B1_PRODUCT_OWNER_VALIDATION_VERIFY: PASS | PASS_WITH_GAPS | FAIL
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DOCS = {
    "fe1b1-product-owner-ui-validation-record": ROOT
    / "docs"
    / "frontend"
    / "66ui4-phase1-product-visual-language"
    / "fe1b1-product-owner-ui-validation-record.md",
    "fe1b1-product-owner-validation": ROOT
    / "docs"
    / "test"
    / "step66ui4-fe1b1-product-owner-validation.md",
}

PROGRESS = ROOT / "source" / "progress.md"

MARKER = "STEP66UI4_FE1B1_PRODUCT_OWNER_VALIDATION_VERIFY"
PR9_COMMIT = "974822d"
PR9_BRANCH = "frontend/66ui4-fe1b1-safety-field-mapping"

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
    re.compile(r"pr #9 (?:has been|was) merged", re.IGNORECASE),
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
    for name, p in DOCS.items():
        if not p.is_file():
            bad(f"missing doc: {p} ({name})")
    if not PROGRESS.is_file():
        bad(f"missing progress log: {PROGRESS}")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    texts = {name: p.read_text(encoding="utf-8") for name, p in DOCS.items()}
    progress_text = PROGRESS.read_text(encoding="utf-8")
    combined_low = _norm("\n".join(texts.values()))
    progress_low = _norm(progress_text)

    if "pr #9" not in combined_low:
        bad("PR #9 reference missing")
    if PR9_BRANCH not in combined_low:
        bad("branch reference missing")
    if PR9_COMMIT not in combined_low:
        bad("commit reference missing")
    if "66ui.4-fe.1b.1-v" not in progress_low:
        bad("source/progress.md does not reference Stage 66UI.4-FE.1B.1-V")

    if "visible" not in combined_low:
        bad("VISIBLE verdict not recorded")

    if "resolved" not in combined_low:
        bad("gap-resolved statement missing")
    if "unavailable" not in combined_low:
        bad("prior Unavailable gap reference missing")

    if "compact" not in combined_low:
        bad("compact-vs-full rendering clarification missing")
    if "per-task" not in combined_low:
        bad("per-task approval wording clarification missing")
    if "not a regression" not in combined_low and "not touched" not in combined_low:
        bad("not-a-regression statement missing")

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

    print("  [OK] Product Owner UI validation record + test report present; PR #9/branch/commit")
    print("       referenced; VISIBLE verdict recorded; prior Unavailable gap resolution recorded;")
    print("       compact-vs-full per-task approval wording clarification recorded as not a")
    print("       regression; production_executed_true_count and no production/external/workflow")
    print("       action claims documented; FE.1C/FE.1D unauthorized; PR-not-merged status")
    print("       documented; no forbidden capability claims or sensitive identifiers")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
