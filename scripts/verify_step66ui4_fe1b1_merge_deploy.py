#!/usr/bin/env python3
"""Step 66UI.4-FE.1B.1-MD -- FE.1B.1 merge + merged-main test-deployment verifier.

Confirms the merge record and merged-main test-deployment record for Step 66UI.4-FE.1B.1 exist and
state: the PR #9 merge to main, the Product Owner merge authorization, the Product Owner UI
validation VISIBLE verdict, that the prior Step 66UI.4-FE.1B-V Unavailable gap is closed, that the
FE.1B.1 planning/review/preview artifacts are present in main, that the deployment source is merged
main, that runtime posture is test-runtime-only, that no backend/API/database/workflow change is
claimed, that the /operations/safety response shape is unchanged, that no production/external
action is claimed, that FE.1C/FE.1D remain unauthorized, that production_executed_true_count
remains 0, that Local Artifact Reconciliation is recorded, and that no Windows/local path exposure
is recorded.

This is a documentation-only verifier: it reads files on the current checkout and does not touch
any runtime or remote host.

Marker: STEP66UI4_FE1B1_MERGE_DEPLOY_VERIFY: PASS | PASS_WITH_GAPS | FAIL
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DOCS = {
    "fe1b1-merge-record": ROOT
    / "docs"
    / "frontend"
    / "66ui4-phase1-product-visual-language"
    / "fe1b1-merge-record.md",
    "fe1b1-merged-main-test-deployment-record": ROOT
    / "docs"
    / "test"
    / "step66ui4-fe1b1-merged-main-test-deployment-record.md",
}

PROGRESS = ROOT / "source" / "progress.md"

MARKER = "STEP66UI4_FE1B1_MERGE_DEPLOY_VERIFY"
PR9_COMMIT = "974822d"
PR9_BRANCH = "frontend/66ui4-fe1b1-safety-field-mapping"

FE1B1_ARTIFACTS = [
    ROOT
    / "docs"
    / "frontend"
    / "66ui4-phase1-product-visual-language"
    / "fe1b1-safety-field-mapping-plan.md",
    ROOT
    / "docs"
    / "contracts"
    / "66ui4-fe1b1-safety-field-mapping"
    / "frontend-implementation-boundary.md",
    ROOT / "docs" / "test" / "step66ui4-fe1b1-safety-field-mapping-planning-record.md",
    ROOT / "docs" / "stages" / "66ui4-fe1b1" / "stage-manifest.yaml",
    ROOT
    / "docs"
    / "frontend"
    / "66ui4-phase1-product-visual-language"
    / "fe1b1-safety-field-mapping-implementation-report.md",
    ROOT / "docs" / "handoffs" / "66ui4-fe1b1" / "codex-to-claude-code-handoff.md",
    ROOT / "docs" / "test" / "step66ui4-fe1b1-safety-field-mapping-test-report.md",
    ROOT
    / "docs"
    / "frontend"
    / "66ui4-phase1-product-visual-language"
    / "fe1b1-claude-code-review.md",
    ROOT / "docs" / "test" / "step66ui4-fe1b1-review-record.md",
    ROOT / "docs" / "test" / "step66ui4-fe1b1-ui-validation-preview-deployment-record.md",
    ROOT
    / "docs"
    / "frontend"
    / "66ui4-phase1-product-visual-language"
    / "fe1b1-ui-validation-preview-record.md",
    ROOT
    / "docs"
    / "frontend"
    / "66ui4-phase1-product-visual-language"
    / "fe1b1-product-owner-ui-validation-record.md",
    ROOT / "docs" / "test" / "step66ui4-fe1b1-product-owner-validation.md",
    ROOT / "scripts" / "verify_step66ui4_fe1b1_planning.py",
    ROOT / "scripts" / "verify_step66ui4_fe1b1_mapping_calibration.py",
    ROOT / "scripts" / "verify_step66ui4_fe1b1_review.py",
    ROOT / "scripts" / "verify_step66ui4_fe1b1_preview_deploy.py",
    ROOT / "scripts" / "verify_step66ui4_fe1b1_product_owner_validation.py",
]

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
    re.compile(r"production action (?:was|is) triggered", re.IGNORECASE),
    re.compile(r"external action (?:was|is) triggered", re.IGNORECASE),
    re.compile(r"fe\.1c is authorized", re.IGNORECASE),
    re.compile(r"fe\.1d is authorized", re.IGNORECASE),
    re.compile(r"deployed from (?:the )?pr branch", re.IGNORECASE),
    re.compile(r"gap (?:was|is) fixed by this validation", re.IGNORECASE),
    re.compile(r"response shape (?:was|is) changed", re.IGNORECASE),
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
    for p in FE1B1_ARTIFACTS:
        if not p.is_file():
            bad(f"missing consolidated FE.1B.1 artifact on main: {p}")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    texts = {name: p.read_text(encoding="utf-8") for name, p in DOCS.items()}
    progress_text = PROGRESS.read_text(encoding="utf-8")
    combined_low = _norm("\n".join(texts.values()))
    progress_low = _norm(progress_text)

    if "pr #9" not in combined_low:
        bad("PR #9 reference missing")
    if PR9_BRANCH not in combined_low:
        bad("branch reference missing")
    if PR9_COMMIT not in combined_low:
        bad("commit reference missing")
    if "66ui.4-fe.1b.1-md" not in progress_low:
        bad("source/progress.md does not reference Stage 66UI.4-FE.1B.1-MD")

    if "visible" not in combined_low:
        bad("Product Owner VISIBLE validation not referenced")
    if "authorization" not in combined_low:
        bad("Product Owner merge authorization not referenced")

    if "gap" not in combined_low or (
        "closed" not in combined_low and "resolved" not in combined_low
    ):
        bad("FE.1B-V Unavailable gap closure statement missing")
    if "unavailable" not in combined_low:
        bad("prior Unavailable gap not referenced")

    for phrase in ("fe.1c", "fe.1d"):
        if phrase not in combined_low:
            bad(f"{phrase} not referenced")
    if "unauthorized" not in combined_low and "not authorized" not in combined_low:
        bad("FE.1C/FE.1D unauthorized statement missing")

    if "merged main" not in combined_low:
        bad("deployment-source-is-merged-main statement missing")
    if "pr branch" not in combined_low:
        bad("not-deployed-from-pr-branch statement missing")

    if "test runtime" not in combined_low and "test-runtime" not in combined_low:
        bad("test-runtime-only runtime posture statement missing")

    for term in ("backend", "api", "database", "workflow"):
        if not re.search(rf"no [\w/]*{term}", combined_low):
            bad(f"no-{term}-change statement missing")

    if "/operations/safety" not in combined_low or "response shape" not in combined_low:
        bad("/operations/safety response shape statement missing")

    if not re.search(r"no [\w/]*production action", combined_low):
        bad("no-production-action statement missing")
    if not re.search(r"no [\w/]*external action", combined_low):
        bad("no-external-action statement missing")

    if "production_executed_true_count" not in combined_low:
        bad("production_executed_true_count not recorded")
    if "0` before and after" not in combined_low and "0` before" not in combined_low:
        bad("production_executed_true_count=0 before/after statement missing")

    if "local artifact reconciliation" not in combined_low:
        bad("Local Artifact Reconciliation section missing")
    for name, text in texts.items():
        if WINDOWS_PATH_SHAPE.search(text):
            bad(f"{name} contains a local Windows absolute path")

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

    print("  [OK] FE.1B.1 merge record + merged-main test-deployment record present; PR #9/branch/")
    print("       commit referenced; Product Owner merge authorization and VISIBLE validation")
    print("       documented; prior Unavailable gap closure documented; FE.1C/FE.1D unauthorized;")
    print(
        "       all consolidated FE.1B.1 planning/implementation/review/preview artifacts present"
    )
    print("       on main; deployment source is merged main (not PR branch); test-runtime-only")
    print("       posture; no backend/API/database/workflow change; /operations/safety response")
    print(
        "       shape unchanged; no production/external action; production_executed_true_count=0;"
    )
    print("       Local Artifact Reconciliation recorded; no forbidden capability claims or")
    print("       sensitive identifiers")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
