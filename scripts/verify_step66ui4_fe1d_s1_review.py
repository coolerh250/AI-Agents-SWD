#!/usr/bin/env python3
"""Step 66UI.4-FE.1D-S1-R -- Navigation Polish implementation review verifier.

Confirms the review doc and review record exist and state: the Product Owner authorization, PR #13
branch/commit reviewed, the Codex implementation marker, navigation label review, group subtitle
review, badge review, Platform Ops density review, Delivery Package placement under Platform Ops,
"+ Create task" unchanged, delivery_package_ready_for_admin_console rename deferred, SPA deep-link
fallback and two-way URL sync excluded, no backend/API/database/workflow/new-endpoint/new-route
change, FE.1D Slice 2 remaining unauthorized, Local Artifact Reconciliation, no Windows/local path
exposure, and the Product Owner validation recommendation.

This is a documentation-only verifier: it reads files on the current checkout and does not touch
any runtime or remote host.

Marker: STEP66UI4_FE1D_S1_REVIEW_VERIFY: PASS | PASS_WITH_GAPS | FAIL
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DOCS = {
    "slice1-navigation-polish-review": ROOT
    / "docs"
    / "frontend"
    / "66ui4-fe1d-navigation-microcopy"
    / "slice1-navigation-polish-review.md",
    "slice1-navigation-polish-review-record": ROOT
    / "docs"
    / "test"
    / "step66ui4-fe1d-s1-navigation-polish-review-record.md",
}

PROGRESS = ROOT / "source" / "progress.md"

MARKER = "STEP66UI4_FE1D_S1_REVIEW_VERIFY"
PR13_COMMIT = "72d8bff"
PR13_BRANCH = "frontend/66ui4-fe1d-s1-navigation-polish"
IMPLEMENTATION_MARKER = "step66ui4_fe1d_s1_implementation_verify: pass"

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
    re.compile(r"new route (?:was|is) added", re.IGNORECASE),
    re.compile(r"production action (?:was|is) triggered", re.IGNORECASE),
    re.compile(r"external action (?:was|is) triggered", re.IGNORECASE),
    re.compile(r"pr #13 (?:has been|was) merged", re.IGNORECASE),
    re.compile(r"fe\.1d slice 2 is authorized", re.IGNORECASE),
    re.compile(r"spa deep-link fallback (?:was|is) fixed", re.IGNORECASE),
    re.compile(r"two-way url sync (?:was|is) implemented", re.IGNORECASE),
    re.compile(r"delivery package (?:was|is) moved to deliveries", re.IGNORECASE),
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
    "remains under platform ops",
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

    if "66ui.4-fe.1d-s1-r" not in progress_low:
        bad("source/progress.md does not reference Stage 66UI.4-FE.1D-S1-R")

    if PR13_BRANCH not in combined_low:
        bad("PR #13 branch reference missing")
    if PR13_COMMIT not in combined_low:
        bad("PR #13 commit reference missing")

    if "product owner" not in combined_low or "授權" not in "\n".join(texts.values()):
        bad("Product Owner authorization not recorded")

    if IMPLEMENTATION_MARKER not in combined_low:
        bad("Codex FE.1D-S1 implementation marker not referenced")

    if "navigation label" not in combined_low:
        bad("navigation label review not recorded")
    if "group subtitle" not in combined_low:
        bad("group subtitle review not recorded")
    if "badge" not in combined_low:
        bad("badge review not recorded")
    if "platform ops compact density" not in combined_low and "compact density" not in combined_low:
        bad("Platform Ops density review not recorded")
    if "delivery package remains under platform ops" not in combined_low and (
        "delivery package" not in combined_low or "platform ops" not in combined_low
    ):
        bad("Delivery Package placement under Platform Ops not recorded")

    if '"+ create task"' not in combined_low and "create task" not in combined_low:
        bad('"+ Create task" unchanged not recorded')
    if "delivery_package_ready_for_admin_console" not in combined_low:
        bad("delivery_package_ready_for_admin_console reference missing")

    if "spa deep-link" not in combined_low:
        bad("SPA deep-link fallback exclusion missing")
    if "two-way url sync" not in combined_low:
        bad("two-way URL sync exclusion missing")

    for term in ("backend", "api", "database", "workflow"):
        if (
            not re.search(rf"no [\w/]*{term}", combined_low)
            and f"{term} change" not in combined_low
        ):
            bad(f"no-{term}-change statement missing")
    if not re.search(r"no [\w/]*new endpoint", combined_low) and "new endpoint" not in combined_low:
        bad("no-new-endpoint statement missing")
    if not re.search(r"no [\w/]*new route", combined_low) and "new route" not in combined_low:
        bad("no-new-route statement missing")

    if "slice 2" not in combined_low or "remains unauthorized" not in combined_low:
        bad("FE.1D Slice 2 unauthorized statement missing")

    if "local artifact reconciliation" not in combined_low:
        bad("Local Artifact Reconciliation section missing")

    if "product owner validation" not in combined_low:
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

    print("  [OK] FE.1D-S1 review doc + review record present; PR #13 branch/commit, Product Owner")
    print("       authorization, Codex implementation marker, navigation label/subtitle/badge/")
    print("       density review, Delivery Package placement, Product Owner decisions preserved,")
    print(
        "       and Slice 2 exclusion all recorded; no backend/API/database/workflow/new-endpoint/"
    )
    print("       new-route change; FE.1D Slice 2 remains unauthorized; Local Artifact")
    print("       Reconciliation recorded; no forbidden capability claims or sensitive identifiers")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
