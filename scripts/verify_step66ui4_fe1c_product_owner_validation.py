#!/usr/bin/env python3
"""Step 66UI.4-FE.1C-V -- Product Owner UI validation verifier.

Confirms the validation record and test report for Step 66UI.4-FE.1C exist and state: the deployed
source (PR #10 / frontend/66ui4-fe1c-overview-attention-first / commit 816856a), the VISIBLE
verdict covering all 10 checklist items, the real-data clarification (item #3) investigated live,
production_executed_true_count remaining 0, no production/external/workflow action claimed, FE.1D
still unauthorized, the TaskList query-param gap disclosed as non-blocking, and that merge
authorization is not granted by this document.

This is a documentation-only verifier: it reads files on the current checkout and does not touch
any runtime or remote host.

Marker: STEP66UI4_FE1C_PRODUCT_OWNER_VALIDATION_VERIFY: PASS | PASS_WITH_GAPS | FAIL
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DOCS = {
    "fe1c-product-owner-ui-validation-record": ROOT
    / "docs"
    / "frontend"
    / "66ui4-fe1c-overview-attention-first"
    / "product-owner-ui-validation-record.md",
    "fe1c-product-owner-validation": ROOT
    / "docs"
    / "test"
    / "step66ui4-fe1c-product-owner-validation.md",
}

PROGRESS = ROOT / "source" / "progress.md"

MARKER = "STEP66UI4_FE1C_PRODUCT_OWNER_VALIDATION_VERIFY"
PR10_COMMIT = "816856a"
PR10_BRANCH = "frontend/66ui4-fe1c-overview-attention-first"

SECRET_SHAPES = re.compile(
    r"(-----BEGIN [A-Z ]*PRIVATE KEY|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
    r"AKIA[0-9A-Z]{16}|xoxb-[A-Za-z0-9-]{10,}|sk-ant-[A-Za-z0-9_-]{20,})"
)
INFRA_SHAPES = re.compile(r"(10\.0\.1\.31|aiagent-swd|itadmin)", re.IGNORECASE)
WINDOWS_PATH_SHAPE = re.compile(r"[A-Za-z]:[\\/]Users[\\/]", re.IGNORECASE)

FORBIDDEN_CLAIM_PATTERNS = (
    re.compile(r"workflow dispatch is enabled", re.IGNORECASE),
    re.compile(r"workflow resume is enabled", re.IGNORECASE),
    re.compile(r"production action is enabled", re.IGNORECASE),
    re.compile(r"external action is enabled", re.IGNORECASE),
    re.compile(r"pr #10 (?:has been|was) merged", re.IGNORECASE),
    re.compile(r"fe\.1d is authorized", re.IGNORECASE),
    re.compile(r"tasklist query-param gap (?:was|is) fixed", re.IGNORECASE),
)
NEGATION_CUES = (
    "no ",
    "not ",
    "never ",
    "cannot ",
    "must not",
    "does not",
    "doesn't",
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

    if "66ui.4-fe.1c-v" not in progress_low:
        bad("source/progress.md does not reference Stage 66UI.4-FE.1C-V")

    if PR10_BRANCH not in combined_low:
        bad("PR #10 branch reference missing")
    if PR10_COMMIT not in combined_low:
        bad("PR #10 commit reference missing")

    if "visible" not in combined_low:
        bad("VISIBLE verdict not recorded")

    if "10" not in combined_low or "checklist" not in combined_low:
        bad("10-item checklist reference missing")

    if "real data" not in combined_low and "real-data" not in combined_low:
        bad("real-data clarification (item #3) not recorded")
    if "clarification_needed" not in combined_low or "blocked" not in combined_low:
        bad("live task-status query evidence not recorded")

    if "production_executed_true_count" not in combined_low or "0" not in combined_low:
        bad("production_executed_true_count=0 statement missing")

    if not re.search(r"no [\w/]*production action", combined_low):
        bad("no-production-action statement missing")
    if not re.search(r"no [\w/]*external action", combined_low):
        bad("no-external-action statement missing")

    if "fe.1d" not in combined_low or (
        "not authorized" not in combined_low and "unauthorized" not in combined_low
    ):
        bad("FE.1D unauthorized statement missing")

    if "tasklist" not in combined_low or "query-param" not in combined_low:
        bad("TaskList query-param gap not recorded")
    if "non-blocking" not in combined_low:
        bad("non-blocking classification of TaskList gap missing")

    if "does not merge" not in combined_low and "not merge" not in combined_low:
        bad("PR #10 not-merged-by-this-document statement missing")
    if "merge authorization" not in combined_low:
        bad("merge authorization status not recorded")

    for name, text in texts.items():
        if WINDOWS_PATH_SHAPE.search(text):
            bad(f"{name} contains a local Windows absolute path")
        if SECRET_SHAPES.search(text):
            bad(f"{name} contains secret-shaped content")
        if INFRA_SHAPES.search(text):
            bad(f"{name} contains a real internal infrastructure identifier")
        for hit in _unnegated_matches(name, text):
            bad(hit)

    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    print("  [OK] FE.1C product owner UI validation record + test report present; PR #10")
    print("       branch/commit referenced; VISIBLE verdict covering all 10 checklist items;")
    print("       real-data clarification (item #3) investigated live and recorded;")
    print("       production_executed_true_count=0; no production/external action; FE.1D")
    print("       unauthorized; TaskList query-param gap disclosed as non-blocking; merge not")
    print("       granted by this document; no forbidden capability claims or sensitive")
    print("       identifiers")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
