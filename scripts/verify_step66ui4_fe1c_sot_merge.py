#!/usr/bin/env python3
"""Step 66UI.4-FE.1C-SOT-M -- FE.1C design/review source-of-truth merge verifier.

Confirms the source-of-truth merge record and test record exist and state: the merged design branch
/ PR #8 and review branch, the FE.1C review PASS marker, the existing-data-only principle, the
/tasks status-filter usage decision, the FE.1B.1 safety reuse dependency now satisfied, the
agent-execution status mapping, that 66D/66C.4/notifications/pipeline items remain placeholder-only,
that no fake counts/controls are claimed, that Codex FE.1C implementation remains unauthorized, that
FE.1D remains unauthorized, that no frontend runtime/backend/API/database/workflow change is
claimed, that no production/external action is claimed, that Local Artifact Reconciliation is
recorded, and that no Windows/local path exposure is recorded.

This is a documentation-only verifier: it reads files on the current checkout and does not touch
any runtime or remote host.

Marker: STEP66UI4_FE1C_SOT_MERGE_VERIFY: PASS | PASS_WITH_GAPS | FAIL
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DOCS = {
    "fe1c-sot-merge-record": ROOT
    / "docs"
    / "design"
    / "66ui4-fe1c-overview-attention-first"
    / "source-of-truth-merge-record.md",
    "fe1c-sot-merge-test-record": ROOT
    / "docs"
    / "test"
    / "step66ui4-fe1c-source-of-truth-merge-record.md",
}

PROGRESS = ROOT / "source" / "progress.md"

MARKER = "STEP66UI4_FE1C_SOT_MERGE_VERIFY"
DESIGN_COMMIT = "0c7762e"
REVIEW_COMMIT = "4eb1279"

FE1C_ARTIFACTS = [
    ROOT / "docs" / "design" / "66ui4-fe1c-overview-attention-first" / "design-brief.md",
    ROOT
    / "docs"
    / "design"
    / "66ui4-fe1c-overview-attention-first"
    / "claude-code-architecture-review.md",
    ROOT
    / "docs"
    / "contracts"
    / "66ui4-fe1c-overview-attention-first"
    / "frontend-implementation-boundary.md",
    ROOT
    / "docs"
    / "frontend"
    / "66ui4-fe1c-overview-attention-first"
    / "codex-readiness-boundary.md",
    ROOT / "docs" / "handoffs" / "66ui4-fe1c" / "claude-design-to-claude-code-handoff.md",
    ROOT / "docs" / "stages" / "66ui4-fe1c" / "stage-manifest.yaml",
    ROOT / "docs" / "test" / "step66ui4-fe1c-design-review-record.md",
    ROOT / "scripts" / "verify_design_66ui4_fe1c_overview_brief.py",
    ROOT / "scripts" / "verify_step66ui4_fe1c_design_review.py",
]

SECRET_SHAPES = re.compile(
    r"(-----BEGIN [A-Z ]*PRIVATE KEY|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
    r"AKIA[0-9A-Z]{16}|xoxb-[A-Za-z0-9-]{10,}|sk-ant-[A-Za-z0-9_-]{20,})"
)
INFRA_SHAPES = re.compile(r"(10\.0\.1\.31|aiagent-swd|itadmin)", re.IGNORECASE)
WINDOWS_PATH_SHAPE = re.compile(r"[A-Za-z]:[\\/]Users[\\/]", re.IGNORECASE)

FORBIDDEN_CLAIM_PATTERNS = (
    re.compile(r"frontend runtime (?:was|is) changed", re.IGNORECASE),
    re.compile(r"backend (?:was|is) changed", re.IGNORECASE),
    re.compile(r"api (?:was|is) changed", re.IGNORECASE),
    re.compile(r"database (?:was|is) changed", re.IGNORECASE),
    re.compile(r"workflow (?:was|is) changed", re.IGNORECASE),
    re.compile(r"production action (?:was|is) triggered", re.IGNORECASE),
    re.compile(r"external action (?:was|is) triggered", re.IGNORECASE),
    re.compile(r"codex fe\.1c is authorized", re.IGNORECASE),
    re.compile(r"fe\.1d is authorized", re.IGNORECASE),
    re.compile(r"deployed to test runtime", re.IGNORECASE),
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
    for p in FE1C_ARTIFACTS:
        if not p.is_file():
            bad(f"missing consolidated FE.1C artifact on main: {p}")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    texts = {name: p.read_text(encoding="utf-8") for name, p in DOCS.items()}
    progress_text = PROGRESS.read_text(encoding="utf-8")
    combined_low = _norm("\n".join(texts.values()))
    progress_low = _norm(progress_text)

    if "pr #8" not in combined_low:
        bad("PR #8 reference missing")
    if DESIGN_COMMIT not in combined_low:
        bad("design branch commit reference missing")
    if REVIEW_COMMIT not in combined_low:
        bad("review branch commit reference missing")
    if "66ui.4-fe.1c-sot-m" not in progress_low:
        bad("source/progress.md does not reference Stage 66UI.4-FE.1C-SOT-M")

    if "step66ui4_fe1c_design_review_verify: pass" not in combined_low:
        bad("FE.1C review PASS marker not referenced")

    if "existing-data-only" not in combined_low and "existing data only" not in combined_low:
        bad("existing-data-only principle not recorded")

    if "status filter" not in combined_low and "status=clarification_needed" not in combined_low:
        bad("/tasks status-filter usage decision not recorded")

    if "satisfied" not in combined_low and "unblocked" not in combined_low:
        bad("FE.1B.1 safety reuse dependency satisfaction not recorded")

    if (
        "completed" not in combined_low
        or "needs review" not in combined_low
        or "not reported" not in combined_low
    ):
        bad("agent-execution status mapping not fully recorded")

    for phrase in ("66d", "66c.4", "placeholder"):
        if phrase not in combined_low:
            bad(f"{phrase} placeholder reference missing")

    if "no fake counts" not in combined_low:
        bad("no-fake-counts statement missing")
    if "no fake controls" not in combined_low:
        bad("no-fake-controls statement missing")

    if "codex fe.1c implementation" not in combined_low and "codex fe.1c" not in combined_low:
        bad("Codex FE.1C implementation status not referenced")
    if "not authorized" not in combined_low and "unauthorized" not in combined_low:
        bad("Codex FE.1C unauthorized statement missing")

    if "fe.1d" not in combined_low:
        bad("FE.1D not referenced")

    for term in ("frontend runtime", "backend", "api", "database", "workflow"):
        if not re.search(rf"no [\w/]*{term}", combined_low):
            bad(f"no-{term}-change statement missing")

    if not re.search(r"no [\w/]*production action", combined_low):
        bad("no-production-action statement missing")
    if not re.search(r"no [\w/]*external action", combined_low):
        bad("no-external-action statement missing")

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

    print("  [OK] FE.1C source-of-truth merge record + test record present; PR #8/design/review")
    print("       commits referenced; FE.1C review PASS marker referenced; existing-data-only,")
    print("       /tasks status-filter usage, FE.1B.1 safety reuse satisfaction, and agent-")
    print("       execution status mapping recorded; 66D/66C.4/placeholder items honest; no fake")
    print(
        "       counts/controls; Codex FE.1C and FE.1D unauthorized; no frontend runtime/backend/"
    )
    print("       API/database/workflow change; no production/external action; Local Artifact")
    print("       Reconciliation recorded; no forbidden capability claims or sensitive identifiers")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
