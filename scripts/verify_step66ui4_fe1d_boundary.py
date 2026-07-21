#!/usr/bin/env python3
"""Step 66UI.4-FE.1D-BOUNDARY -- Codex implementation boundary consolidation verifier.

Confirms the boundary, PO decision record, slicing plan, and consolidation record all exist and
state: Codex remains unauthorized, "+ Create task" keep decision, delivery_package_ready_for_
admin_console rename deferred to 66D, SPA deep-link fallback excluded, two-way URL sync excluded,
no backend/API/database/workflow/new-endpoint change claimed, no runtime source files changed,
Slice 1 and Slice 2 recorded, and Product Owner validation required.

This is a documentation-only verifier: it reads files on the current checkout and does not touch
any runtime or remote host.

Marker: STEP66UI4_FE1D_BOUNDARY_VERIFY: PASS | PASS_WITH_GAPS | FAIL
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

CONTRACT_DOCS = {
    "codex-implementation-boundary": ROOT
    / "docs"
    / "contracts"
    / "66ui4-fe1d-navigation-microcopy"
    / "codex-implementation-boundary.md",
    "po-decision-record": ROOT
    / "docs"
    / "contracts"
    / "66ui4-fe1d-navigation-microcopy"
    / "po-decision-record.md",
    "implementation-slicing-plan": ROOT
    / "docs"
    / "contracts"
    / "66ui4-fe1d-navigation-microcopy"
    / "implementation-slicing-plan.md",
}

RECORD_DOC = ROOT / "docs" / "test" / "step66ui4-fe1d-boundary-consolidation-record.md"

STAGE_DOCS = {
    "stage-manifest": ROOT / "docs" / "stages" / "66ui4-fe1d-boundary" / "stage-manifest.yaml",
    "context-receipt": ROOT / "docs" / "stages" / "66ui4-fe1d-boundary" / "context-receipt.md",
    "stage-gate-report": ROOT / "docs" / "stages" / "66ui4-fe1d-boundary" / "stage-gate-report.md",
}

PROGRESS = ROOT / "source" / "progress.md"

MARKER = "STEP66UI4_FE1D_BOUNDARY_VERIFY"

ALL_TEXT_DOCS = {**CONTRACT_DOCS, "boundary-consolidation-record": RECORD_DOC}

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
    re.compile(r"pr #12 (?:has been|was) merged", re.IGNORECASE),
    re.compile(r"codex is authorized", re.IGNORECASE),
    re.compile(r"fe\.1d implementation is authorized", re.IGNORECASE),
    re.compile(r"spa deep-link fallback (?:was|is) fixed", re.IGNORECASE),
    re.compile(r"deployment (?:was|is) performed", re.IGNORECASE),
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
    for name, p in CONTRACT_DOCS.items():
        if not p.is_file():
            bad(f"missing contract doc: {p} ({name})")
    if not RECORD_DOC.is_file():
        bad(f"missing boundary consolidation record: {RECORD_DOC}")
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

    if "66ui.4-fe.1d-boundary" not in progress_low:
        bad("source/progress.md does not reference Stage 66UI.4-FE.1D-BOUNDARY")

    if "product owner" not in combined_low or "授權" not in "\n".join(texts.values()):
        bad("Product Owner authorization not recorded")

    if "codex" not in combined_low or (
        "codex remains unauthorized" not in combined_low and "not authorized" not in combined_low
    ):
        bad("Codex unauthorized statement missing")

    if '"+ create task"' not in combined_low and "create task" not in combined_low:
        bad('"+ Create task" keep decision not recorded')
    if "unchanged" not in combined_low:
        bad('"+ Create task" unchanged statement missing')

    if "delivery_package_ready_for_admin_console" not in combined_low:
        bad("delivery_package_ready_for_admin_console reference missing")
    if "66d" not in combined_low or "defer" not in combined_low:
        bad("delivery_package_ready_for_admin_console deferred-to-66D statement missing")

    if "spa deep-link" not in combined_low:
        bad("SPA deep-link fallback exclusion missing")
    if "two-way url sync" not in combined_low:
        bad("two-way URL sync exclusion missing")

    for term in ("backend", "api", "database", "workflow"):
        if (
            not re.search(rf"no [\w/]*{term}", combined_low)
            and f"{term} change" not in combined_low
        ):
            bad(f"no-{term}-change statement missing")
    if not re.search(r"no [\w/]*new endpoint", combined_low) and "new endpoint" not in combined_low:
        bad("no-new-endpoint statement missing")

    if "no runtime" not in combined_low and "runtime source files changed" not in combined_low:
        bad("no-runtime-source-files-changed statement missing")

    if "slice 1" not in combined_low:
        bad("Slice 1 not recorded")
    if "slice 2" not in combined_low:
        bad("Slice 2 not recorded")

    if "product owner validation" not in combined_low:
        bad("Product Owner validation requirement not recorded")

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

    print("  [OK] Codex implementation boundary + PO decision record + implementation slicing plan")
    print(
        "       + boundary consolidation record + stage manifest/context-receipt/stage-gate-report"
    )
    print(
        '       all present; Codex unauthorized; "+ Create task" kept unchanged; delivery_package_'
    )
    print(
        "       ready_for_admin_console rename deferred to 66D; SPA deep-link fallback and two-way"
    )
    print("       URL sync excluded; no backend/API/database/workflow/new-endpoint change; no")
    print("       runtime source files changed; Slice 1 and Slice 2 recorded; Product Owner")
    print("       validation requirement recorded; no forbidden capability claims or sensitive")
    print("       identifiers")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
