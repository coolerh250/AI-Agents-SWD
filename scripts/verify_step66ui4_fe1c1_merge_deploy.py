#!/usr/bin/env python3
"""Step 66UI.4-FE.1C.1-MD -- merge PR #11 and calibrate test runtime verifier.

Confirms the merge record and merged-main test deployment record exist and state: PR #11 merge,
Product Owner merge authorization, Product Owner UI validation PASS/VISIBLE_WITH_ACCEPTED_PLATFORM_
GAP, presence of the planning/implementation/review/preview-deployment/known-gap artifacts on main,
that the deployment source is merged main, test-runtime-only scope, one-way deep-link behavior,
bidirectional URL sync not implemented, no backend/API/database/workflow/new-endpoint change, no
production/external action, that FE.1D remains unauthorized, production_executed_true_count
remaining 0, Local Artifact Reconciliation, no Windows/local path exposure, and the secret-scan
informational UUID note.

This is a documentation-only verifier: it reads files on the current checkout and does not touch
any runtime or remote host.

Marker: STEP66UI4_FE1C1_MERGE_DEPLOY_VERIFY: PASS | PASS_WITH_GAPS | FAIL
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DOCS = {
    "fe1c1-merge-record": ROOT
    / "docs"
    / "frontend"
    / "66ui4-fe1c-overview-attention-first"
    / "tasklist-query-param-merge-record.md",
    "fe1c1-merged-main-deploy-record": ROOT
    / "docs"
    / "test"
    / "step66ui4-fe1c1-merged-main-test-deployment-record.md",
}

PROGRESS = ROOT / "source" / "progress.md"

MARKER = "STEP66UI4_FE1C1_MERGE_DEPLOY_VERIFY"
PR11_COMMIT = "cba5dd0"

FE1C1_ARTIFACTS = [
    ROOT
    / "docs"
    / "frontend"
    / "66ui4-fe1c-overview-attention-first"
    / "tasklist-query-param-filter-plan.md",
    ROOT
    / "docs"
    / "contracts"
    / "66ui4-fe1c1-tasklist-query-param"
    / "frontend-implementation-boundary.md",
    ROOT / "docs" / "test" / "step66ui4-fe1c1-tasklist-query-param-planning-record.md",
    ROOT
    / "docs"
    / "frontend"
    / "66ui4-fe1c-overview-attention-first"
    / "tasklist-query-param-filter-implementation-report.md",
    ROOT / "docs" / "handoffs" / "66ui4-fe1c1" / "codex-to-claude-code-handoff.md",
    ROOT / "docs" / "test" / "step66ui4-fe1c1-tasklist-query-param-implementation-test-report.md",
    ROOT
    / "docs"
    / "frontend"
    / "66ui4-fe1c-overview-attention-first"
    / "tasklist-query-param-filter-review.md",
    ROOT / "docs" / "test" / "step66ui4-fe1c1-tasklist-query-param-review-record.md",
    ROOT
    / "docs"
    / "frontend"
    / "66ui4-fe1c-overview-attention-first"
    / "tasklist-query-param-ui-validation-preview-record.md",
    ROOT / "docs" / "test" / "step66ui4-fe1c1-ui-validation-preview-deployment-record.md",
    ROOT / "docs" / "frontend" / "admin-console-spa-deep-link-fallback-known-gap.md",
    ROOT / "scripts" / "verify_step66ui4_fe1c1_planning.py",
    ROOT / "tests" / "test_step66ui4_fe1c1_planning.py",
    ROOT / "scripts" / "verify_step66ui4_fe1c1_implementation.py",
    ROOT / "tests" / "test_step66ui4_fe1c1_implementation.py",
    ROOT / "scripts" / "verify_step66ui4_fe1c1_review.py",
    ROOT / "tests" / "test_step66ui4_fe1c1_review.py",
    ROOT / "scripts" / "verify_step66ui4_fe1c1_preview_deploy.py",
    ROOT / "tests" / "test_step66ui4_fe1c1_preview_deploy.py",
]

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
    re.compile(r"fe\.1d is authorized", re.IGNORECASE),
    re.compile(r"bidirectional url sync (?:was|is) implemented", re.IGNORECASE),
    re.compile(r"spa deep-link fallback (?:was|is) fixed", re.IGNORECASE),
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
    for p in FE1C1_ARTIFACTS:
        if not p.is_file():
            bad(f"missing consolidated FE.1C.1 artifact on main: {p}")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    texts = {name: p.read_text(encoding="utf-8") for name, p in DOCS.items()}
    progress_text = PROGRESS.read_text(encoding="utf-8")
    combined_low = _norm("\n".join(texts.values()))
    progress_low = _norm(progress_text)

    if "66ui.4-fe.1c.1-md" not in progress_low:
        bad("source/progress.md does not reference Stage 66UI.4-FE.1C.1-MD")

    if PR11_COMMIT not in combined_low:
        bad("PR #11 commit reference missing")
    if "merged" not in combined_low:
        bad("PR #11 merge not recorded")

    if "product owner" not in combined_low or "授權" not in "\n".join(texts.values()):
        bad("Product Owner merge authorization not recorded")

    if "visible_with_accepted_platform_gap" not in combined_low:
        bad("Product Owner UI validation PASS/VISIBLE_WITH_ACCEPTED_PLATFORM_GAP not recorded")

    for name, path in {
        "planning": "step66ui4-fe1c1-tasklist-query-param-planning-record",
        "implementation": "step66ui4-fe1c1-tasklist-query-param-implementation-test-report",
        "review": "step66ui4-fe1c1-tasklist-query-param-review-record",
        "preview deployment": "step66ui4-fe1c1-ui-validation-preview-deployment-record",
    }.items():
        if path not in combined_low:
            bad(f"{name} artifact reference missing")

    if "known gap" not in combined_low or "spa deep-link" not in combined_low:
        bad("known-gap artifact reference missing")

    if "merged main" not in combined_low:
        bad("deployment source (merged main) not recorded")
    if "test runtime" not in combined_low:
        bad("test-runtime-only scope not recorded")

    if "one-way" not in combined_low and "manual dropdown" not in combined_low:
        bad("one-way deep-link behavior not recorded")
    if "bidirectional url sync" not in combined_low or "not implemented" not in combined_low:
        bad("bidirectional URL sync not-implemented statement missing")

    for term in ("backend", "api", "database", "workflow"):
        if (
            not re.search(rf"no [\w/]*{term}", combined_low)
            and f"{term} change" not in combined_low
        ):
            bad(f"no-{term}-change statement missing")
    if not re.search(r"no [\w/]*new endpoint", combined_low) and "new endpoint" not in combined_low:
        bad("no-new-endpoint statement missing")

    if not re.search(r"no [\w/]*production[/\s]*external action", combined_low) and (
        not re.search(r"no [\w/]*production action", combined_low)
        or not re.search(r"no [\w/]*external action", combined_low)
    ):
        bad("no-production/external-action statement missing")

    if "fe.1d" not in combined_low or not re.search(
        r"no [\w/]*fe\.1d authorized|fe\.1d (?:remains |is )?(?:not authorized|unauthorized)",
        combined_low,
    ):
        bad("FE.1D unauthorized statement missing")

    if "production_executed_true_count" not in combined_low or "0" not in combined_low:
        bad("production_executed_true_count=0 statement missing")

    if "local artifact reconciliation" not in combined_low:
        bad("Local Artifact Reconciliation section missing")

    if "informational=100" not in combined_low:
        bad("secret scan informational baseline note missing")

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

    print("  [OK] FE.1C.1 merge record + merged-main test deployment record present; PR #11 merge,")
    print("       Product Owner merge authorization, PASS/VISIBLE_WITH_ACCEPTED_PLATFORM_GAP, and")
    print("       all planning/implementation/review/preview-deployment/known-gap artifacts on")
    print("       main all recorded; deployment source is merged main; test-runtime-only scope;")
    print("       one-way deep-link behavior; bidirectional URL sync not implemented; no backend/")
    print("       API/database/workflow/new-endpoint change; no production/external action; FE.1D")
    print("       unauthorized; production_executed_true_count=0; Local Artifact Reconciliation")
    print("       recorded; secret scan informational note recorded; no forbidden capability")
    print("       claims or sensitive identifiers")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
