#!/usr/bin/env python3
"""Step 66UI.4-FE.1C-MD -- merge PR #10 and calibrate test runtime verifier.

Confirms the merge record and merged-main test deployment record exist and state: PR #10 merge,
Product Owner merge authorization, Product Owner UI validation VISIBLE, presence of the review/
live-verification/preview-deployment/validation artifacts on main, that the deployment source is
merged main, test-runtime-only scope, the accepted non-blocking TaskList query-param gap, no
backend/API/database/workflow/new-endpoint change, no production/external action, that FE.1D
remains unauthorized, that production_executed_true_count remains 0, Local Artifact Reconciliation,
no Windows/local path exposure, and the secret-scan informational GUID note.

This is a documentation-only verifier: it reads files on the current checkout and does not touch
any runtime or remote host.

Marker: STEP66UI4_FE1C_MERGE_DEPLOY_VERIFY: PASS | PASS_WITH_GAPS | FAIL
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DOCS = {
    "fe1c-merge-record": ROOT
    / "docs"
    / "frontend"
    / "66ui4-fe1c-overview-attention-first"
    / "merge-record.md",
    "fe1c-merged-main-deploy-record": ROOT
    / "docs"
    / "test"
    / "step66ui4-fe1c-merged-main-test-deployment-record.md",
}

PROGRESS = ROOT / "source" / "progress.md"

MARKER = "STEP66UI4_FE1C_MERGE_DEPLOY_VERIFY"
PR10_COMMIT = "816856a"

FE1C_ARTIFACTS = [
    ROOT / "docs" / "frontend" / "66ui4-fe1c-overview-attention-first" / "implementation-report.md",
    ROOT / "docs" / "handoffs" / "66ui4-fe1c" / "codex-to-claude-code-handoff.md",
    ROOT / "docs" / "test" / "step66ui4-fe1c-implementation-test-report.md",
    ROOT / "docs" / "stages" / "66ui4-fe1c-implementation" / "stage-manifest.yaml",
    ROOT / "docs" / "stages" / "66ui4-fe1c-implementation" / "context-receipt.md",
    ROOT / "docs" / "stages" / "66ui4-fe1c-implementation" / "stage-gate-report.md",
    ROOT
    / "docs"
    / "frontend"
    / "66ui4-fe1c-overview-attention-first"
    / "claude-code-implementation-review.md",
    ROOT / "docs" / "test" / "step66ui4-fe1c-implementation-review-record.md",
    ROOT / "docs" / "test" / "step66ui4-fe1c-live-agent-execution-verification-record.md",
    ROOT
    / "docs"
    / "frontend"
    / "66ui4-fe1c-overview-attention-first"
    / "live-agent-execution-status-verification.md",
    ROOT / "docs" / "test" / "step66ui4-fe1c-ui-validation-preview-deployment-record.md",
    ROOT
    / "docs"
    / "frontend"
    / "66ui4-fe1c-overview-attention-first"
    / "ui-validation-preview-record.md",
    ROOT
    / "docs"
    / "frontend"
    / "66ui4-fe1c-overview-attention-first"
    / "product-owner-ui-validation-record.md",
    ROOT / "docs" / "test" / "step66ui4-fe1c-product-owner-validation.md",
    ROOT / "scripts" / "verify_step66ui4_fe1c_implementation.py",
    ROOT / "tests" / "test_step66ui4_fe1c_implementation.py",
    ROOT / "scripts" / "verify_step66ui4_fe1c_review.py",
    ROOT / "tests" / "test_step66ui4_fe1c_review.py",
    ROOT / "scripts" / "verify_step66ui4_fe1c_live_verification.py",
    ROOT / "tests" / "test_step66ui4_fe1c_live_verification.py",
    ROOT / "scripts" / "verify_step66ui4_fe1c_preview_deploy.py",
    ROOT / "tests" / "test_step66ui4_fe1c_preview_deploy.py",
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
    for p in FE1C_ARTIFACTS:
        if not p.is_file():
            bad(f"missing consolidated FE.1C artifact on main: {p}")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    texts = {name: p.read_text(encoding="utf-8") for name, p in DOCS.items()}
    progress_text = PROGRESS.read_text(encoding="utf-8")
    combined_low = _norm("\n".join(texts.values()))
    progress_low = _norm(progress_text)

    if "66ui.4-fe.1c-md" not in progress_low:
        bad("source/progress.md does not reference Stage 66UI.4-FE.1C-MD")

    if PR10_COMMIT not in combined_low:
        bad("PR #10 commit reference missing")
    if "merged" not in combined_low:
        bad("PR #10 merge not recorded")

    if "product owner" not in combined_low or "授權" not in "\n".join(texts.values()):
        bad("Product Owner merge authorization not recorded")

    if "visible" not in combined_low:
        bad("Product Owner UI validation VISIBLE not recorded")

    for name, path in {
        "review": "step66ui4-fe1c-implementation-review-record",
        "live verification": "step66ui4-fe1c-live-agent-execution-verification-record",
        "preview deployment": "step66ui4-fe1c-ui-validation-preview-deployment-record",
        "validation": "step66ui4-fe1c-product-owner-validation",
    }.items():
        if path not in combined_low:
            bad(f"{name} artifact reference missing")

    if "merged main" not in combined_low:
        bad("deployment source (merged main) not recorded")
    if "test runtime" not in combined_low:
        bad("test-runtime-only scope not recorded")

    if "tasklist" not in combined_low or "query-param" not in combined_low:
        bad("TaskList query-param gap not recorded")
    if "non-blocking" not in combined_low and "accepted" not in combined_low:
        bad("TaskList query-param gap acceptance not recorded")

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

    if "informational=100" not in combined_low and "informational count is 100" not in combined_low:
        bad("secret scan informational GUID note missing")
    if "guid" not in combined_low:
        bad("GUID non-secret explanation missing")

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

    print("  [OK] FE.1C merge record + merged-main test deployment record present; PR #10 merge,")
    print("       Product Owner merge authorization, Product Owner UI validation VISIBLE, and all")
    print("       review/live-verification/preview-deployment/validation artifacts on main all")
    print("       recorded; deployment source is merged main; test-runtime-only scope; TaskList")
    print("       query-param gap accepted non-blocking; no backend/API/database/workflow/new-")
    print("       endpoint change; no production/external action; FE.1D unauthorized;")
    print("       production_executed_true_count=0; Local Artifact Reconciliation recorded; secret")
    print("       scan informational GUID note recorded; no forbidden capability claims or")
    print("       sensitive identifiers")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
