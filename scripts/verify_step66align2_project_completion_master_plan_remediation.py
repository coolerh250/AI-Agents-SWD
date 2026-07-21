#!/usr/bin/env python3
"""Step 66ALIGN.2-R1 -- project completion master plan ownership remediation verifier.

Confirms the ownership remediation record and remediation test record exist and state: Step 66C.4
primary implementation owner is Claude Code (scheduler/expiry/resume/backend/workflow), Codex is
limited to explicitly authorized frontend slices, M3 owns product-level Team RBAC implementation,
M6/M7 own production identity/session/provisioning hardening without deferring M3's implementation,
FE.1D-S2 is not an unresolved PO decision (remains unauthorized/non-critical), the canonical
milestone order is unchanged, Step 66C.4-P remains not started, no runtime/backend/API/DB/workflow
change or deployment is claimed, alignment branches remain unmerged, and source/progress.md is
updated.

This is a documentation-only verifier: it reads files on the current checkout and does not touch
any runtime or remote host.

Marker: STEP66ALIGN2_PROJECT_COMPLETION_MASTER_PLAN_REMEDIATION_VERIFY: PASS | PASS_WITH_GAPS | FAIL
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MASTER_DIR = ROOT / "docs" / "alignment" / "66-project-completion" / "master"

OWNERSHIP_RECORD = MASTER_DIR / "ownership-remediation-record.md"
REMEDIATION_TEST_RECORD = (
    ROOT / "docs" / "test" / "step66align2-project-completion-master-plan-remediation-record.md"
)

MASTER_DOCS = {
    "master-plan": MASTER_DIR / "project-completion-master-plan.md",
    "canonical-milestone-manifest": MASTER_DIR / "canonical-milestone-manifest.md",
    "critical-path-and-dependency-map": MASTER_DIR / "critical-path-and-dependency-map.md",
    "role-ownership-matrix": MASTER_DIR / "role-ownership-matrix.md",
    "product-and-technical-gates": MASTER_DIR / "product-and-technical-gates.md",
    "project-definition-of-done": MASTER_DIR / "project-definition-of-done.md",
    "next-executable-stage-sequence": MASTER_DIR / "next-executable-stage-sequence.md",
    "cross-partner-resolution-record": MASTER_DIR / "cross-partner-resolution-record.md",
    "product-owner-review-checklist": MASTER_DIR / "product-owner-review-checklist.md",
    "ownership-remediation-record": OWNERSHIP_RECORD,
}

STAGE_DOCS = {
    "stage-manifest": ROOT
    / "docs"
    / "stages"
    / "66align2-project-completion-master-plan-remediation"
    / "stage-manifest.yaml",
    "context-receipt": ROOT
    / "docs"
    / "stages"
    / "66align2-project-completion-master-plan-remediation"
    / "context-receipt.md",
    "stage-gate-report": ROOT
    / "docs"
    / "stages"
    / "66align2-project-completion-master-plan-remediation"
    / "stage-gate-report.md",
}

PROGRESS = ROOT / "source" / "progress.md"

MARKER = "STEP66ALIGN2_PROJECT_COMPLETION_MASTER_PLAN_REMEDIATION_VERIFY"

ALIGNMENT_BRANCH_NAMES = (
    "alignment/66-project-completion-claude-code",
    "design/66-project-completion-experience-alignment",
    "alignment/66-project-completion-codex",
)

CANONICAL_MILESTONES = ("m0", "m1", "m2", "m3", "m4", "m5", "m6", "m7")

ALL_TEXT_DOCS = {**MASTER_DOCS, "remediation-test-record": REMEDIATION_TEST_RECORD}

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
    re.compile(r"master plan (?:was|is) merged", re.IGNORECASE),
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
    if not OWNERSHIP_RECORD.is_file():
        bad(f"missing ownership remediation record: {OWNERSHIP_RECORD}")
    if not REMEDIATION_TEST_RECORD.is_file():
        bad(f"missing remediation test record: {REMEDIATION_TEST_RECORD}")
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

    # 3-5. Step 66C.4 primary owner is Claude Code; Codex limited to authorized frontend slices;
    # Claude Code owns scheduler/expiry/resume/backend/workflow.
    if not re.search(r"claude code[^.]{0,80}primary[^.]{0,40}(owner|implementation)", combined_low):
        bad("Claude Code as primary Step 66C.4 implementation owner not clearly stated")
    if (
        "explicitly authorized frontend" not in combined_low
        and "explicitly authorized" not in combined_low
    ):
        bad("Codex limited-to-explicitly-authorized-frontend-slice statement missing")
    for term in ("scheduler", "expiry", "resume", "backend", "workflow"):
        if term not in combined_low:
            bad(f"Claude Code Step 66C.4 ownership term missing: {term}")

    # 6-7. M3 owns Team RBAC implementation; M6/M7 own production identity/session/provisioning.
    if "m3 owns" not in combined_low and "m3 implements" not in combined_low:
        bad("M3 Team RBAC implementation ownership not recorded")
    if "m6/m7" not in combined_low or "identity" not in combined_low:
        bad("M6/M7 production identity ownership not recorded")
    if "session" not in combined_low or "provisioning" not in combined_low:
        bad("M6/M7 session/provisioning hardening scope not recorded")

    # 8. M6 wording must not defer Team RBAC implementation from M3.
    if not re.search(
        r"not deferred to m6|not defer(?:red|ring)? m3|implemented and validated in m3",
        combined_low,
    ):
        bad("explicit non-deferral statement (Team RBAC implementation not deferred to M6) missing")

    # 9-10. FE.1D-S2 not an unresolved PO decision; remains unauthorized/non-critical.
    if (
        "not listed as an unresolved" not in combined_low
        and "not framed as an open decision" not in combined_low
    ):
        bad("FE.1D-S2 removed-from-unresolved-decisions statement missing")
    if not re.search(r"fe\.1d-s2[^.]{0,60}(unauthorized|non-critical)", combined_low):
        bad("FE.1D-S2 unauthorized/non-critical status missing")

    # 11. Canonical milestone order unchanged.
    order_doc = texts["master-plan"].lower()
    if "m0 -> m1 -> m2 -> m3 -> m4 -> m5 -> m6 -> m7" not in order_doc:
        bad("canonical milestone order M0->M1->...->M7 not found unchanged in master-plan.md")
    for m in CANONICAL_MILESTONES:
        if m not in combined_low:
            bad(f"canonical milestone {m.upper()} reference missing")

    # 12. Step 66C.4-P remains not started.
    if "66c.4-p" not in combined_low:
        bad("Step 66C.4-P reference missing")
    if "not started" not in combined_low:
        bad("Step 66C.4-P not-started statement missing")

    # 13-14. No runtime/backend/API/DB/workflow change claimed; no deployment claimed.
    for term in ("backend", "api", "database", "workflow"):
        if (
            not re.search(rf"no [\w/]*{term}", combined_low)
            and f"{term} change" not in combined_low
        ):
            bad(f"no-{term}-change statement missing")
    if "no deployment" not in combined_low:
        bad("no-deployment statement missing")

    # 15. Alignment branches remain unmerged.
    for branch in ALIGNMENT_BRANCH_NAMES:
        if branch not in combined_low:
            bad(f"alignment branch {branch} not referenced")
    if "unmerged" not in combined_low:
        bad("alignment branches remain-unmerged statement missing")

    # 16. source/progress.md updated.
    if "66align.2-r1" not in progress_low:
        bad("source/progress.md does not reference Stage 66ALIGN.2-R1")

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

    print("  [OK] Ownership remediation record + remediation test record + stage manifest/")
    print("       context-receipt/stage-gate-report all present; Step 66C.4 primary owner is")
    print("       Claude Code (scheduler/expiry/resume/backend/workflow), Codex limited to")
    print("       explicitly authorized frontend slices; M3 owns Team RBAC implementation, M6/M7")
    print("       own production identity/session/provisioning hardening without deferring M3;")
    print("       FE.1D-S2 removed from unresolved PO decisions, remains unauthorized/non-")
    print("       critical; canonical milestone order unchanged; Step 66C.4-P not started; no")
    print("       runtime/backend/API/database/workflow change; no deployment; alignment branches")
    print("       remain unmerged; source/progress.md updated; no forbidden capability claims or")
    print("       sensitive identifiers")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
