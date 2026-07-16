#!/usr/bin/env python3
"""Step 66UI.4-FE.1B.1-R -- Claude Code review of Codex's FE.1B.1 Safety Field Mapping
Calibration (PR #9) verifier.

Confirms the review doc and review record exist and state: the reviewed PR #9 / branch / commit,
the FE.1B.1 mapping-calibration marker, that FE.1C/FE.1D remain unauthorized, that the change is
frontend-only mapping calibration, that no backend/API/database/workflow/infra change is claimed,
that the /operations/safety response shape is unchanged, that no production/external action is
claimed, that raw evidence remains accessible, that conservative fallback remains, that retired
field behavior was reviewed, that the source-of-truth planning-branch risk was reviewed, that no
local Windows paths were committed, and that a PASS / PASS_WITH_GAPS / FAIL review result was
recorded.

This is a documentation-only verifier: it reads files on the current checkout and does not touch
any runtime or remote host.

Marker: STEP66UI4_FE1B1_REVIEW_VERIFY: PASS | PASS_WITH_GAPS | FAIL
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DOCS = {
    "fe1b1-claude-code-review": ROOT
    / "docs"
    / "frontend"
    / "66ui4-phase1-product-visual-language"
    / "fe1b1-claude-code-review.md",
    "fe1b1-review-record": ROOT / "docs" / "test" / "step66ui4-fe1b1-review-record.md",
}

PROGRESS = ROOT / "source" / "progress.md"

MARKER = "STEP66UI4_FE1B1_REVIEW_VERIFY"
PR9_COMMIT = "974822d940c0e1ed9d061fbfe68fbed40ebd1fc0"
PR9_BRANCH = "frontend/66ui4-fe1b1-safety-field-mapping"
IMPLEMENTATION_MARKER = "STEP66UI4_FE1B1_MAPPING_CALIBRATION_VERIFY"

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
    re.compile(r"pr #9 (?:was|is) merged", re.IGNORECASE),
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

    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    texts = {name: p.read_text(encoding="utf-8") for name, p in DOCS.items()}
    progress_text = PROGRESS.read_text(encoding="utf-8")
    combined_low = _norm("\n".join(texts.values()))
    progress_low = _norm(progress_text)

    # 1/2. Review doc + review record exist -- checked above via DOCS.

    # 3. source/progress.md references FE.1B.1-R.
    if "66ui.4-fe.1b.1-r" not in progress_low:
        bad("source/progress.md does not reference Stage 66UI.4-FE.1B.1-R")

    # 4. Codex PR #9 / branch / commit referenced.
    if "pr #9" not in combined_low:
        bad("PR #9 reference missing")
    if PR9_BRANCH not in combined_low:
        bad("PR #9 branch reference missing")
    if PR9_COMMIT.lower() not in combined_low:
        bad("PR #9 commit reference missing")

    # 5. FE.1B.1 marker referenced.
    if IMPLEMENTATION_MARKER not in "\n".join(texts.values()):
        bad("FE.1B.1 implementation marker not referenced")

    # 6. FE.1C / FE.1D remain unauthorized.
    for phrase in ("fe.1c", "fe.1d"):
        if phrase not in combined_low:
            bad(f"{phrase} not referenced")
    if "unauthorized" not in combined_low and "not authorized" not in combined_low:
        bad("FE.1C/FE.1D unauthorized statement missing")

    # 7. Frontend-only mapping calibration documented.
    if "frontend-only" not in combined_low and "frontend only" not in combined_low:
        bad("frontend-only scope statement missing")
    if "mapping calibration" not in combined_low:
        bad("mapping calibration reference missing")

    # 8. No backend/API/database/workflow/infra changes claimed.
    for term in ("backend", "api", "database", "workflow", "infra"):
        if not re.search(rf"no [\w/]*{term}", combined_low):
            bad(f"no-{term}-change statement missing")

    # 9. /operations/safety response shape unchanged.
    if not re.search(r"no [\w/\s]*response shape change", combined_low) and (
        "response shape change" not in combined_low or "no" not in combined_low
    ):
        bad("/operations/safety response shape unchanged statement missing")
    if "/operations/safety" not in combined_low:
        bad("/operations/safety endpoint not referenced")

    # 10. No production/external action.
    if not re.search(r"no [\w/]*production action", combined_low):
        bad("no-production-action statement missing")
    if not re.search(r"no [\w/]*external action", combined_low):
        bad("no-external-action statement missing")

    # 11. Raw evidence remains accessible.
    if "evidence" not in combined_low or "accessible" not in combined_low:
        bad("raw-evidence-remains-accessible statement missing")

    # 12. Conservative fallback remains.
    if "conservative" not in combined_low:
        bad("conservative-fallback statement missing")

    # 13. Retired field behavior reviewed.
    for field in (
        "dispatch_enabled",
        "resume_dispatch_enabled",
        "approval_required",
        "requires_approval",
    ):
        if field not in combined_low:
            bad(f"retired field not reviewed: {field}")
    if "not applicable at this endpoint" not in combined_low:
        bad("retired-field evidence labeling not reviewed")

    # 14. Source-of-truth planning branch risk reviewed.
    if "source-of-truth" not in combined_low:
        bad("source-of-truth review section missing")
    if "review/66ui4-fe1b1-safety-field-mapping-plan" not in combined_low:
        bad("FE.1B.1 planning branch reference missing")
    if (
        "option c" not in combined_low
        and "option a" not in combined_low
        and "option b" not in combined_low
    ):
        bad("merge-order recommendation option missing")

    # 15. No local Windows paths committed.
    for name, text in texts.items():
        if WINDOWS_PATH_SHAPE.search(text):
            bad(f"{name} contains a local Windows absolute path")
    if "no local windows" not in combined_low and "windows absolute path" not in combined_low:
        bad("no-local-windows-path statement missing")

    # 16. Review result PASS / PASS_WITH_GAPS / FAIL recorded.
    if not re.search(r"\bpass\b|\bpass_with_gaps\b|\bfail\b", combined_low):
        bad("review result (PASS/PASS_WITH_GAPS/FAIL) not recorded")

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

    print("  [OK] FE.1B.1 Claude Code review doc + review record present; PR #9/branch/commit and")
    print(
        "       implementation marker referenced; FE.1C/FE.1D unauthorized; frontend-only mapping"
    )
    print("       calibration documented; no backend/API/database/workflow/infra change claimed;")
    print("       /operations/safety response shape unchanged; no production/external action; raw")
    print("       evidence accessible; conservative fallback preserved; retired-field behavior and")
    print("       source-of-truth planning-branch risk reviewed; no local Windows paths; review")
    print("       result recorded; no forbidden capability claims or sensitive identifiers")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
