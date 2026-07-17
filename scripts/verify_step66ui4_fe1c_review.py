#!/usr/bin/env python3
"""Step 66UI.4-FE.1C-R -- Claude Code review of Codex's FE.1C Overview implementation (PR #10)
verifier.

Confirms the review doc and review record exist and state: the reviewed PR #10 / branch / commit,
the Codex FE.1C implementation marker, a recorded review result (PASS / PASS_WITH_GAPS / FAIL), the
live agent-execution verification result, the current-work 5/updated_at-desc review, the
existing-data-only review, that no backend/API/database/workflow change is claimed, that no new
endpoint is claimed, that no fake counts/controls are claimed, that FE.1D remains unauthorized, that
Local Artifact Reconciliation is recorded, and that no local Windows path exposure is recorded.

This is a documentation-only verifier: it reads files on the current checkout and does not touch
any runtime or remote host.

Marker: STEP66UI4_FE1C_REVIEW_VERIFY: PASS | PASS_WITH_GAPS | FAIL
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DOCS = {
    "fe1c-claude-code-implementation-review": ROOT
    / "docs"
    / "frontend"
    / "66ui4-fe1c-overview-attention-first"
    / "claude-code-implementation-review.md",
    "fe1c-implementation-review-record": ROOT
    / "docs"
    / "test"
    / "step66ui4-fe1c-implementation-review-record.md",
}

PROGRESS = ROOT / "source" / "progress.md"

MARKER = "STEP66UI4_FE1C_REVIEW_VERIFY"
PR10_COMMIT = "816856a9ffe2b7a14aa0a1a070d9538f2231cf67"
PR10_BRANCH = "frontend/66ui4-fe1c-overview-attention-first"
IMPLEMENTATION_MARKER = "STEP66UI4_FE1C_IMPLEMENTATION_VERIFY"

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
    re.compile(r"fe\.1d is authorized", re.IGNORECASE),
    re.compile(r"pr #10 (?:was|is) merged", re.IGNORECASE),
    re.compile(r"deployed to test runtime", re.IGNORECASE),
    re.compile(r"live data (?:was|is) confirmed", re.IGNORECASE),
)
NEGATION_CUES = (
    "no ",
    "not ",
    "never ",
    "cannot ",
    "could not",
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

    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    texts = {name: p.read_text(encoding="utf-8") for name, p in DOCS.items()}
    progress_text = PROGRESS.read_text(encoding="utf-8")
    combined_low = _norm("\n".join(texts.values()))
    progress_low = _norm(progress_text)

    # 1/2. Review doc + review record exist -- checked above via DOCS.

    # 3. source/progress.md references FE.1C-R.
    if "66ui.4-fe.1c-r" not in progress_low:
        bad("source/progress.md does not reference Stage 66UI.4-FE.1C-R")

    # 4. PR #10 branch and commit referenced.
    if "pr #10" not in combined_low:
        bad("PR #10 reference missing")
    if PR10_BRANCH not in combined_low:
        bad("PR #10 branch reference missing")
    if PR10_COMMIT.lower() not in combined_low:
        bad("PR #10 commit reference missing")

    # 5. Codex FE.1C implementation marker referenced.
    if IMPLEMENTATION_MARKER not in "\n".join(texts.values()):
        bad("Codex FE.1C implementation marker not referenced")

    # 6. Review result PASS / PASS_WITH_GAPS / FAIL recorded.
    if not re.search(r"\bpass_with_gaps\b|\bpass\b|\bfail\b", combined_low):
        bad("review result (PASS/PASS_WITH_GAPS/FAIL) not recorded")

    # 7. Live agent-execution verification result recorded.
    if "agent-execution" not in combined_low and "agent execution" not in combined_low:
        bad("live agent-execution verification section missing")
    if "live" not in combined_low:
        bad("live-data verification reference missing")

    # 8. Current work 5 / updated_at desc reviewed.
    if "updated_at" not in combined_low:
        bad("current-work updated_at sort not reviewed")
    if " 5 " not in combined_low and "five" not in combined_low and "5 tasks" not in combined_low:
        bad("current-work 5-task count not reviewed")

    # 9. Existing-data-only reviewed.
    if "existing-data-only" not in combined_low and "existing data only" not in combined_low:
        bad("existing-data-only review statement missing")

    # 10. No backend/API/database/workflow change claimed.
    for term in ("backend", "api", "database", "workflow"):
        if not re.search(rf"no [\w/]*{term}", combined_low):
            bad(f"no-{term}-change statement missing")

    # 11. No new endpoint claimed.
    if "no new endpoint" not in combined_low:
        bad("no-new-endpoint statement missing")

    # 12. No fake counts / fake controls reviewed.
    if "no fake count" not in combined_low and "fake counts" not in combined_low:
        bad("no-fake-counts statement missing")
    if "fake control" not in combined_low:
        bad("fake-controls review statement missing")

    # 13. FE.1D remains unauthorized.
    if "fe.1d" not in combined_low:
        bad("FE.1D not referenced")
    if "unauthorized" not in combined_low and "not authorized" not in combined_low:
        bad("FE.1D unauthorized statement missing")

    # 14. Local Artifact Reconciliation recorded.
    if "local artifact reconciliation" not in combined_low:
        bad("Local Artifact Reconciliation section missing")

    # 15. No local Windows path exposure recorded.
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

    print("  [OK] FE.1C implementation review doc + review record present; PR #10/branch/commit")
    print("       and Codex implementation marker referenced; review result recorded; live agent-")
    print("       execution verification, current-work 5/updated_at-desc, and existing-data-only")
    print("       reviewed; no backend/API/database/workflow change; no new endpoint; no fake")
    print("       counts/controls; FE.1D unauthorized; Local Artifact Reconciliation recorded; no")
    print("       local Windows paths; no forbidden capability claims or sensitive identifiers")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
