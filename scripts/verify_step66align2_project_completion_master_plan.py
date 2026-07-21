#!/usr/bin/env python3
"""Step 66ALIGN.2-CONSOLIDATE -- project completion master plan consolidation verifier.

Confirms the 11 consolidated Master Plan documents exist and state: M0 CLOSED, M1-M7 status
recorded, Step 66C.4-P next but not started, 66D-ARCH preceding Delivery UI implementation,
FE.1D-S2 unauthorized/non-critical, Team RBAC M3 ownership and M6/M7 production-identity ownership
recorded, the no-fake-UI/capability principle recorded, alignment branches remaining unmerged, no
runtime/backend/API/DB/workflow change or deployment claimed, and source/progress.md updated.

This is a documentation-only verifier: it reads files on the current checkout and does not touch
any runtime or remote host.

Marker: STEP66ALIGN2_PROJECT_COMPLETION_MASTER_PLAN_VERIFY: PASS | PASS_WITH_GAPS | FAIL
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MASTER_DIR = ROOT / "docs" / "alignment" / "66-project-completion" / "master"

MASTER_DOCS = {
    "master-plan": MASTER_DIR / "project-completion-master-plan.md",
    "canonical-milestone-manifest": MASTER_DIR / "canonical-milestone-manifest.md",
    "current-state-capability-matrix": MASTER_DIR / "current-state-capability-matrix.md",
    "critical-path-and-dependency-map": MASTER_DIR / "critical-path-and-dependency-map.md",
    "role-ownership-matrix": MASTER_DIR / "role-ownership-matrix.md",
    "product-and-technical-gates": MASTER_DIR / "product-and-technical-gates.md",
    "project-definition-of-done": MASTER_DIR / "project-definition-of-done.md",
    "deferred-work-register": MASTER_DIR / "deferred-work-register.md",
    "next-executable-stage-sequence": MASTER_DIR / "next-executable-stage-sequence.md",
    "cross-partner-resolution-record": MASTER_DIR / "cross-partner-resolution-record.md",
    "product-owner-review-checklist": MASTER_DIR / "product-owner-review-checklist.md",
}

TEST_RECORD = ROOT / "docs" / "test" / "step66align2-project-completion-master-plan-record.md"

STAGE_DOCS = {
    "stage-manifest": ROOT
    / "docs"
    / "stages"
    / "66align2-project-completion-master-plan"
    / "stage-manifest.yaml",
    "context-receipt": ROOT
    / "docs"
    / "stages"
    / "66align2-project-completion-master-plan"
    / "context-receipt.md",
    "stage-gate-report": ROOT
    / "docs"
    / "stages"
    / "66align2-project-completion-master-plan"
    / "stage-gate-report.md",
}

PROGRESS = ROOT / "source" / "progress.md"
ALIGNMENT_ROOT = ROOT / "docs" / "alignment" / "66-project-completion"

MARKER = "STEP66ALIGN2_PROJECT_COMPLETION_MASTER_PLAN_VERIFY"

ALIGNMENT_BRANCH_NAMES = (
    "alignment/66-project-completion-claude-code",
    "design/66-project-completion-experience-alignment",
    "alignment/66-project-completion-codex",
)

FORBIDDEN_ORIGINAL_DIRS = ("claude-code", "claude-design", "codex")

ALL_TEXT_DOCS = {**MASTER_DOCS, "test-record": TEST_RECORD}

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
    for name, p in MASTER_DOCS.items():
        if not p.is_file():
            bad(f"missing master plan doc: {p} ({name})")
    if not TEST_RECORD.is_file():
        bad(f"missing test record: {TEST_RECORD}")
    for name, p in STAGE_DOCS.items():
        if not p.is_file():
            bad(f"missing stage doc: {p} ({name})")
    if not PROGRESS.is_file():
        bad(f"missing progress log: {PROGRESS}")

    for sub in FORBIDDEN_ORIGINAL_DIRS:
        original_dir = ALIGNMENT_ROOT / sub
        if original_dir.is_dir() and any(original_dir.iterdir()):
            bad(
                f"original partner alignment artifacts copied into this stage's scope: {original_dir}"
            )

    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    texts = {name: p.read_text(encoding="utf-8") for name, p in ALL_TEXT_DOCS.items()}
    progress_text = PROGRESS.read_text(encoding="utf-8")
    combined_low = _norm("\n".join(texts.values()))
    progress_low = _norm(progress_text)

    # 12. M0 recorded CLOSED.
    if not re.search(r"m0[^.]{0,20}closed", combined_low):
        bad("M0 CLOSED status not recorded")

    # 13. M1-M7 status recorded.
    for m in ("m1", "m2", "m3", "m4", "m5", "m6", "m7"):
        if (
            m + " —" not in combined_low
            and m + " -" not in combined_low
            and m + ":" not in combined_low
        ):
            bad(f"{m.upper()} status entry not clearly recorded")
    for status in ("in_progress", "not_started"):
        if status not in combined_low:
            bad(f"milestone status keyword '{status}' not found")

    # 14. Step 66C.4-P next but not started.
    if "66c.4-p" not in combined_low:
        bad("Step 66C.4-P reference missing")
    if "not started" not in combined_low and "not_started" not in combined_low:
        bad("Step 66C.4-P not-started statement missing")

    # 15. 66D-ARCH precedes Delivery UI implementation.
    if "66d-arch" not in combined_low:
        bad("66D-ARCH reference missing")
    if "66d-design" not in combined_low:
        bad("66D-DESIGN reference missing")
    if not re.search(r"66d-arch.{0,400}66d-design", combined_low, re.DOTALL) and not re.search(
        r"before any ui", combined_low
    ):
        bad("66D-ARCH-precedes-UI ordering not clearly recorded")

    # 16. FE.1D-S2 unauthorized/non-critical.
    if not re.search(r"fe\.1d-s2[^.]{0,60}(unauthorized|non-critical)", combined_low):
        bad("FE.1D-S2 unauthorized/non-critical statement missing")

    # 17-18. Team RBAC M3 ownership + M6/M7 production identity ownership.
    if "m3 owns" not in combined_low:
        bad("Team RBAC M3 ownership not recorded")
    if "m6/m7 own" not in combined_low:
        bad("Team RBAC M6/M7 production-identity ownership not recorded")

    # 19. No-fake-UI/capability principle recorded.
    fake_ui_cues = (
        "fake delivery inbox",
        "fake action center",
        "fake notification",
        "fabricated agent activity",
        "orchestration controls that do not exist",
    )
    if not any(cue in combined_low for cue in fake_ui_cues):
        bad("no-fake-UI/capability principle not recorded")

    # 20. Alignment branches remain unmerged.
    for branch in ALIGNMENT_BRANCH_NAMES:
        if branch not in combined_low:
            bad(f"alignment branch {branch} not referenced")
    if "unmerged" not in combined_low:
        bad("alignment branches remain-unmerged statement missing")

    # 21. No runtime/backend/API/DB/workflow change claimed.
    for term in ("backend", "api", "database", "workflow"):
        if (
            not re.search(rf"no [\w/]*{term}", combined_low)
            and f"{term} change" not in combined_low
        ):
            bad(f"no-{term}-change statement missing")

    # 22. No deployment claimed.
    if "no deployment" not in combined_low:
        bad("no-deployment statement missing")

    # 23. source/progress.md updated.
    if "66align.2-consolidate" not in progress_low:
        bad("source/progress.md does not reference Stage 66ALIGN.2-CONSOLIDATE")

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

    print("  [OK] All 11 Master Plan documents + test record + stage manifest/context-receipt/")
    print("       stage-gate-report present; M0 CLOSED, M1-M7 status recorded; Step 66C.4-P next")
    print("       but not started; 66D-ARCH precedes Delivery UI; FE.1D-S2 unauthorized/non-")
    print("       critical; Team RBAC M3/M6-M7 ownership recorded; no-fake-UI principle recorded;")
    print("       alignment branches remain unmerged; no runtime/backend/API/database/workflow")
    print("       change; no deployment; source/progress.md updated; no forbidden capability")
    print("       claims or sensitive identifiers")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
