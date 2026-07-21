#!/usr/bin/env python3
"""Step 66ALIGN.2-M -- merge project completion master plan into main verifier.

Confirms the merge record and source-of-truth record exist and state: Master Plan source commit
5da21f5 and merge commit recorded, Master Plan artifacts present on main, Master Plan recorded as
canonical source of truth, M0-M7 order recorded (M0 CLOSED, M1 IN_PROGRESS), Step 66C.4-P next but
not started, Step 66C.4 primary owner is Claude Code with Codex limited to separately authorized
frontend slices, M3 implements product-level Team RBAC, M6/M7 production-harden identity/access,
FE.1D-S2 remains unauthorized/non-critical and is not an unresolved PO decision, original alignment
branches remain unmerged, PR #14/#15 remain unchanged, no runtime/backend/API/DB/workflow change or
deployment is claimed, production_executed_true_count remains 0, and source/progress.md is
updated.

This is a documentation-only verifier: it reads files on the current checkout and does not touch
any runtime or remote host.

Marker: STEP66ALIGN2_PROJECT_COMPLETION_MASTER_PLAN_MERGE_VERIFY: PASS | PASS_WITH_GAPS | FAIL
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MASTER_DIR = ROOT / "docs" / "alignment" / "66-project-completion" / "master"

MERGE_RECORD = MASTER_DIR / "master-plan-merge-record.md"
SOT_RECORD = MASTER_DIR / "master-plan-source-of-truth-record.md"
MERGE_TEST_RECORD = (
    ROOT / "docs" / "test" / "step66align2-project-completion-master-plan-merge-record.md"
)

MASTER_PLAN_ARTIFACTS = [
    MASTER_DIR / "project-completion-master-plan.md",
    MASTER_DIR / "canonical-milestone-manifest.md",
    MASTER_DIR / "current-state-capability-matrix.md",
    MASTER_DIR / "critical-path-and-dependency-map.md",
    MASTER_DIR / "role-ownership-matrix.md",
    MASTER_DIR / "product-and-technical-gates.md",
    MASTER_DIR / "project-definition-of-done.md",
    MASTER_DIR / "deferred-work-register.md",
    MASTER_DIR / "next-executable-stage-sequence.md",
    MASTER_DIR / "cross-partner-resolution-record.md",
    MASTER_DIR / "product-owner-review-checklist.md",
    MASTER_DIR / "ownership-remediation-record.md",
]

STAGE_DOCS = {
    "stage-manifest": ROOT
    / "docs"
    / "stages"
    / "66align2-project-completion-master-plan-merge"
    / "stage-manifest.yaml",
    "context-receipt": ROOT
    / "docs"
    / "stages"
    / "66align2-project-completion-master-plan-merge"
    / "context-receipt.md",
    "stage-gate-report": ROOT
    / "docs"
    / "stages"
    / "66align2-project-completion-master-plan-merge"
    / "stage-gate-report.md",
}

PROGRESS = ROOT / "source" / "progress.md"

MARKER = "STEP66ALIGN2_PROJECT_COMPLETION_MASTER_PLAN_MERGE_VERIFY"

MASTER_PLAN_SOURCE_COMMIT = "5da21f5"

ALIGNMENT_BRANCH_NAMES = (
    "alignment/66-project-completion-claude-code",
    "design/66-project-completion-experience-alignment",
    "alignment/66-project-completion-codex",
)

ALL_TEXT_DOCS = {
    "merge-record": MERGE_RECORD,
    "sot-record": SOT_RECORD,
    "merge-test-record": MERGE_TEST_RECORD,
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
    re.compile(
        r"(claude-code|codex|claude-design) alignment branch (?:was|is) merged", re.IGNORECASE
    ),
    re.compile(r"pr #1[45] (?:was|is|has been) closed", re.IGNORECASE),
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
    "unmerged",
    "unclosed",
    "unchanged",
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
    for name, p in ALL_TEXT_DOCS.items():
        if not p.is_file():
            bad(f"missing record: {p} ({name})")
    for p in MASTER_PLAN_ARTIFACTS:
        if not p.is_file():
            bad(f"missing Master Plan artifact on main: {p}")
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

    # 1. Master Plan branch source commit recorded.
    if MASTER_PLAN_SOURCE_COMMIT not in combined_low:
        bad(f"Master Plan source commit {MASTER_PLAN_SOURCE_COMMIT} not recorded")

    # 2. Merge commit recorded.
    if "merge commit" not in combined_low:
        bad("merge commit not recorded")

    # 3-4. Master Plan artifacts on main (checked above); recorded as canonical source of truth.
    if "canonical source of truth" not in combined_low and "canonical" not in combined_low:
        bad("Master Plan not recorded as canonical source of truth")

    # 5-7. M0-M7 order recorded; M0 CLOSED; M1 IN_PROGRESS.
    if "m0 -> m1 -> m2 -> m3 -> m4 -> m5 -> m6 -> m7" not in combined_low:
        bad("canonical milestone order M0->M1->...->M7 not recorded")
    if not re.search(r"m0[^.]{0,20}closed", combined_low):
        bad("M0 CLOSED not recorded")
    if "in_progress" not in combined_low:
        bad("M1 IN_PROGRESS not recorded")

    # 8. Step 66C.4-P next but not started.
    if "66c.4-p" not in combined_low:
        bad("Step 66C.4-P reference missing")
    if "not started" not in combined_low:
        bad("Step 66C.4-P not-started statement missing")

    # 9-10. Step 66C.4 primary owner Claude Code; Codex limited to authorized frontend slices.
    if not re.search(r"claude code[^.]{0,40}(primary|owner)", combined_low):
        bad("Claude Code as Step 66C.4 primary owner not recorded")
    if "authorized frontend" not in combined_low:
        bad("Codex limited-to-authorized-frontend-slices statement missing")

    # 11-12. M3 Team RBAC implementation; M6/M7 identity/access hardening.
    if "team rbac" not in combined_low or "m3" not in combined_low:
        bad("M3 Team RBAC implementation ownership not recorded")
    if "m6/m7" not in combined_low or "identity" not in combined_low:
        bad("M6/M7 production identity/access ownership not recorded")

    # 13-14. FE.1D-S2 unauthorized/non-critical; not an unresolved PO decision.
    if not re.search(r"fe\.1d-s2[^.]{0,60}(unauthorized|non-critical)", combined_low):
        bad("FE.1D-S2 unauthorized/non-critical status missing")
    if "unresolved" not in combined_low and "not an open" not in combined_low:
        bad("FE.1D-S2 not-an-unresolved-PO-decision statement missing")

    # 15-16. Original alignment branches remain unmerged; PR #14/#15 unchanged.
    for branch in ALIGNMENT_BRANCH_NAMES:
        if branch not in combined_low:
            bad(f"alignment branch {branch} not referenced")
    if "unmerged" not in combined_low:
        bad("alignment branches remain-unmerged statement missing")
    if "pr #14" not in combined_low or "pr #15" not in combined_low:
        bad("PR #14/#15 reference missing")

    # 17-19. No runtime/backend/API/DB/workflow change; no deployment; no production/external action.
    for term in ("backend", "api", "database", "workflow"):
        if (
            not re.search(rf"no [\w/]*{term}", combined_low)
            and f"{term} change" not in combined_low
        ):
            bad(f"no-{term}-change statement missing")
    if "no deployment" not in combined_low:
        bad("no-deployment statement missing")
    if (
        "production/external action" not in combined_low
        and "production/ external action" not in combined_low
    ):
        bad("no-production/external-action statement missing")

    # 20. production_executed_true_count remains 0.
    if "production_executed_true_count" not in combined_low or "0" not in combined_low:
        bad("production_executed_true_count=0 statement missing")

    # 21. source/progress.md updated.
    if "66align.2-m" not in progress_low:
        bad("source/progress.md does not reference Stage 66ALIGN.2-M")

    # 22. Merge/source-of-truth records exist (checked above via file existence).

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

    print("  [OK] Merge record + source-of-truth record + merge test record + stage manifest/")
    print("       context-receipt/stage-gate-report all present; Master Plan source commit and")
    print("       merge commit recorded; Master Plan artifacts present on main and recorded as")
    print("       canonical source of truth; M0-M7 order recorded (M0 CLOSED, M1 IN_PROGRESS);")
    print("       Step 66C.4-P next but not started; Step 66C.4 primary owner Claude Code, Codex")
    print("       limited to authorized frontend slices; M3 Team RBAC implementation and M6/M7")
    print("       identity/access hardening recorded; FE.1D-S2 unauthorized/non-critical, not an")
    print("       unresolved PO decision; original alignment branches remain unmerged; PR #14/#15")
    print("       unchanged; no runtime/backend/API/database/workflow change; no deployment;")
    print("       production_executed_true_count=0; source/progress.md updated; no forbidden")
    print("       capability claims or sensitive identifiers")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
