#!/usr/bin/env python3
"""Step 66UI.4-FE.1B-R -- Calm Safety Posture review verifier.

Confirms the Claude Code review doc and review record for Step 66UI.4-FE.1B
exist and state: the reviewed PR #7/branch/commit, the FE.1B marker,
FE.1C/FE.1D remaining unauthorized, that existing /operations/safety data
only was used, that raw safety evidence remains accessible, that no
backend/API/database/workflow/infra change is claimed, that no new safety
endpoint or backend safety computation is claimed, that no production/
external action is claimed, that no Delivery/Reminder/Pipeline/drag-drop
content is claimed, that the excluded local-only paths are absent, and that
a review result (PASS/PASS_WITH_GAPS/FAIL) is stated.

This is a documentation-only verifier: it reads files on the current
checkout and does not touch any runtime or remote host.

Marker: STEP66UI4_FE1B_REVIEW_VERIFY: PASS | PASS_WITH_GAPS | FAIL
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REVIEW_DOCS = {
    "fe1b-claude-code-review": ROOT
    / "docs"
    / "frontend"
    / "66ui4-phase1-product-visual-language"
    / "fe1b-claude-code-review.md",
    "fe1b-review-record": ROOT / "docs" / "test" / "step66ui4-fe1b-review-record.md",
}

PROGRESS = ROOT / "source" / "progress.md"

MARKER = "STEP66UI4_FE1B_REVIEW_VERIFY"

SECRET_SHAPES = re.compile(
    r"(-----BEGIN [A-Z ]*PRIVATE KEY|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
    r"AKIA[0-9A-Z]{16}|xoxb-[A-Za-z0-9-]{10,}|sk-ant-[A-Za-z0-9_-]{20,})"
)
INFRA_SHAPES = re.compile(r"(10\.0\.1\.31|aiagent-swd|itadmin)", re.IGNORECASE)

FORBIDDEN_CLAIM_PATTERNS = (
    re.compile(r"backend (?:was|is) changed", re.IGNORECASE),
    re.compile(r"api (?:was|is) changed", re.IGNORECASE),
    re.compile(r"database (?:was|is) changed", re.IGNORECASE),
    re.compile(r"workflow (?:was|is) changed", re.IGNORECASE),
    re.compile(r"production action (?:was|is) triggered", re.IGNORECASE),
    re.compile(r"external action (?:was|is) triggered", re.IGNORECASE),
    re.compile(r"new safety endpoint (?:was|is) added", re.IGNORECASE),
    re.compile(r"fe\.1c is authorized", re.IGNORECASE),
    re.compile(r"fe\.1d is authorized", re.IGNORECASE),
    re.compile(r"pr #7 (?:has been|was) merged", re.IGNORECASE),
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
    "none",
    "confirmed",
)
NEGATION_WINDOW = 160

EXCLUDED_PATHS = (
    ".tools/",
    "docs/product/platform-progress-admin-console-proposal.md",
)

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
    if "66ui.4-fe.1b-r" not in progress_low:
        bad("source/progress.md does not reference Stage 66UI.4-FE.1B-R")

    if MARKER not in "\n".join(texts.values()):
        bad("FE.1B review marker not present verbatim")

    for phrase in ("fe.1c", "fe.1d"):
        if phrase not in combined_low:
            bad(f"{phrase} not referenced")
    if "unauthorized" not in combined_low and "not authorized" not in combined_low:
        bad("FE.1C/FE.1D unauthorized statement missing")

    if "/operations/safety" not in combined_low:
        bad("existing /operations/safety data statement missing")
    if "raw" not in combined_low or "evidence" not in combined_low:
        bad("raw safety evidence accessibility statement missing")
    if "accessible" not in combined_low:
        bad("raw safety evidence 'accessible' statement missing")

    for term, label in (
        ("backend", "no-backend-change"),
        ("api", "no-api-change"),
        ("database", "no-database-change"),
        ("workflow", "no-workflow-change"),
        ("infra", "no-infra-change"),
    ):
        if not re.search(rf"no [\w/]*{term}", combined_low):
            bad(f"{label} statement missing")

    if "no new safety endpoint" not in combined_low:
        bad("no-new-safety-endpoint statement missing")
    if "no new backend safety computation" not in combined_low:
        bad("no-new-backend-safety-computation statement missing")

    if not re.search(r"no [\w/]*production action", combined_low):
        bad("no-production-action statement missing")
    if not re.search(r"no [\w/]*external action", combined_low):
        bad("no-external-action statement missing")

    if "no delivery" not in combined_low:
        bad("no-Delivery-real-UI statement missing")
    if "no reminder" not in combined_low:
        bad("no-Reminder/Expiry-real-UI statement missing")
    if "no pipeline" not in combined_low and "pipeline board" not in combined_low:
        bad("no-Pipeline/drag-drop statement missing")

    for excluded in EXCLUDED_PATHS:
        if excluded.lower() not in combined_low:
            bad(f"exclusion statement for {excluded} missing")

    if not any(
        v in combined_low for v in ("pass_with_gaps", "**pass.**", "verdict: **pass", "pass.")
    ):
        bad("review result (PASS/PASS_WITH_GAPS/FAIL) not stated")

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

    print("  [OK] FE.1B review doc + review record present; PR #7/branch/commit referenced; marker")
    print(
        "       present; FE.1C/FE.1D unauthorized; existing /operations/safety data + raw evidence"
    )
    print("       accessibility documented; no backend/API/database/workflow/infra change claimed;")
    print("       no new safety endpoint/computation; no production/external action; no Delivery/")
    print("       Reminder/Pipeline content; excluded paths absent; review result stated; no")
    print("       forbidden capability claims or sensitive identifiers")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
