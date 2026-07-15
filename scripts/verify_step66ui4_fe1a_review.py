#!/usr/bin/env python3
"""Step 66UI.4-FE.1A-R -- Visual polish review verifier.

Confirms the Claude Code FE.1A review doc and review record exist and
state: PR #6 / branch / commit references, the FE.1A marker, that
FE.1B/FE.1C/FE.1D remain unauthorized, no backend/API/database/workflow/
infra change claimed, no production/external action claimed, no Delivery/
Reminder real UI claimed, no Pipeline/drag-drop claimed, that the
local-only `.tools/` and unrelated platform-progress doc are confirmed
absent from the PR, and that source/progress.md references this stage.

This is a documentation-only verifier: it reads files on the current
checkout and does not touch any runtime, remote host, or git branch/remote.

Marker: STEP66UI4_FE1A_REVIEW_VERIFY: PASS | PASS_WITH_GAPS | FAIL
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REVIEW_DOCS = {
    "fe1a-claude-code-review": ROOT
    / "docs"
    / "frontend"
    / "66ui4-phase1-product-visual-language"
    / "fe1a-claude-code-review.md",
    "fe1a-review-record": ROOT / "docs" / "test" / "step66ui4-fe1a-review-record.md",
}

PROGRESS_MD = ROOT / "source" / "progress.md"

MARKER = "STEP66UI4_FE1A_REVIEW_VERIFY"

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
    re.compile(r"fe\.1b is authorized", re.IGNORECASE),
    re.compile(r"fe\.1c is authorized", re.IGNORECASE),
    re.compile(r"fe\.1d is authorized", re.IGNORECASE),
    re.compile(r"delivery real ui implemented", re.IGNORECASE),
    re.compile(r"reminder/expiry real ui implemented", re.IGNORECASE),
    re.compile(r"pipeline board implemented", re.IGNORECASE),
    re.compile(r"drag-and-drop implemented", re.IGNORECASE),
    re.compile(r"pr #6 (?:has been|was) merged", re.IGNORECASE),
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
    "remain",
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
    if not PROGRESS_MD.is_file():
        bad(f"missing progress file: {PROGRESS_MD}")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    texts = {name: p.read_text(encoding="utf-8") for name, p in REVIEW_DOCS.items()}
    combined_low = _norm("\n".join(texts.values()))
    progress_text_low = _norm(PROGRESS_MD.read_text(encoding="utf-8"))

    if "pr #6" not in combined_low:
        bad("PR #6 reference missing")
    if "frontend/66ui4-fe1a-visual-polish" not in combined_low:
        bad("branch reference missing")
    if "7e6422f" not in combined_low:
        bad("commit reference missing")

    if MARKER not in "\n".join(texts.values()):
        bad("FE.1A review marker not present verbatim")

    if "66ui4-fe1a-r" not in progress_text_low.replace(".", "-"):
        bad("source/progress.md does not reference Stage 66UI.4-FE.1A-R")
    if (
        "pr #6" not in progress_text_low
        and "frontend/66ui4-fe1a-visual-polish" not in progress_text_low
    ):
        bad("source/progress.md does not reference the FE.1A PR/branch")

    for phrase in ("fe.1b", "fe.1c", "fe.1d"):
        if phrase not in combined_low:
            bad(f"{phrase} not referenced")
    if "unauthorized" not in combined_low:
        bad("FE.1B/FE.1C/FE.1D unauthorized statement missing")

    if "no backend" not in combined_low and "backend changed: no" not in combined_low:
        bad("no-backend-change statement missing")
    if "no api" not in combined_low and "api changed: no" not in combined_low:
        bad("no-API-change statement missing")
    if "no database" not in combined_low and "database changed: no" not in combined_low:
        bad("no-database-change statement missing")
    if "workflow" not in combined_low:
        bad("workflow statement missing")
    if "infra" not in combined_low:
        bad("infra statement missing")

    if "no production action" not in combined_low:
        bad("no-production-action statement missing")
    if "no external action" not in combined_low and "external action" not in combined_low:
        bad("no-external-action statement missing")

    if "delivery real ui" not in combined_low:
        bad("Delivery real UI statement missing")
    if "reminder/expiry real ui" not in combined_low or "reminder" not in combined_low:
        bad("Reminder/Expiry real UI statement missing")
    if "pipeline" not in combined_low:
        bad("Pipeline board statement missing")
    if "drag-and-drop" not in combined_low and "drag/drop" not in combined_low:
        bad("drag-and-drop statement missing")

    if ".tools/" not in combined_low and ".tools" not in combined_low:
        bad(".tools/ exclusion statement missing")
    if "platform-progress-admin-console-proposal" not in combined_low:
        bad("unrelated platform-progress doc exclusion statement missing")

    if not any(
        verdict in "\n".join(texts.values()) for verdict in ("PASS", "PASS_WITH_GAPS", "FAIL")
    ):
        bad("review result verdict (PASS/PASS_WITH_GAPS/FAIL) not stated")

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

    print("  [OK] FE.1A review doc and review record present; PR #6/branch/commit referenced;")
    print("       FE.1A marker present; FE.1B/FE.1C/FE.1D unauthorized statement present; no")
    print("       backend/API/database/workflow/infra change claimed; no production/external")
    print("       action claimed; no Delivery/Reminder/Pipeline/drag-drop claimed; .tools/ and")
    print("       unrelated platform-progress doc confirmed excluded; progress.md updated; no")
    print("       forbidden capability claims or sensitive identifiers found")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
