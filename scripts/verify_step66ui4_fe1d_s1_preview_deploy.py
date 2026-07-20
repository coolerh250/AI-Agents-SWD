#!/usr/bin/env python3
"""Step 66UI.4-FE.1D-S1-VP -- PR #13 test runtime UI validation preview deployment verifier.

Confirms the preview deployment record and UI validation preview record exist and state: PR #13
branch/commit deployed, main not merged, test-runtime-only scope, Product Owner validation pending,
7 nav groups and subtitles, Soon/Read-only/Evidence badges, Platform Ops compact density, Delivery
Package under Platform Ops, route preservation, no fake controls, Slice 2 not implemented,
"+ Create task" unchanged, delivery_package_ready_for_admin_console deferred, SPA deep-link
fallback and two-way URL sync excluded, no backend/API/database/workflow/new-endpoint/new-route
change, no production/external action, FE.1D Slice 2 remaining unauthorized, Local Artifact
Reconciliation, and no Windows/local path exposure.

This is a documentation-only verifier: it reads files on the current checkout and does not touch
any runtime or remote host.

Marker: STEP66UI4_FE1D_S1_PREVIEW_DEPLOY_VERIFY: PASS | PASS_WITH_GAPS | FAIL
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DOCS = {
    "fe1d-s1-preview-deploy-record": ROOT
    / "docs"
    / "test"
    / "step66ui4-fe1d-s1-ui-validation-preview-deployment-record.md",
    "fe1d-s1-ui-validation-preview-record": ROOT
    / "docs"
    / "frontend"
    / "66ui4-fe1d-navigation-microcopy"
    / "slice1-navigation-polish-ui-validation-preview-record.md",
}

PROGRESS = ROOT / "source" / "progress.md"

MARKER = "STEP66UI4_FE1D_S1_PREVIEW_DEPLOY_VERIFY"
PR13_COMMIT = "72d8bff"
PR13_BRANCH = "frontend/66ui4-fe1d-s1-navigation-polish"

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
    re.compile(r"new route (?:was|is) added", re.IGNORECASE),
    re.compile(r"production action (?:was|is) triggered", re.IGNORECASE),
    re.compile(r"external action (?:was|is) triggered", re.IGNORECASE),
    re.compile(r"pr #13 (?:has been|was) merged", re.IGNORECASE),
    re.compile(r"main (?:has been|was) merged", re.IGNORECASE),
    re.compile(r"fe\.1d slice 2 is authorized", re.IGNORECASE),
    re.compile(r"spa deep-link fallback (?:was|is) fixed", re.IGNORECASE),
    re.compile(r"two-way url sync (?:was|is) implemented", re.IGNORECASE),
    re.compile(r"delivery package (?:was|is) moved to deliveries", re.IGNORECASE),
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
    "remains under platform ops",
    "pending",
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

    if "66ui.4-fe.1d-s1-vp" not in progress_low:
        bad("source/progress.md does not reference Stage 66UI.4-FE.1D-S1-VP")

    if PR13_BRANCH not in combined_low:
        bad("PR #13 branch reference missing")
    if PR13_COMMIT not in combined_low:
        bad("PR #13 commit reference missing")

    if not re.search(r"main[^.]*not[^.]*merged|main was not merged|main not merged", combined_low):
        bad("main-not-merged statement missing")
    if "test runtime only" not in combined_low and "test-runtime only" not in combined_low:
        bad("test-runtime-only scope statement missing")

    if "product owner validation" not in combined_low or "pending" not in combined_low:
        bad("Product Owner validation pending statement missing")

    if "group subtitle" not in combined_low:
        bad("group subtitles not recorded")
    if not re.search(r"7 (navigation|nav) groups", combined_low):
        bad("7 nav groups not recorded")

    for badge in ("soon", "read-only", "evidence"):
        if badge not in combined_low:
            bad(f"{badge} badge not recorded")

    if "compact density" not in combined_low and "platform ops" not in combined_low:
        bad("Platform Ops compact density not recorded")
    if "delivery package" not in combined_low or "platform ops" not in combined_low:
        bad("Delivery Package under Platform Ops not recorded")

    if "route" not in combined_low or "preserved" not in combined_low:
        bad("route preservation not recorded")
    if "fake control" not in combined_low:
        bad("no-fake-controls statement missing")
    if "slice 2" not in combined_low:
        bad("Slice 2 not-implemented statement missing")

    if '"+ create task"' not in combined_low and "create task" not in combined_low:
        bad('"+ Create task" unchanged not recorded')
    if "delivery_package_ready_for_admin_console" not in combined_low:
        bad("delivery_package_ready_for_admin_console reference missing")

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
    if not re.search(r"no [\w/]*new route", combined_low) and "new route" not in combined_low:
        bad("no-new-route statement missing")

    if not re.search(r"no [\w/]*production[/\s]*external action", combined_low) and (
        not re.search(r"no [\w/]*production action", combined_low)
        or not re.search(r"no [\w/]*external action", combined_low)
    ):
        bad("no-production/external-action statement missing")

    if "slice 2" not in combined_low or "remains unauthorized" not in combined_low:
        bad("FE.1D Slice 2 unauthorized statement missing")

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

    print("  [OK] FE.1D-S1 preview deployment record + UI validation preview record present; PR")
    print("       #13 branch/commit, main-not-merged, test-runtime-only scope, Product Owner")
    print("       validation pending, 7 nav groups/subtitles, Soon/Read-only/Evidence badges,")
    print("       Platform Ops density, Delivery Package placement, route preservation, no fake")
    print("       controls, Slice 2 exclusion, Product Owner decisions preserved, and SPA deep-")
    print("       link/two-way-sync exclusion all recorded; no backend/API/database/workflow/new-")
    print("       endpoint/new-route change; no production/external action; FE.1D Slice 2 remains")
    print("       unauthorized; Local Artifact Reconciliation recorded; no forbidden capability")
    print("       claims or sensitive identifiers")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
