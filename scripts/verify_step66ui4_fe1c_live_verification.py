#!/usr/bin/env python3
"""Step 66UI.4-FE.1C-LV -- restore test runtime + live agent-execution verification verifier.

Confirms the live verification record and status verification doc exist and state: the Product
Owner authorization, the runtime stopped-state baseline, the restoration action taken, the
/operations/agent-executions availability and observed status values, the mapping compatibility
result, that PR #10 review gap #1 is cleared, that PR #10 is neither merged nor deployed by this
stage, that no frontend/backend/API/database/workflow change is claimed, that no production/
external action is claimed, that FE.1D remains unauthorized, that Local Artifact Reconciliation is
recorded, and that no Windows/local path exposure is recorded.

This is a documentation-only verifier: it reads files on the current checkout and does not touch
any runtime or remote host.

Marker: STEP66UI4_FE1C_LIVE_VERIFICATION_VERIFY: PASS | PASS_WITH_GAPS | FAIL
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DOCS = {
    "fe1c-live-verification-record": ROOT
    / "docs"
    / "test"
    / "step66ui4-fe1c-live-agent-execution-verification-record.md",
    "fe1c-live-status-verification": ROOT
    / "docs"
    / "frontend"
    / "66ui4-fe1c-overview-attention-first"
    / "live-agent-execution-status-verification.md",
}

PROGRESS = ROOT / "source" / "progress.md"

MARKER = "STEP66UI4_FE1C_LIVE_VERIFICATION_VERIFY"
PR10_COMMIT = "816856a"

SECRET_SHAPES = re.compile(
    r"(-----BEGIN [A-Z ]*PRIVATE KEY|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
    r"AKIA[0-9A-Z]{16}|xoxb-[A-Za-z0-9-]{10,}|sk-ant-[A-Za-z0-9_-]{20,})"
)
INFRA_SHAPES = re.compile(r"(10\.0\.1\.31|aiagent-swd|itadmin)", re.IGNORECASE)
WINDOWS_PATH_SHAPE = re.compile(r"[A-Za-z]:[\\/]Users[\\/]", re.IGNORECASE)

FORBIDDEN_CLAIM_PATTERNS = (
    re.compile(r"frontend (?:code|runtime) (?:was|is) changed", re.IGNORECASE),
    re.compile(r"backend (?:was|is) changed", re.IGNORECASE),
    re.compile(r"api (?:was|is) changed", re.IGNORECASE),
    re.compile(r"database (?:was|is) changed", re.IGNORECASE),
    re.compile(r"workflow (?:was|is) changed", re.IGNORECASE),
    re.compile(r"production action (?:was|is) triggered", re.IGNORECASE),
    re.compile(r"external action (?:was|is) triggered", re.IGNORECASE),
    re.compile(r"pr #10 (?:was|is) merged", re.IGNORECASE),
    re.compile(r"pr #10 (?:was|is) deployed", re.IGNORECASE),
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
    if not PROGRESS.is_file():
        bad(f"missing progress log: {PROGRESS}")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    texts = {name: p.read_text(encoding="utf-8") for name, p in DOCS.items()}
    progress_text = PROGRESS.read_text(encoding="utf-8")
    combined_low = _norm("\n".join(texts.values()))
    progress_low = _norm(progress_text)

    if "66ui.4-fe.1c-lv" not in progress_low:
        bad("source/progress.md does not reference Stage 66UI.4-FE.1C-LV")

    if "product owner authorization" not in combined_low and "授權" not in "\n".join(
        texts.values()
    ):
        bad("Product Owner authorization not recorded")

    if "stopped" not in combined_low and "exited" not in combined_low:
        bad("runtime stopped-state baseline not recorded")

    if "restoration" not in combined_low and "restored" not in combined_low:
        bad("restoration action not recorded")

    if "agent-executions" not in combined_low or "reachable" not in combined_low:
        bad("/operations/agent-executions availability not recorded")

    if "completed" not in combined_low:
        bad("observed status values not recorded")

    if "mapping compatibility" not in combined_low and "maps correctly" not in combined_low:
        bad("mapping compatibility result not recorded")

    if "gap #1" not in combined_low and "gap 1" not in combined_low:
        bad("PR #10 review gap #1 closure not recorded")
    if "cleared" not in combined_low:
        bad("gap clearance statement missing")

    if PR10_COMMIT not in combined_low:
        bad("PR #10 commit reference missing")

    if (
        not re.search(r"pr #10 (?:merged|not merged)[:\s]", combined_low)
        and "pr #10 merged: no" not in combined_low
        and "pr #10 not merged" not in combined_low
    ):
        bad("PR #10 not-merged statement missing")
    if "pr #10 deployed: no" not in combined_low and "pr #10 not deployed" not in combined_low:
        bad("PR #10 not-deployed statement missing")

    for term in ("frontend code", "backend", "api", "database", "workflow"):
        if not re.search(rf"no [\w/]*{term}", combined_low):
            bad(f"no-{term}-change statement missing")

    if not re.search(
        r"no [\w/]*production[/\s]*external action|no production/external action", combined_low
    ):
        if not re.search(r"no [\w/]*production action", combined_low) or not re.search(
            r"no [\w/]*external action", combined_low
        ):
            bad("no-production/external-action statement missing")

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

    print("  [OK] FE.1C live verification record + status verification doc present; Product Owner")
    print("       authorization, runtime stopped-state baseline, restoration action, live")
    print("       agent-executions availability/status values, mapping compatibility, and gap #1")
    print("       closure all recorded; PR #10 not merged/deployed; no frontend/backend/API/")
    print("       database/workflow change; no production/external action; FE.1D unauthorized;")
    print("       Local Artifact Reconciliation recorded; no forbidden capability claims or")
    print("       sensitive identifiers")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
