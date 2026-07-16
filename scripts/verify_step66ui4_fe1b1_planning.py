#!/usr/bin/env python3
"""Step 66UI.4-FE.1B.1-P -- Safety Field Mapping Calibration planning verifier.

Confirms the mapping plan, frontend implementation boundary, planning
record, stage manifest, context receipt, and stage gate report for Step
66UI.4-FE.1B.1-P exist and state: that Codex remains unauthorized, that
FE.1C/FE.1D remain unauthorized, that no backend/API/database/workflow
change is claimed or required, that the /operations/safety response shape
change is forbidden, that a frontend-only future calibration is recorded,
that raw evidence preservation is recorded, that the conservative fallback
is recorded, and that the accepted Unavailable gap is referenced.

This is a documentation-only verifier: it reads files on the current
checkout and does not touch any runtime or remote host.

Marker: STEP66UI4_FE1B1_PLANNING_VERIFY: PASS | PASS_WITH_GAPS | FAIL
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DOCS = {
    "fe1b1-safety-field-mapping-plan": ROOT
    / "docs"
    / "frontend"
    / "66ui4-phase1-product-visual-language"
    / "fe1b1-safety-field-mapping-plan.md",
    "frontend-implementation-boundary": ROOT
    / "docs"
    / "contracts"
    / "66ui4-fe1b1-safety-field-mapping"
    / "frontend-implementation-boundary.md",
    "planning-record": ROOT
    / "docs"
    / "test"
    / "step66ui4-fe1b1-safety-field-mapping-planning-record.md",
    "stage-manifest": ROOT / "docs" / "stages" / "66ui4-fe1b1" / "stage-manifest.yaml",
    "context-receipt": ROOT / "docs" / "stages" / "66ui4-fe1b1" / "context-receipt.md",
    "stage-gate-report": ROOT / "docs" / "stages" / "66ui4-fe1b1" / "stage-gate-report.md",
}

PROGRESS = ROOT / "source" / "progress.md"

MARKER = "STEP66UI4_FE1B1_PLANNING_VERIFY"

SECRET_SHAPES = re.compile(
    r"(-----BEGIN [A-Z ]*PRIVATE KEY|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
    r"AKIA[0-9A-Z]{16}|xoxb-[A-Za-z0-9-]{10,}|sk-ant-[A-Za-z0-9_-]{20,})"
)
INFRA_SHAPES = re.compile(r"(10\.0\.1\.31|aiagent-swd|itadmin)", re.IGNORECASE)

FORBIDDEN_CLAIM_PATTERNS = (
    re.compile(r"backend (?:was|is) changed", re.IGNORECASE),
    re.compile(r"api (?:was|is) changed", re.IGNORECASE),
    re.compile(r"database (?:was|is) changed", re.IGNORECASE),
    re.compile(r"workflow (?:was|is) changed", re.IGNORECASE),
    re.compile(r"production action (?:was|is) triggered", re.IGNORECASE),
    re.compile(r"external action (?:was|is) triggered", re.IGNORECASE),
    re.compile(r"codex is authorized", re.IGNORECASE),
    re.compile(r"fe\.1c is authorized", re.IGNORECASE),
    re.compile(r"fe\.1d is authorized", re.IGNORECASE),
    re.compile(r"response shape (?:was|is) changed", re.IGNORECASE),
    re.compile(r"gap (?:was|is) fixed", re.IGNORECASE),
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
    "unchanged",
)
NEGATION_WINDOW = 160

FORBIDDEN_RUNTIME_PREFIXES = ("apps/", "services/", "infra/", "migrations/", "database/")

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


def _changed_paths() -> set[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", "HEAD"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    cached = subprocess.run(
        ["git", "diff", "--name-only", "--cached"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    lines = result.stdout.splitlines() + cached.stdout.splitlines()
    return {line.strip().replace("\\", "/") for line in lines if line.strip()}


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

    if "66ui.4-fe.1b.1-p" not in progress_low:
        bad("source/progress.md does not reference Stage 66UI.4-FE.1B.1-P")

    if MARKER not in "\n".join(texts.values()):
        bad("FE.1B.1-P planning marker not present verbatim")

    if "codex" not in combined_low or (
        "unauthorized" not in combined_low and "not authorized" not in combined_low
    ):
        bad("Codex-unauthorized statement missing")
    for phrase in ("fe.1c", "fe.1d"):
        if phrase not in combined_low:
            bad(f"{phrase} not referenced")

    for term in ("backend", "api", "database", "workflow"):
        if not re.search(rf"no [\w/]*{term}", combined_low):
            bad(f"no-{term}-change statement missing")

    if "response shape" not in combined_low:
        bad("/operations/safety response shape statement missing")
    if "unchanged" not in combined_low:
        bad("response-shape-unchanged statement missing")

    if "frontend-only" not in combined_low and "frontend only" not in combined_low:
        bad("frontend-only future calibration statement missing")

    if "raw evidence" not in combined_low or "accessible" not in combined_low:
        bad("raw evidence preservation statement missing")

    if "conservative" not in combined_low:
        bad("conservative fallback statement missing")

    if "unavailable" not in combined_low:
        bad("accepted Unavailable gap reference missing")
    if "dispatch_enabled" not in combined_low or "approval_required" not in combined_low:
        bad("accepted-gap field list missing")

    changed = _changed_paths()
    forbidden = [
        p for p in changed if any(p.startswith(prefix) for prefix in FORBIDDEN_RUNTIME_PREFIXES)
    ]
    if forbidden:
        bad(f"runtime paths touched by this planning stage: {', '.join(sorted(forbidden))}")

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

    print("  [OK] FE.1B.1-P mapping plan, frontend boundary, planning record, and stage artifacts")
    print(
        "       present; Codex/FE.1C/FE.1D unauthorized; no backend/API/database/workflow change;"
    )
    print("       /operations/safety response shape unchanged; frontend-only future calibration,")
    print("       raw evidence preservation, and conservative fallback recorded; accepted")
    print("       Unavailable gap referenced; no runtime files changed; no forbidden capability")
    print("       claims or sensitive identifiers")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
