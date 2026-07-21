#!/usr/bin/env python3
"""Step 66M0-SOT-RECONCILE-M -- merge and close FE.1D source-of-truth gap verifier.

Confirms the source-of-truth closure record, merge execution record, Team RBAC decision record,
and test record all exist and state: all three FE.1D branches merged with source/merge commits
recorded, FE.1D design/technical-readiness/boundary docs present on main, FE.1D-S1 COMPLETE/SHIPPED,
FE.1D-S2 UNAUTHORIZED/NON-CRITICAL, "+ Create task" unchanged, delivery_package_ready_for_admin_
console rename deferred to 66D, workflow dispatch wording kept, SPA deep-link fallback and two-way
URL sync excluded, Team RBAC M3/M6/M7 ownership recorded, alignment branches remain unmerged, no
runtime/backend/API/DB/workflow change claimed, no deployment claimed, no Step 66C.4-P start
claimed, source/progress.md updated, and the runtime-code vs. repository-record commit distinction
preserved.

This is a documentation-only verifier: it reads files on the current checkout and does not touch
any runtime or remote host.

Marker: STEP66M0_FE1D_SOT_RECONCILIATION_MERGE_VERIFY: PASS | PASS_WITH_GAPS | FAIL
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

RECONCILIATION_DOCS = {
    "source-of-truth-closure-record": ROOT
    / "docs"
    / "reconciliation"
    / "66m0-fe1d-sot"
    / "source-of-truth-closure-record.md",
    "merge-execution-record": ROOT
    / "docs"
    / "reconciliation"
    / "66m0-fe1d-sot"
    / "merge-execution-record.md",
}

TEAM_RBAC_DECISION = ROOT / "docs" / "decisions" / "66-team-rbac-milestone-ownership.md"
TEST_RECORD = ROOT / "docs" / "test" / "step66m0-fe1d-sot-reconciliation-merge-record.md"
SOT_RECORD = ROOT / "docs" / "design" / "66ui-source-of-truth-record.md"

STAGE_DOCS = {
    "stage-manifest": ROOT
    / "docs"
    / "stages"
    / "66m0-fe1d-sot-reconciliation-merge"
    / "stage-manifest.yaml",
    "context-receipt": ROOT
    / "docs"
    / "stages"
    / "66m0-fe1d-sot-reconciliation-merge"
    / "context-receipt.md",
    "stage-gate-report": ROOT
    / "docs"
    / "stages"
    / "66m0-fe1d-sot-reconciliation-merge"
    / "stage-gate-report.md",
}

MERGED_FE1D_DOCS = [
    ROOT / "docs" / "design" / "66ui4-fe1d-navigation-microcopy" / "design-brief.md",
    ROOT
    / "docs"
    / "design"
    / "66ui4-fe1d-navigation-microcopy"
    / "claude-code-technical-readiness-review.md",
    ROOT
    / "docs"
    / "contracts"
    / "66ui4-fe1d-navigation-microcopy"
    / "codex-implementation-boundary.md",
]

PROGRESS = ROOT / "source" / "progress.md"

MARKER = "STEP66M0_FE1D_SOT_RECONCILIATION_MERGE_VERIFY"

DESIGN_SOURCE_COMMIT = "43269c5"
TECH_REVIEW_SOURCE_COMMIT = "25309ea"
BOUNDARY_SOURCE_COMMIT = "9e9a622"
DESIGN_MERGE_COMMIT = "45da561"
TECH_REVIEW_MERGE_COMMIT = "03318b7"
BOUNDARY_MERGE_COMMIT = "0414343"
RUNTIME_CODE_COMMIT = "513f190"
PRE_MERGE_MAIN_COMMIT = "690b700"

ALIGNMENT_BRANCH_NAMES = (
    "alignment/66-project-completion-claude-code",
    "design/66-project-completion-experience-alignment",
    "alignment/66-project-completion-codex",
)

ALL_TEXT_DOCS = {
    **RECONCILIATION_DOCS,
    "team-rbac-decision": TEAM_RBAC_DECISION,
    "test-record": TEST_RECORD,
}

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
    re.compile(r"deployment (?:was|is) performed", re.IGNORECASE),
    re.compile(r"fe\.1d slice 2 is authorized", re.IGNORECASE),
    re.compile(r"step 66c\.4-p (?:has been|was) started", re.IGNORECASE),
    re.compile(r"alignment branch(?:es)? (?:was|were|is|are) merged", re.IGNORECASE),
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
    "remain unmerged",
    "remains unmerged",
    "neither",
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
    for name, p in RECONCILIATION_DOCS.items():
        if not p.is_file():
            bad(f"missing reconciliation doc: {p} ({name})")
    if not TEAM_RBAC_DECISION.is_file():
        bad(f"missing Team RBAC decision record: {TEAM_RBAC_DECISION}")
    if not TEST_RECORD.is_file():
        bad(f"missing test record: {TEST_RECORD}")
    if not SOT_RECORD.is_file():
        bad(f"missing UI source-of-truth record: {SOT_RECORD}")
    for name, p in STAGE_DOCS.items():
        if not p.is_file():
            bad(f"missing stage doc: {p} ({name})")
    for p in MERGED_FE1D_DOCS:
        if not p.is_file():
            bad(f"missing merged FE.1D artifact on main: {p}")
    if not PROGRESS.is_file():
        bad(f"missing progress log: {PROGRESS}")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    texts = {name: p.read_text(encoding="utf-8") for name, p in ALL_TEXT_DOCS.items()}
    sot_record_text = SOT_RECORD.read_text(encoding="utf-8")
    progress_text = PROGRESS.read_text(encoding="utf-8")
    combined_low = _norm("\n".join(texts.values()) + "\n" + sot_record_text)
    progress_low = _norm(progress_text)

    # 1-3: all three branches recorded as merged, with source and merge commits.
    for label, source_commit, merge_commit in (
        ("design", DESIGN_SOURCE_COMMIT, DESIGN_MERGE_COMMIT),
        ("technical readiness", TECH_REVIEW_SOURCE_COMMIT, TECH_REVIEW_MERGE_COMMIT),
        ("boundary", BOUNDARY_SOURCE_COMMIT, BOUNDARY_MERGE_COMMIT),
    ):
        if source_commit not in combined_low:
            bad(f"{label} branch source commit {source_commit} not recorded")
        if merge_commit not in combined_low:
            bad(f"{label} branch merge commit {merge_commit} not recorded")
    if "merged" not in combined_low:
        bad("no branch recorded as merged")

    # 4-6: FE.1D design/technical-readiness/boundary docs exist on main (checked above via
    # MERGED_FE1D_DOCS; also require closure record to name each).
    if "design" not in combined_low or "technical readiness" not in combined_low:
        bad("design or technical readiness disposition not recorded")
    if "boundary" not in combined_low:
        bad("boundary disposition not recorded")

    # 7: FE.1D-S1 COMPLETE/SHIPPED.
    if not re.search(r"fe\.1d-s1[^.]{0,40}(complete|shipped)", combined_low):
        bad("FE.1D-S1 COMPLETE/SHIPPED statement missing")

    # 8: FE.1D-S2 UNAUTHORIZED/NON-CRITICAL.
    if not re.search(r"fe\.1d-s2[^.]{0,40}(unauthorized|non-critical)", combined_low):
        bad("FE.1D-S2 UNAUTHORIZED/NON-CRITICAL statement missing")

    # 9: "+ Create task" unchanged.
    if "create task" not in combined_low or "unchanged" not in combined_low:
        bad('"+ Create task" unchanged decision not recorded')

    # 10: delivery_package rename deferred to 66D.
    if "delivery_package_ready_for_admin_console" not in combined_low:
        bad("delivery_package_ready_for_admin_console reference missing")
    if "66d" not in combined_low or "defer" not in combined_low:
        bad("delivery_package rename deferred-to-66D statement missing")

    # 11: workflow dispatch wording decision.
    if "workflow dispatch" not in combined_low:
        bad("workflow dispatch wording decision missing")

    # 12-13: SPA deep-link fallback / two-way URL sync excluded.
    if "spa deep-link" not in combined_low:
        bad("SPA deep-link fallback exclusion missing")
    if "two-way url sync" not in combined_low:
        bad("two-way URL sync exclusion missing")

    # 14-16: Team RBAC decision, M3 ownership, M6/M7 ownership.
    rbac_text = _norm(texts["team-rbac-decision"])
    if "approved_by_product_owner" not in rbac_text:
        bad("Team RBAC decision status APPROVED_BY_PRODUCT_OWNER missing")
    if "m3 owns" not in rbac_text and "m3 owns:" not in rbac_text:
        bad("M3 ownership not recorded in Team RBAC decision")
    if "m6/m7 own" not in rbac_text:
        bad("M6/M7 ownership not recorded in Team RBAC decision")

    # 17: alignment branches remain unmerged.
    for branch in ALIGNMENT_BRANCH_NAMES:
        if branch not in combined_low:
            bad(f"alignment branch {branch} not referenced")
    if "unmerged" not in combined_low and "remain unmerged" not in combined_low:
        bad("alignment branches remain-unmerged statement missing")
    for alignment_dir in ROOT.glob("docs/alignment/**"):
        if alignment_dir.is_file():
            bad(f"unexpected docs/alignment/ file present on main: {alignment_dir}")

    # 18-20: no runtime/backend/API/DB/workflow change, no deployment, no Step 66C.4-P start.
    for term in ("backend", "api", "database", "workflow"):
        if (
            not re.search(rf"no [\w/]*{term}", combined_low)
            and f"{term} change" not in combined_low
        ):
            bad(f"no-{term}-change statement missing")
    if "no deployment" not in combined_low and "deployment performed: no" not in combined_low:
        bad("no-deployment statement missing")
    if "66c.4-p" not in combined_low or "not started" not in combined_low:
        bad("Step 66C.4-P not-started statement missing")

    # 21: source/progress.md updated.
    if "66m0-sot-reconcile-m" not in progress_low:
        bad("source/progress.md does not reference Stage 66M0-SOT-RECONCILE-M")

    # 22: source-of-truth closure record exists (checked above).

    # 23: runtime code vs. repository record commit distinguished.
    if RUNTIME_CODE_COMMIT not in combined_low:
        bad("runtime frontend code commit not recorded")
    if PRE_MERGE_MAIN_COMMIT not in combined_low:
        bad("pre-merge repository record commit not recorded")

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

    print("  [OK] Source-of-truth closure record + merge execution record + Team RBAC decision +")
    print("       test record + stage manifest/context-receipt/stage-gate-report all present; all")
    print("       three FE.1D branches recorded merged with source/merge commits; FE.1D-S1")
    print("       COMPLETE/SHIPPED; FE.1D-S2 UNAUTHORIZED/NON-CRITICAL; PO decisions preserved;")
    print("       Team RBAC M3/M6-M7 ownership recorded; alignment branches remain unmerged; no")
    print("       backend/API/database/workflow change; no deployment; no Step 66C.4-P start;")
    print("       source/progress.md updated; runtime vs. repository record commits distinguished;")
    print("       no forbidden capability claims or sensitive identifiers")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
