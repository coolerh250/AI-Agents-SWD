#!/usr/bin/env python3
"""Step 66UI.2-FE.1-R -- Navigation Grouping / IA Shell implementation review verifier.

Confirms the reviewed frontend branch (frontend/66ui2-navigation-grouping,
commits 8fd406a + 469b980) touches only the expected frontend/docs/verifier
scope, that its shared artifacts (implementation report, handoff, test
report, open-questions) exist on that branch, that this stage's 2 review
documents exist on the current checkout, that no sensitive identifiers or
forbidden capability claims appear anywhere in the reviewed content, and that
the known Delivery Package design-conformance gap is documented rather than
silently ignored.

This verifier reads the frontend branch via `git show <ref>:<path>` and
`git diff --name-only` -- it never checks out or merges that branch. If the
branch ref cannot be resolved locally, it attempts one read-only `git fetch`
(never a merge) before reporting a hard failure.

Marker: STEP66UI2_FE1_REVIEW_VERIFY: PASS | PASS_WITH_GAPS | FAIL
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FE_BRANCH_REF = "origin/frontend/66ui2-navigation-grouping"
FE_BRANCH_NAME = "frontend/66ui2-navigation-grouping"
EXPECTED_COMMITS = ("8fd406a", "469b980")

FE_SHARED_ARTIFACTS = (
    "docs/frontend/66ui2-navigation-ia/fe1-navigation-grouping-implementation-report.md",
    "docs/frontend/66ui2-navigation-ia/fe1-open-questions-and-gaps.md",
    "docs/handoffs/66ui2-navigation-ia/codex-to-claude-code-handoff.md",
    "docs/test/step66ui2-fe1-navigation-grouping-test-report.md",
)

REVIEW_DOCS = {
    "claude-code-fe1-review": ROOT
    / "docs"
    / "frontend"
    / "66ui2-navigation-ia"
    / "claude-code-fe1-review.md",
    "fe1-navigation-grouping-review": ROOT
    / "docs"
    / "test"
    / "step66ui2-fe1-navigation-grouping-review.md",
}

ALLOWED_PREFIXES = (
    "apps/admin-console/",
    "docs/frontend/66ui2-navigation-ia/",
    "docs/handoffs/66ui2-navigation-ia/",
    "docs/test/step66ui2-fe1-navigation-grouping-test-report.md",
    "scripts/verify_step66ui2_fe1_navigation_grouping.py",
    "tests/test_step66ui2_fe1_navigation_grouping.py",
    "source/progress.md",
)

MARKER = "STEP66UI2_FE1_REVIEW_VERIFY"

SECRET_SHAPES = re.compile(
    r"(-----BEGIN [A-Z ]*PRIVATE KEY|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
    r"AKIA[0-9A-Z]{16}|xoxb-[A-Za-z0-9-]{10,}|sk-ant-[A-Za-z0-9_-]{20,})"
)
INFRA_SHAPES = re.compile(r"(10\.0\.1\.31|aiagent-swd|itadmin)", re.IGNORECASE)

FORBIDDEN_CLAIM_PATTERNS = (
    re.compile(r"workflow dispatch is enabled", re.IGNORECASE),
    re.compile(r"workflow resume is enabled", re.IGNORECASE),
    re.compile(r"production action is enabled", re.IGNORECASE),
    re.compile(r"external action is enabled", re.IGNORECASE),
    re.compile(r"drag(ging)? (a card |is )?(now |currently )?allowed", re.IGNORECASE),
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
)
NEGATION_WINDOW = 160

failures: list[str] = []
gaps: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def gap(m: str) -> None:
    gaps.append(m)
    print(f"  [GAP] {m}")


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8"
    )


def _ensure_branch_available() -> bool:
    res = _git("cat-file", "-e", FE_BRANCH_REF)
    if res.returncode == 0:
        return True
    _git("fetch", "origin", FE_BRANCH_NAME)
    return _git("cat-file", "-e", FE_BRANCH_REF).returncode == 0


def _show(path: str) -> str | None:
    res = _git("show", f"{FE_BRANCH_REF}:{path}")
    return res.stdout if res.returncode == 0 else None


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
    if not _ensure_branch_available():
        bad(
            f"cannot resolve {FE_BRANCH_REF} locally -- run 'git fetch origin {FE_BRANCH_NAME}' first"
        )
        print(f"{MARKER}: FAIL")
        return 1

    for commit in EXPECTED_COMMITS:
        if _git("cat-file", "-e", commit).returncode != 0:
            bad(f"expected commit {commit} not found locally")

    # PR/branch must not be merged into main.
    merged = _git("merge-base", "--is-ancestor", FE_BRANCH_REF, "origin/main")
    if merged.returncode == 0:
        bad(f"{FE_BRANCH_REF} is already merged into origin/main -- review must precede merge")

    # Scope: diff must stay within the allowed prefixes.
    diff = _git("diff", "--name-only", f"origin/main...{FE_BRANCH_REF}")
    if diff.returncode != 0:
        bad("could not diff origin/main...FE_BRANCH_REF")
        changed: list[str] = []
    else:
        changed = [line for line in diff.stdout.splitlines() if line.strip()]
        out_of_scope = [f for f in changed if not any(f.startswith(p) for p in ALLOWED_PREFIXES)]
        if out_of_scope:
            bad(f"branch touches out-of-scope paths: {out_of_scope}")

    # Shared artifacts must exist on the branch.
    branch_texts: dict[str, str] = {}
    for path in FE_SHARED_ARTIFACTS:
        text = _show(path)
        if text is None:
            bad(f"shared artifact not found on {FE_BRANCH_REF}: {path}")
        else:
            branch_texts[path] = text

    # This stage's own review docs must exist on the current checkout.
    for name, p in REVIEW_DOCS.items():
        if not p.is_file():
            bad(f"missing review doc: {p} ({name})")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    review_texts = {name: p.read_text(encoding="utf-8") for name, p in REVIEW_DOCS.items()}
    all_texts = {**branch_texts, **review_texts}
    combined_low = re.sub(r"\s+", " ", "\n".join(all_texts.values()).lower())

    # Known Delivery Package design-conformance gap must be documented, not silently dropped.
    # This is a real, disclosed finding (not a defect in the review docs) -- its presence, once
    # confirmed documented, is exactly why this stage's honest marker is PASS_WITH_GAPS rather
    # than a silent PASS.
    if "delivery package" not in combined_low or "platform ops" not in combined_low:
        bad("Delivery Package / Platform Ops placement discrepancy not documented")
    else:
        gap(
            "Delivery Package placement conflicts with the reviewed page-grouping.md decision (documented; remediation required before merge)"
        )

    # Untracked-file caution must be addressed.
    if "platform-progress-admin-console-proposal" not in combined_low:
        gap(
            "untracked docs/product/platform-progress-admin-console-proposal.md not referenced in review docs"
        )

    # Sensitive identifiers / secrets.
    for name, text in all_texts.items():
        if SECRET_SHAPES.search(text):
            bad(f"{name} contains secret-shaped content")
        if INFRA_SHAPES.search(text):
            bad(f"{name} contains a real internal infrastructure identifier")

    # Forbidden capability claims (negation-aware).
    for name, text in all_texts.items():
        for hit in _unnegated_matches(name, text):
            bad(hit)

    # Review docs must state scope-control facts and PR/merge/authorization status.
    for name, text in review_texts.items():
        text_low = re.sub(r"\s+", " ", text.lower())
        if "backend changed" not in text_low:
            bad(f"{name} missing backend-changed scope statement")
        if "codex" not in text_low:
            bad(f"{name} missing Codex reference")
        if "not merged" not in text_low and "pr not merged" not in text_low:
            bad(f"{name} missing PR-not-merged statement")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    print("  [OK] branch scope confined to frontend/docs/verifier paths; shared artifacts present;")
    print("       2 review docs present; Delivery Package placement gap documented; no sensitive")
    print("       identifiers or forbidden capability claims found; branch not merged")
    if gaps:
        print(f"{MARKER}: PASS_WITH_GAPS")
        return 0
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
