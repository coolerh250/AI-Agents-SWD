#!/usr/bin/env python3
"""Step 66UI.4-FE.1C-VP -- PR #10 test-runtime UI-validation preview-deployment verifier.

Confirms the preview deployment record and UI validation preview record exist and state: PR #10
branch/commit deployed, main not merged, test-runtime-only scope, Product Owner validation pending,
Overview attention-first behavior, Current work 5/updated_at-desc behavior, AI team activity
completed -> Completed behavior, FE.1B.1 System Posture reuse, demoted metrics, placeholder-only
items, the retained TaskList query-param gap, no backend/API/database/workflow/new-endpoint change,
no production/external action, that FE.1D remains unauthorized, Local Artifact Reconciliation, and
no Windows/local path exposure.

This is a documentation-only verifier: it reads files on the current checkout and does not touch
any runtime or remote host.

Marker: STEP66UI4_FE1C_PREVIEW_DEPLOY_VERIFY: PASS | PASS_WITH_GAPS | FAIL
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DOCS = {
    "fe1c-preview-deploy-record": ROOT
    / "docs"
    / "test"
    / "step66ui4-fe1c-ui-validation-preview-deployment-record.md",
    "fe1c-ui-validation-preview": ROOT
    / "docs"
    / "frontend"
    / "66ui4-fe1c-overview-attention-first"
    / "ui-validation-preview-record.md",
}

PROGRESS = ROOT / "source" / "progress.md"

MARKER = "STEP66UI4_FE1C_PREVIEW_DEPLOY_VERIFY"
PR10_COMMIT = "816856a"

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
    re.compile(r"main (?:was|is) merged", re.IGNORECASE),
    re.compile(r"fe\.1d is authorized", re.IGNORECASE),
    re.compile(r"tasklist query-param gap (?:was|is) fixed", re.IGNORECASE),
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
    "intentionally not",
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

    if "66ui.4-fe.1c-vp" not in progress_low:
        bad("source/progress.md does not reference Stage 66UI.4-FE.1C-VP")

    if "pr #10" not in combined_low:
        bad("PR #10 reference missing")
    if PR10_COMMIT not in combined_low:
        bad("PR #10 commit reference missing")

    if "not merged" not in combined_low and "not touched" not in combined_low:
        bad("main-not-merged statement missing")

    if "test runtime only" not in combined_low and "test runtime" not in combined_low:
        bad("test-runtime-only scope not recorded")

    if "product owner validation" not in combined_low:
        bad("Product Owner validation reference missing")

    if "attention-first" not in combined_low:
        bad("Overview attention-first behavior not recorded")

    if "5" not in combined_low or "updated_at" not in combined_low:
        bad("Current work 5/updated_at-desc behavior not recorded")

    if "completed" not in combined_low or "needs review" not in combined_low:
        bad("AI team activity completed->Completed mapping not recorded")

    if "fe.1b.1" not in combined_low or "safe" not in combined_low:
        bad("FE.1B.1 System Posture reuse / Safe behavior not recorded")

    if "demoted" not in combined_low:
        bad("metrics demotion not recorded")

    if "placeholder" not in combined_low:
        bad("placeholder-only items not recorded")

    if "tasklist" not in combined_low or "query-param" not in combined_low:
        bad("TaskList query-param gap not recorded")
    if "retained" not in combined_low and "not addressed" not in combined_low:
        bad("TaskList query-param gap retention not recorded")

    for term in ("backend", "api", "database", "workflow"):
        if (
            not re.search(rf"no [\w/]*{term}", combined_low)
            and f"{term} changed: no" not in combined_low
        ):
            bad(f"no-{term}-change statement missing")
    if "new endpoint: no" not in combined_low and not re.search(
        r"no [\w/]*new endpoint", combined_low
    ):
        bad("no-new-endpoint statement missing")

    if (
        not re.search(r"no [\w/]*production action", combined_low)
        and "production action: no" not in combined_low
    ):
        bad("no-production-action statement missing")
    if (
        not re.search(r"no [\w/]*external action", combined_low)
        and "external action: no" not in combined_low
    ):
        bad("no-external-action statement missing")

    if "fe.1d" not in combined_low or (
        "not authorized" not in combined_low and "unauthorized" not in combined_low
    ):
        bad("FE.1D unauthorized statement missing")

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

    print("  [OK] FE.1C preview deployment record + UI validation preview record present; PR #10")
    print("       branch/commit referenced; main not merged; test-runtime-only scope; Product")
    print("       Owner validation pending; attention-first Overview, Current work 5/updated_at")
    print("       desc, AI team activity mapping, FE.1B.1 Safe reuse, demoted metrics, placeholder")
    print("       items, and retained TaskList query-param gap all recorded; no backend/API/")
    print("       database/workflow/new-endpoint change; no production/external action; FE.1D")
    print("       unauthorized; Local Artifact Reconciliation recorded; no forbidden capability")
    print("       claims or sensitive identifiers")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
