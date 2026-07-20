#!/usr/bin/env python3
"""Step 66UI.4-FE.1C.1-R -- TaskList query param filter implementation review verifier.

Confirms the review record and full review doc exist and state: the Product Owner authorization,
PR #11 branch/commit reviewed, the Codex implementation marker, valid-status-query review, invalid-
status-query review, one-way-only review, dropdown-sync review, existing taskApi.list() usage, no
backend/API/database/workflow/new-endpoint change, no FE.1D, Local Artifact Reconciliation, no
Windows/local path exposure, and the Product Owner validation recommendation.

This is a documentation-only verifier: it reads files on the current checkout and does not touch
any runtime or remote host.

Marker: STEP66UI4_FE1C1_REVIEW_VERIFY: PASS | PASS_WITH_GAPS | FAIL
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DOCS = {
    "fe1c1-review": ROOT
    / "docs"
    / "frontend"
    / "66ui4-fe1c-overview-attention-first"
    / "tasklist-query-param-filter-review.md",
    "fe1c1-review-record": ROOT
    / "docs"
    / "test"
    / "step66ui4-fe1c1-tasklist-query-param-review-record.md",
}

PROGRESS = ROOT / "source" / "progress.md"

MARKER = "STEP66UI4_FE1C1_REVIEW_VERIFY"
PR11_COMMIT = "cba5dd0"
PR11_BRANCH = "frontend/66ui4-fe1c1-tasklist-query-param"

SECRET_SHAPES = re.compile(
    r"(-----BEGIN [A-Z ]*PRIVATE KEY|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
    r"AKIA[0-9A-Z]{16}|xoxb-[A-Za-z0-9-]{10,}|sk-ant-[A-Za-z0-9_-]{20,})"
)
INFRA_SHAPES = re.compile(r"(10\.0\.1\.31|aiagent-swd|itadmin)", re.IGNORECASE)
WINDOWS_PATH_SHAPE = re.compile(r"[A-Za-z]:[\\/]Users[\\/]", re.IGNORECASE)

FORBIDDEN_CLAIM_PATTERNS = (
    re.compile(r"backend (?:was|is) changed", re.IGNORECASE),
    re.compile(r"api (?:was|is) changed", re.IGNORECASE),
    re.compile(r"database (?:was|is) changed", re.IGNORECASE),
    re.compile(r"workflow (?:was|is) changed", re.IGNORECASE),
    re.compile(r"new endpoint (?:was|is) added", re.IGNORECASE),
    re.compile(r"production action (?:was|is) triggered", re.IGNORECASE),
    re.compile(r"external action (?:was|is) triggered", re.IGNORECASE),
    re.compile(r"pr #11 (?:has been|was) merged", re.IGNORECASE),
    re.compile(r"fe\.1d is authorized", re.IGNORECASE),
    re.compile(r"url (?:was|is) updated", re.IGNORECASE),
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
    "none",
    "does not merge",
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

    if "66ui.4-fe.1c.1-r" not in progress_low:
        bad("source/progress.md does not reference Stage 66UI.4-FE.1C.1-R")

    if PR11_BRANCH not in combined_low:
        bad("PR #11 branch reference missing")
    if PR11_COMMIT not in combined_low:
        bad("PR #11 commit reference missing")

    if "product owner" not in combined_low or "授權" not in "\n".join(texts.values()):
        bad("Product Owner authorization not recorded")

    if "step66ui4_fe1c1_implementation_verify: pass" not in combined_low:
        bad("Codex FE.1C.1 implementation marker not referenced")

    if "blocked" not in combined_low or "clarification_needed" not in combined_low:
        bad("valid status query review not recorded")

    if "unknown" not in combined_low or "invalid" not in combined_low:
        bad("invalid status query review not recorded")

    if "one-way" not in combined_low:
        bad("one-way-only review not recorded")

    if "dropdown" not in combined_low or "sync" not in combined_low:
        bad("dropdown sync review not recorded")

    if "taskapi.list" not in combined_low:
        bad("existing taskApi.list usage not recorded")

    for term in ("backend", "api", "database", "workflow"):
        if (
            not re.search(rf"no [\w/]*{term}", combined_low)
            and f"{term} change" not in combined_low
        ):
            bad(f"no-{term}-change statement missing")
    if not re.search(r"no [\w/]*new endpoint", combined_low) and "new endpoint" not in combined_low:
        bad("no-new-endpoint statement missing")

    if "fe.1d" not in combined_low or (
        "not authorized" not in combined_low and "unauthorized" not in combined_low
    ):
        bad("FE.1D unauthorized statement missing")

    if "local artifact reconciliation" not in combined_low:
        bad("Local Artifact Reconciliation section missing")

    if "product owner validation" not in combined_low or "proceed" not in combined_low:
        bad("Product Owner validation recommendation not recorded")

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

    print("  [OK] FE.1C.1 review doc + review record present; PR #11 branch/commit referenced;")
    print("       Codex implementation marker referenced; valid/invalid status query review,")
    print("       one-way-only, dropdown sync, and existing taskApi.list usage all recorded; no")
    print("       backend/API/database/workflow/new-endpoint change; FE.1D unauthorized; Local")
    print("       Artifact Reconciliation recorded; Product Owner validation recommendation")
    print("       recorded; no forbidden capability claims or sensitive identifiers")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
