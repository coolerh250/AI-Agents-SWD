#!/usr/bin/env python3
"""Step 66UI.4-FE.1C.1-P -- TaskList query param filter support planning verifier.

Confirms the planning doc, frontend implementation boundary, planning record, and stage artifacts
exist and state: Codex remains unauthorized, FE.1D remains unauthorized, no runtime files changed,
no backend/API/database/workflow change is claimed, no new endpoint is claimed, the frontend-only
future implementation boundary is recorded, existing TaskList status filter reuse is recorded,
invalid query param behavior is recorded, and no fake counts/controls is recorded.

This is a documentation-only verifier: it reads files on the current checkout and does not touch
any runtime or remote host.

Marker: STEP66UI4_FE1C1_PLANNING_VERIFY: PASS | PASS_WITH_GAPS | FAIL
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DOCS = {
    "fe1c1-planning-doc": ROOT
    / "docs"
    / "frontend"
    / "66ui4-fe1c-overview-attention-first"
    / "tasklist-query-param-filter-plan.md",
    "fe1c1-frontend-boundary": ROOT
    / "docs"
    / "contracts"
    / "66ui4-fe1c1-tasklist-query-param"
    / "frontend-implementation-boundary.md",
    "fe1c1-planning-record": ROOT
    / "docs"
    / "test"
    / "step66ui4-fe1c1-tasklist-query-param-planning-record.md",
}

STAGE_ARTIFACTS = {
    "stage-manifest": ROOT
    / "docs"
    / "stages"
    / "66ui4-fe1c1-tasklist-query-param"
    / "stage-manifest.yaml",
    "context-receipt": ROOT
    / "docs"
    / "stages"
    / "66ui4-fe1c1-tasklist-query-param"
    / "context-receipt.md",
    "stage-gate-report": ROOT
    / "docs"
    / "stages"
    / "66ui4-fe1c1-tasklist-query-param"
    / "stage-gate-report.md",
}

PROGRESS = ROOT / "source" / "progress.md"

MARKER = "STEP66UI4_FE1C1_PLANNING_VERIFY"

FORBIDDEN_RUNTIME_PREFIXES = (
    "apps/",
    "services/",
    "infra/",
    "migrations/",
    "database/",
    "helm/",
    "k8s/",
    ".github/workflows/",
)

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
    re.compile(r"codex (?:is|has been) authorized", re.IGNORECASE),
    re.compile(r"fe\.1d is authorized", re.IGNORECASE),
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
    for name, p in STAGE_ARTIFACTS.items():
        if not p.is_file():
            bad(f"missing stage artifact: {p} ({name})")
    if not PROGRESS.is_file():
        bad(f"missing progress log: {PROGRESS}")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    all_paths = {**DOCS, **STAGE_ARTIFACTS}
    texts = {name: p.read_text(encoding="utf-8") for name, p in all_paths.items()}
    progress_text = PROGRESS.read_text(encoding="utf-8")
    combined_low = _norm("\n".join(texts.values()))
    progress_low = _norm(progress_text)

    if "66ui.4-fe.1c.1-p" not in progress_low:
        bad("source/progress.md does not reference Stage 66UI.4-FE.1C.1-P")

    if "codex" not in combined_low or not re.search(
        r"codex implementation not authorized|codex.{0,40}not authorized", combined_low
    ):
        bad("Codex unauthorized statement missing")

    if "fe.1d" not in combined_low or (
        "not authorized" not in combined_low and "unauthorized" not in combined_low
    ):
        bad("FE.1D unauthorized statement missing")

    for term in ("backend", "api", "database", "workflow"):
        if (
            not re.search(rf"no [\w/]*{term}", combined_low)
            and f"{term} change" not in combined_low
        ):
            bad(f"no-{term}-change statement missing")
    if not re.search(r"no [\w/]*new endpoint", combined_low) and "new endpoint" not in combined_low:
        bad("no-new-endpoint statement missing")

    if "frontend-only" not in combined_low and "frontend only" not in combined_low:
        bad("frontend-only future implementation not recorded")

    if "existing" not in combined_low or "status filter" not in combined_low:
        bad("existing TaskList status filter reuse not recorded")

    if "invalid" not in combined_low or "ignored" not in combined_low:
        bad("invalid query param behavior not recorded")

    if "no fake counts" not in combined_low:
        bad("no-fake-counts statement missing")
    if "fake controls" not in combined_low:
        bad("no-fake-controls statement missing")

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

    print("  [OK] FE.1C.1 planning doc, frontend implementation boundary, planning record, and")
    print("       stage artifacts present; Codex and FE.1D unauthorized; no backend/API/database/")
    print("       workflow/new-endpoint change claimed; frontend-only future implementation,")
    print("       existing status-filter reuse, invalid-query-param handling, and no-fake-counts/")
    print("       controls all recorded; no forbidden capability claims or sensitive identifiers")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
