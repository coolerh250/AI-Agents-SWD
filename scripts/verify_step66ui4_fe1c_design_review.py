#!/usr/bin/env python3
"""Step 66UI.4-FE.1C-R -- Overview Attention-first design review verifier.

Confirms the Claude Code architecture review, frontend implementation
boundary, Codex readiness boundary, and review record for Step 66UI.4-FE.1C
exist and state: the reviewed design PR #8/branch/commit, that Codex remains
unauthorized, the existing-data-only boundary, no backend/API/database/
workflow change required, no production/external action required, 66D/66C.4
placeholders, no fake controls, no new endpoints, the FE.1B dependency/reuse
recommendation, the /tasks usage recommendation, the agent-execution status
mapping recommendation, that no runtime files were changed, and a stated
review result.

This is a documentation-only verifier: it reads files on the current
checkout and does not touch any runtime or remote host.

Marker: STEP66UI4_FE1C_DESIGN_REVIEW_VERIFY: PASS | PASS_WITH_GAPS | FAIL
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REVIEW_DOCS = {
    "claude-code-architecture-review": ROOT
    / "docs"
    / "design"
    / "66ui4-fe1c-overview-attention-first"
    / "claude-code-architecture-review.md",
    "frontend-implementation-boundary": ROOT
    / "docs"
    / "contracts"
    / "66ui4-fe1c-overview-attention-first"
    / "frontend-implementation-boundary.md",
    "codex-readiness-boundary": ROOT
    / "docs"
    / "frontend"
    / "66ui4-fe1c-overview-attention-first"
    / "codex-readiness-boundary.md",
    "design-review-record": ROOT / "docs" / "test" / "step66ui4-fe1c-design-review-record.md",
}

PROGRESS = ROOT / "source" / "progress.md"

MARKER = "STEP66UI4_FE1C_DESIGN_REVIEW_VERIFY"

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
    re.compile(r"pr #8 (?:has been|was) merged", re.IGNORECASE),
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
    for name, p in REVIEW_DOCS.items():
        if not p.is_file():
            bad(f"missing review doc: {p} ({name})")
    if not PROGRESS.is_file():
        bad(f"missing progress log: {PROGRESS}")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    texts = {name: p.read_text(encoding="utf-8") for name, p in REVIEW_DOCS.items()}
    progress_text = PROGRESS.read_text(encoding="utf-8")
    combined_low = _norm("\n".join(texts.values()))
    progress_low = _norm(progress_text)

    if "pr #8" not in combined_low:
        bad("PR #8 reference missing")
    if "design/66ui4-fe1c-overview-attention-first" not in combined_low:
        bad("branch reference missing")
    if "0c7762e" not in combined_low:
        bad("commit reference missing")
    if "66ui.4-fe.1c-r" not in progress_low:
        bad("source/progress.md does not reference Stage 66UI.4-FE.1C-R")

    if MARKER not in "\n".join(texts.values()):
        bad("FE.1C design review marker not present verbatim")

    if "codex" not in combined_low or (
        "unauthorized" not in combined_low and "not authorized" not in combined_low
    ):
        bad("Codex-unauthorized statement missing")

    if "existing-data-only" not in combined_low and "existing data only" not in combined_low:
        bad("existing-data-only boundary statement missing")

    for term in ("backend", "api", "database", "workflow"):
        if not re.search(rf"no [\w/]*{term}", combined_low):
            bad(f"no-{term}-change-required statement missing")

    if not re.search(r"no [\w/]*production action", combined_low):
        bad("no-production-action-required statement missing")
    if not re.search(r"no [\w/]*external action", combined_low):
        bad("no-external-action-required statement missing")

    if "66d" not in combined_low or "66c.4" not in combined_low:
        bad("66D/66C.4 placeholder reference missing")
    if "placeholder" not in combined_low:
        bad("placeholder strategy reference missing")

    if "no fake" not in combined_low and "fake control" not in combined_low:
        bad("no-fake-controls statement missing")
    if "no new endpoint" not in combined_low and "new endpoint" not in combined_low:
        bad("no-new-endpoints statement missing")

    if "fe.1b" not in combined_low or "reuse" not in combined_low:
        bad("FE.1B dependency/reuse recommendation missing")
    if "merged to `main`" not in combined_low and "merged to main" not in combined_low:
        bad("FE.1B merge-order precondition missing")

    if "/tasks" not in combined_low:
        bad("/tasks usage recommendation missing")

    if "agent-execution" not in combined_low and "agent_executions" not in combined_low:
        bad("agent-execution status mapping recommendation missing")
    if "not reported" not in combined_low:
        bad("conservative not-reported fallback missing from status mapping")

    changed = _changed_paths()
    forbidden = [
        p for p in changed if any(p.startswith(prefix) for prefix in FORBIDDEN_RUNTIME_PREFIXES)
    ]
    if forbidden:
        bad(f"runtime paths touched by this review stage: {', '.join(sorted(forbidden))}")
    if "no runtime" not in combined_low and "runtime files changed" not in combined_low:
        bad("no-runtime-files-changed statement missing")

    if not any(
        v in combined_low for v in ("pass_with_gaps", "**pass.**", "verdict: **pass", "pass.")
    ):
        bad("review result (PASS/PASS_WITH_GAPS/FAIL) not stated")

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

    print("  [OK] FE.1C architecture review + boundaries + review record present; PR #8/branch/")
    print("       commit referenced; Codex unauthorized; existing-data-only boundary; no backend/")
    print(
        "       API/database/workflow/production/external requirement; 66D/66C.4 placeholders; no"
    )
    print("       fake controls/new endpoints; FE.1B reuse+merge-order precondition, /tasks usage,")
    print("       and agent-execution status mapping recommendations recorded; no runtime files")
    print("       changed; review result stated; no forbidden capability claims or sensitive")
    print("       identifiers")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
