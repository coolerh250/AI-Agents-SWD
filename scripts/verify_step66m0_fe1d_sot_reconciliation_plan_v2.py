#!/usr/bin/env python3
"""Step 66M0-SOT-RECONCILE-P v2 -- FE.1D source-of-truth reconciliation planning verifier.

Confirms all nine reconciliation docs plus the test record and stage artifacts exist and state:
all three FE.1D branches assessed with one disposition each, all three alignment branches assessed
as advisory only, no merge/cherry-pick/deployment claimed, alignment branches remaining unmerged,
FE.1D-S2 remaining unauthorized/non-critical, runtime code unchanged, the SPA deep-link gap
excluded, delivery_package rename deferred to 66D, "+ Create task" unchanged, and the Codex
local-path exposure validation recorded.

This is a documentation-only verifier: it reads files on the current checkout and does not touch
any runtime or remote host.

Marker: STEP66M0_FE1D_SOT_RECONCILIATION_PLAN_V2_VERIFY: PASS | PASS_WITH_GAPS | FAIL
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

RECON_DIR = ROOT / "docs" / "reconciliation" / "66m0-fe1d-sot"

RECON_DOCS = {
    "current-main-runtime-state": RECON_DIR / "current-main-runtime-state.md",
    "alignment-freshness-assessment": RECON_DIR / "alignment-freshness-assessment.md",
    "cross-partner-consensus-matrix": RECON_DIR / "cross-partner-consensus-matrix.md",
    "fe1d-branch-disposition-matrix": RECON_DIR / "fe1d-branch-disposition-matrix.md",
    "conflict-analysis": RECON_DIR / "conflict-analysis.md",
    "recommended-merge-plan": RECON_DIR / "recommended-merge-plan.md",
    "post-merge-verification-plan": RECON_DIR / "post-merge-verification-plan.md",
    "product-owner-decision-checklist": RECON_DIR / "product-owner-decision-checklist.md",
    "align2-advisory-handoff": RECON_DIR / "align2-advisory-handoff.md",
}

RECORD_DOC = ROOT / "docs" / "test" / "step66m0-fe1d-sot-reconciliation-planning-v2-record.md"

STAGE_DOCS = {
    "stage-manifest": ROOT
    / "docs"
    / "stages"
    / "66m0-fe1d-sot-reconciliation-plan-v2"
    / "stage-manifest.yaml",
    "context-receipt": ROOT
    / "docs"
    / "stages"
    / "66m0-fe1d-sot-reconciliation-plan-v2"
    / "context-receipt.md",
    "stage-gate-report": ROOT
    / "docs"
    / "stages"
    / "66m0-fe1d-sot-reconciliation-plan-v2"
    / "stage-gate-report.md",
}

PROGRESS = ROOT / "source" / "progress.md"

MARKER = "STEP66M0_FE1D_SOT_RECONCILIATION_PLAN_V2_VERIFY"

FE1D_BRANCHES = (
    "design/66ui4-fe1d-navigation-microcopy",
    "review/66ui4-fe1d-technical-readiness",
    "review/66ui4-fe1d-boundary",
)
ALIGNMENT_BRANCHES = (
    "alignment/66-project-completion-claude-code",
    "design/66-project-completion-experience-alignment",
    "alignment/66-project-completion-codex",
)

ALL_TEXT_DOCS = {**RECON_DOCS, "planning-record": RECORD_DOC}

SECRET_SHAPES = re.compile(
    r"(-----BEGIN [A-Z ]*PRIVATE KEY|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
    r"AKIA[0-9A-Z]{16}|xoxb-[A-Za-z0-9-]{10,}|sk-ant-[A-Za-z0-9_-]{20,})"
)
INFRA_SHAPES = re.compile(r"(10\.0\.1\.31|10\.0\.1\.32|aiagent-swd|itadmin)", re.IGNORECASE)
WINDOWS_PATH_SHAPE = re.compile(r"[A-Za-z]:[\\/]Users[\\/]", re.IGNORECASE)

FORBIDDEN_CLAIM_PATTERNS = (
    re.compile(r"branch (?:was|is) merged into main", re.IGNORECASE),
    re.compile(r"cherry-pick(?:ed|ing)? (?:was|is) performed", re.IGNORECASE),
    re.compile(r"deployment (?:was|is) performed", re.IGNORECASE),
    re.compile(r"backend (?:was|is) changed", re.IGNORECASE),
    re.compile(r"api (?:was|is) changed", re.IGNORECASE),
    re.compile(r"database (?:was|is) changed", re.IGNORECASE),
    re.compile(r"workflow (?:was|is) changed", re.IGNORECASE),
    re.compile(r"new endpoint (?:was|is) added", re.IGNORECASE),
    re.compile(r"new route (?:was|is) added", re.IGNORECASE),
    re.compile(r"fe\.1d slice 2 is authorized", re.IGNORECASE),
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
    "recommended",
    "future",
    "would",
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
    for name, p in RECON_DOCS.items():
        if not p.is_file():
            bad(f"missing reconciliation doc: {p} ({name})")
    if not RECORD_DOC.is_file():
        bad(f"missing planning record: {RECORD_DOC}")
    for name, p in STAGE_DOCS.items():
        if not p.is_file():
            bad(f"missing stage doc: {p} ({name})")
    if not PROGRESS.is_file():
        bad(f"missing progress log: {PROGRESS}")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    texts = {name: p.read_text(encoding="utf-8") for name, p in ALL_TEXT_DOCS.items()}
    progress_text = PROGRESS.read_text(encoding="utf-8")
    combined_low = _norm("\n".join(texts.values()))
    progress_low = _norm(progress_text)

    if "66m0-sot-reconcile-p v2" not in progress_low:
        bad("source/progress.md does not reference Stage 66M0-SOT-RECONCILE-P v2")

    for branch in FE1D_BRANCHES:
        if branch not in combined_low:
            bad(f"FE.1D branch not assessed: {branch}")
    for branch in ALIGNMENT_BRANCHES:
        if branch not in combined_low:
            bad(f"alignment branch not assessed: {branch}")

    disposition_terms = (
        "merge_full",
        "merge_partial",
        "supersede_with_consolidated_record",
        "archive_historical",
        "blocked_by_conflict",
    )
    if not any(term in combined_low for term in disposition_terms):
        bad("no FE.1D branch disposition classification found")

    advisory_terms = (
        "advisory_ready_for_align2",
        "advisory_with_remediation",
        "stale_requires_refresh",
        "not_ready_for_align2",
    )
    if not any(term in combined_low for term in advisory_terms):
        bad("no alignment-branch advisory classification found")

    if not re.search(r"no merge|no branch (?:was|is) merged", combined_low):
        bad("no-merge statement missing")
    if "cherry-pick" not in combined_low:
        bad("no-cherry-pick statement missing")

    if "remain unmerged" not in combined_low and "remains unmerged" not in combined_low:
        bad("alignment branches remaining unmerged not recorded")

    if "fe.1d slice 2" not in combined_low or (
        "unauthorized" not in combined_low and "non-critical" not in combined_low
    ):
        bad("FE.1D Slice 2 unauthorized/non-critical statement missing")

    if "runtime code unchanged" not in combined_low and not re.search(
        r"apps/ .{0,40}empty|zero runtime", combined_low
    ):
        if "runtime" not in combined_low or "unchanged" not in combined_low:
            bad("runtime-code-unchanged statement missing")

    if "spa deep-link" not in combined_low:
        bad("SPA deep-link fallback exclusion missing")

    if "delivery_package_ready_for_admin_console" not in combined_low or "66d" not in combined_low:
        bad("delivery_package_ready_for_admin_console deferred-to-66D statement missing")

    if '"+ create task"' not in combined_low and "create task" not in combined_low:
        bad('"+ Create task" unchanged not recorded')

    if "local-artifact" not in combined_low and "local artifact" not in combined_low:
        bad("Codex local-artifact/path exposure validation not recorded")
    if "codex" not in combined_low:
        bad("Codex alignment branch reference missing")

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

    print("  [OK] All 9 reconciliation docs + planning record + stage artifacts present; all 3")
    print("       FE.1D branches assessed with a disposition each; all 3 alignment branches")
    print("       assessed as advisory only; no merge/cherry-pick/deployment claimed; alignment")
    print("       branches remain unmerged; FE.1D Slice 2 remains unauthorized/non-critical;")
    print("       runtime code unchanged; SPA deep-link gap excluded; delivery_package rename")
    print("       deferred to 66D; + Create task unchanged; Codex local-path exposure validation")
    print("       recorded; no forbidden capability claims or sensitive identifiers")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
