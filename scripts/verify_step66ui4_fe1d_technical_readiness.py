#!/usr/bin/env python3
"""Step 66UI.4-FE.1D-TECH-REVIEW -- technical readiness review verifier.

Confirms the technical readiness review doc and test record exist and state: PR #12 branch/commit,
Product Owner context, design-only scope result, frontend-only feasibility classification, open
Product Owner decisions, recommended Codex implementation slicing, forbidden items, the SPA
deep-link fallback exclusion, no backend/API/database/workflow/new-endpoint change claimed, that
Codex and FE.1D implementation remain unauthorized, Local Artifact Reconciliation, and no Windows/
local path exposure.

This is a documentation-only verifier: it reads files on the current checkout and does not touch
any runtime or remote host.

Marker: STEP66UI4_FE1D_TECHNICAL_READINESS_VERIFY: PASS | PASS_WITH_GAPS | FAIL
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DOCS = {
    "fe1d-tech-readiness-review": ROOT
    / "docs"
    / "design"
    / "66ui4-fe1d-navigation-microcopy"
    / "claude-code-technical-readiness-review.md",
    "fe1d-tech-readiness-record": ROOT
    / "docs"
    / "test"
    / "step66ui4-fe1d-technical-readiness-review-record.md",
}

PROGRESS = ROOT / "source" / "progress.md"

MARKER = "STEP66UI4_FE1D_TECHNICAL_READINESS_VERIFY"
PR12_COMMIT = "43269c5"
PR12_BRANCH = "design/66ui4-fe1d-navigation-microcopy"
DESIGN_MARKER = "design66ui4_fe1d_navigation_microcopy_verify: pass"

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
    re.compile(r"pr #12 (?:has been|was) merged", re.IGNORECASE),
    re.compile(r"codex is authorized", re.IGNORECASE),
    re.compile(r"fe\.1d implementation is authorized", re.IGNORECASE),
    re.compile(r"spa deep-link fallback (?:was|is) fixed", re.IGNORECASE),
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
    "remains unauthorized",
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

    if "66ui.4-fe.1d-tech-review" not in progress_low:
        bad("source/progress.md does not reference Stage 66UI.4-FE.1D-TECH-REVIEW")

    if PR12_BRANCH not in combined_low:
        bad("PR #12 branch reference missing")
    if PR12_COMMIT not in combined_low:
        bad("PR #12 commit reference missing")

    if "product owner" not in combined_low or "product owner context" not in combined_low:
        bad("Product Owner context section missing")

    if DESIGN_MARKER not in combined_low:
        bad(
            "FE.1D design marker (DESIGN66UI4_FE1D_NAVIGATION_MICROCOPY_VERIFY: PASS) not referenced"
        )

    if "design-only scope" not in combined_low:
        bad("design-only scope result section missing")

    if "feasibility classification" not in combined_low:
        bad("frontend-only feasibility classification section missing")

    if "open product owner decision" not in combined_low and "open decisions" not in combined_low:
        bad("open Product Owner decisions section missing")

    if "implementation slicing" not in combined_low:
        bad("Codex implementation slicing recommendation missing")

    if "forbidden items" not in combined_low and "forbidden item" not in combined_low:
        bad("forbidden items section missing")

    if (
        "spa deep-link" not in combined_low
        or "known gap" not in combined_low
        and "known platform gap" not in combined_low
    ):
        bad("SPA deep-link fallback exclusion / known-gap reference missing")

    for term in ("backend", "api", "database", "workflow"):
        if (
            not re.search(rf"no [\w/]*{term}", combined_low)
            and f"{term} change" not in combined_low
        ):
            bad(f"no-{term}-change statement missing")
    if not re.search(r"no [\w/]*new endpoint", combined_low) and "new endpoint" not in combined_low:
        bad("no-new-endpoint statement missing")

    if "codex" not in combined_low or (
        "codex remains unauthorized" not in combined_low and "unauthorized" not in combined_low
    ):
        bad("Codex unauthorized statement missing")

    if "fe.1d implementation" not in combined_low or "remains unauthorized" not in combined_low:
        bad("FE.1D implementation unauthorized statement missing")

    if "local artifact reconciliation" not in combined_low:
        bad("Local Artifact Reconciliation section missing")

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

    print(
        "  [OK] FE.1D technical readiness review doc + test record present; PR #12 branch/commit,"
    )
    print("       Product Owner context, design marker, design-only scope, feasibility")
    print("       classification, open decisions, implementation slicing, forbidden items, and SPA")
    print("       deep-link fallback exclusion all recorded; no backend/API/database/workflow/new-")
    print("       endpoint change; Codex and FE.1D implementation remain unauthorized; Local")
    print("       Artifact Reconciliation recorded; no forbidden capability claims or sensitive")
    print("       identifiers")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
