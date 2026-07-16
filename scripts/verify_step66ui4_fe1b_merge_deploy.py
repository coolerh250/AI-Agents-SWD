#!/usr/bin/env python3
"""Step 66UI.4-FE.1B-MD -- FE.1B merge + merged-main test-deployment verifier.

Confirms the merge record and merged-main test-deployment record for Step
66UI.4-FE.1B exist and state: the PR #7 merge to main, the merge commit, the
Product Owner VISIBLE-with-accepted-gap validation preceding it, the Safety
badge Unavailable accepted gap, that FE.1C/FE.1D remain unauthorized, that
FE.1B.1 Safety Field Mapping Calibration is recommended but not implemented,
that the deployment source is merged main (not the PR branch), that runtime
posture is test-runtime-only, that no backend/API/database/workflow change
is claimed, that no production/external action is claimed, and that
production_executed_true_count remains 0.

This is a documentation-only verifier: it reads files on the current
checkout and does not touch any runtime or remote host.

Marker: STEP66UI4_FE1B_MERGE_DEPLOY_VERIFY: PASS | PASS_WITH_GAPS | FAIL
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DOCS = {
    "fe1b-merge-record": ROOT
    / "docs"
    / "frontend"
    / "66ui4-phase1-product-visual-language"
    / "fe1b-merge-record.md",
    "fe1b-merged-main-test-deployment-record": ROOT
    / "docs"
    / "test"
    / "step66ui4-fe1b-merged-main-test-deployment-record.md",
}

PROGRESS = ROOT / "source" / "progress.md"

MARKER = "STEP66UI4_FE1B_MERGE_DEPLOY_VERIFY"
MERGE_COMMIT = "5a2bc4e"

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
    re.compile(r"fe\.1c is authorized", re.IGNORECASE),
    re.compile(r"fe\.1d is authorized", re.IGNORECASE),
    re.compile(r"deployed from (?:the )?pr branch", re.IGNORECASE),
    re.compile(r"gap (?:was|is) fixed", re.IGNORECASE),
    re.compile(r"safety badge (?:now|currently) shows safe", re.IGNORECASE),
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

    if "pr #7" not in combined_low:
        bad("PR #7 reference missing")
    if "frontend/66ui4-fe1b-calm-safety" not in combined_low:
        bad("branch reference missing")
    if MERGE_COMMIT not in combined_low:
        bad("merge commit reference missing")
    if "66ui.4-fe.1b-md" not in progress_low:
        bad("source/progress.md does not reference Stage 66UI.4-FE.1B-MD")

    if "visible" not in combined_low:
        bad("Product Owner VISIBLE validation not referenced")
    if "accepted" not in combined_low:
        bad("accepted-gap statement missing")

    if "dispatch_enabled" not in combined_low or "approval_required" not in combined_low:
        bad("Safety badge Unavailable accepted-gap field list missing")
    if "unavailable" not in combined_low:
        bad("Safety badge Unavailable state not referenced")

    for phrase in ("fe.1c", "fe.1d"):
        if phrase not in combined_low:
            bad(f"{phrase} not referenced")
    if "unauthorized" not in combined_low and "not authorized" not in combined_low:
        bad("FE.1C/FE.1D unauthorized statement missing")

    if "fe.1b.1" not in combined_low:
        bad("FE.1B.1 Safety Field Mapping Calibration recommendation missing")
    if "not fixed" not in combined_low and "not implemented" not in combined_low:
        bad("FE.1B.1-not-implemented-here statement missing")

    if "merged main" not in combined_low:
        bad("deployment-source-is-merged-main statement missing")
    if "pr branch" not in combined_low:
        bad("not-deployed-from-pr-branch statement missing")

    if "test runtime" not in combined_low and "test-runtime" not in combined_low:
        bad("test-runtime-only runtime posture statement missing")

    for term in ("backend", "api", "database", "workflow"):
        if not re.search(rf"no [\w/]*{term}", combined_low):
            bad(f"no-{term}-change statement missing")

    if not re.search(r"no [\w/]*production action", combined_low):
        bad("no-production-action statement missing")
    if not re.search(r"no [\w/]*external action", combined_low):
        bad("no-external-action statement missing")

    if "production_executed_true_count" not in combined_low:
        bad("production_executed_true_count not recorded")
    if "remained `0" not in combined_low and "0` before and after" not in combined_low:
        bad("production_executed_true_count=0 before/after statement missing")

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

    print("  [OK] FE.1B merge record + merged-main test-deployment record present; PR #7/branch/")
    print("       merge commit referenced; Product Owner VISIBLE-with-accepted-gap validation and")
    print("       Safety badge Unavailable gap documented; FE.1C/FE.1D unauthorized; FE.1B.1")
    print("       recommended but not implemented; deployment source is merged main (not PR")
    print("       branch); test-runtime-only posture; no backend/API/database/workflow change; no")
    print("       production/external action; production_executed_true_count=0; no forbidden")
    print("       capability claims or sensitive identifiers")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
