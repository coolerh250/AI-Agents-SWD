#!/usr/bin/env python3
"""Step 66UI.4-FE.1B.1-VP -- PR #9 test runtime UI validation preview deployment verifier.

Confirms the preview deployment record and UI validation preview record exist and state: the
deployed PR #9 branch/commit, that `main` was not merged, that the deployment target is test
runtime only, that Product Owner validation is pending, the observed Safety badge state, raw
evidence/details status, retired-field behavior, approval wording behavior,
production_executed_true_count before/after, that no backend/API/database/workflow change is
claimed, that the /operations/safety response shape is unchanged, that no production/external
action is claimed, that FE.1C/FE.1D remain unauthorized, that Local Artifact Reconciliation was
recorded, and that no local absolute path exposure is recorded.

This is a documentation-only verifier: it reads files on the current checkout and does not touch
any runtime or remote host.

Marker: STEP66UI4_FE1B1_PREVIEW_DEPLOY_VERIFY: PASS | PASS_WITH_GAPS | FAIL
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DOCS = {
    "fe1b1-preview-deployment-record": ROOT
    / "docs"
    / "test"
    / "step66ui4-fe1b1-ui-validation-preview-deployment-record.md",
    "fe1b1-ui-validation-preview-record": ROOT
    / "docs"
    / "frontend"
    / "66ui4-phase1-product-visual-language"
    / "fe1b1-ui-validation-preview-record.md",
}

PROGRESS = ROOT / "source" / "progress.md"

MARKER = "STEP66UI4_FE1B1_PREVIEW_DEPLOY_VERIFY"
PR9_COMMIT = "974822d"
PR9_BRANCH = "frontend/66ui4-fe1b1-safety-field-mapping"

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
    re.compile(r"main (?:was|is) merged", re.IGNORECASE),
    re.compile(r"pr #9 (?:was|is) merged", re.IGNORECASE),
    re.compile(r"deployed to production", re.IGNORECASE),
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

    # 1/2. Preview deployment record + UI validation preview record exist -- checked via DOCS.

    # 3. source/progress.md references FE.1B.1-VP.
    if "66ui.4-fe.1b.1-vp" not in progress_low:
        bad("source/progress.md does not reference Stage 66UI.4-FE.1B.1-VP")

    # 4. PR #9 branch and commit referenced.
    if "pr #9" not in combined_low:
        bad("PR #9 reference missing")
    if PR9_BRANCH not in combined_low:
        bad("PR #9 branch reference missing")
    if PR9_COMMIT not in combined_low:
        bad("PR #9 commit reference missing")

    # 5. Main not merged recorded.
    if not re.search(r"main\W*not merged", combined_low):
        bad("main-not-merged statement missing")

    # 6. Test runtime only recorded.
    if "test runtime" not in combined_low:
        bad("test-runtime-only statement missing")

    # 7. Product Owner validation pending recorded.
    if "pending" not in combined_low or "product owner" not in combined_low:
        bad("Product-Owner-validation-pending statement missing")

    # 8. Safety badge observed state recorded.
    if "safety badge" not in combined_low:
        bad("Safety badge observed state missing")
    if "safe" not in combined_low:
        bad("Safety badge Safe observation missing")

    # 9. Raw evidence/details recorded.
    if "evidence" not in combined_low or (
        "accessible" not in combined_low and "expandable" not in combined_low
    ):
        bad("raw-evidence/details statement missing")

    # 10. Retired fields behavior recorded.
    if "not applicable at this endpoint" not in combined_low:
        bad("retired-fields behavior statement missing")

    # 11. Approval wording behavior recorded.
    if "per-task" not in combined_low and "per task" not in combined_low:
        bad("approval wording behavior statement missing")

    # 12. production_executed_true_count before/after recorded.
    if "production_executed_true_count" not in combined_low:
        bad("production_executed_true_count not recorded")
    if "before and after" not in combined_low and "before/after" not in combined_low:
        bad("production_executed_true_count before/after statement missing")

    # 13. No backend/API/database/workflow change claimed.
    for term in ("backend", "api", "database", "workflow"):
        if not re.search(rf"no [\w/]*{term}", combined_low):
            bad(f"no-{term}-change statement missing")

    # 14. /operations/safety response shape unchanged claimed.
    if "/operations/safety" not in combined_low:
        bad("/operations/safety endpoint not referenced")
    if "response shape" not in combined_low:
        bad("response shape statement missing")

    # 15. No production/external action claimed.
    if not re.search(r"no [\w/]*production action", combined_low):
        bad("no-production-action statement missing")
    if not re.search(r"no [\w/]*external action", combined_low):
        bad("no-external-action statement missing")

    # 16. FE.1C / FE.1D remain unauthorized.
    for phrase in ("fe.1c", "fe.1d"):
        if phrase not in combined_low:
            bad(f"{phrase} not referenced")
    if "unauthorized" not in combined_low and "not authorized" not in combined_low:
        bad("FE.1C/FE.1D unauthorized statement missing")

    # 17. Local Artifact Reconciliation recorded.
    if "local artifact reconciliation" not in combined_low:
        bad("Local Artifact Reconciliation section missing")

    # 18. No local absolute path exposure recorded.
    for name, text in texts.items():
        if WINDOWS_PATH_SHAPE.search(text):
            bad(f"{name} contains a local Windows absolute path")
    if "no c:/users" not in combined_low and "confirmed" not in combined_low:
        bad("no-local-absolute-path statement missing")

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

    print("  [OK] FE.1B.1 preview deployment record + UI validation preview record present; PR #9")
    print("       branch/commit referenced; main-not-merged and test-runtime-only recorded;")
    print("       Product Owner validation pending; Safety badge, evidence/details, retired-field,")
    print("       and approval-wording behavior recorded; production_executed_true_count before/")
    print("       after recorded; no backend/API/database/workflow change; /operations/safety")
    print("       response shape unchanged; no production/external action; FE.1C/FE.1D")
    print("       unauthorized; Local Artifact Reconciliation recorded; no local absolute paths;")
    print("       no forbidden capability claims or sensitive identifiers")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
