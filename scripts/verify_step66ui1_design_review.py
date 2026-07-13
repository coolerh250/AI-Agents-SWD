#!/usr/bin/env python3
"""Step 66UI.1-R -- Claude Design Full UI/UX Redesign Options review verifier.

Confirms the reviewed design branch (design/66ui-full-redesign-options,
commits bc6c5b3 + 00d1191) contains the 10 expected design files and the
required Hybrid/Category-H/Delivery/Pipeline decisions, that this stage's 3
review documents exist on the current checkout, that the design branch
touches no runtime/backend/frontend-implementation path, and that no
sensitive identifiers or forbidden capability claims appear anywhere in the
reviewed content.

This verifier reads the design branch via `git show <ref>:<path>` -- it never
checks out or merges that branch. If the branch ref cannot be resolved
locally, it attempts one read-only `git fetch` (never a merge) before
reporting a hard failure.

Marker: STEP66UI1_DESIGN_REVIEW_VERIFY: PASS | PASS_WITH_GAPS | FAIL
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESIGN_BRANCH_REF = "origin/design/66ui-full-redesign-options"
DESIGN_BRANCH_NAME = "design/66ui-full-redesign-options"
DESIGN_DOC_DIR = "docs/design/66ui-full-redesign-options"
EXPECTED_COMMITS = ("bc6c5b3", "00d1191")

DESIGN_FILES = (
    "design-objective.md",
    "feature-categorization.md",
    "layout-comparison.md",
    "layout-option-1-operations-command-center.md",
    "layout-option-2-task-workspace.md",
    "layout-option-3-lifecycle-pipeline.md",
    "product-owner-decision-summary.md",
    "product-owner-discussion-guide.md",
    "recommendation.md",
    "user-role-journey-map.md",
)

REVIEW_DOCS = {
    "architecture-review": ROOT / DESIGN_DOC_DIR / "claude-code-architecture-review.md",
    "frontend-implementation-boundary": ROOT
    / "docs"
    / "contracts"
    / "66ui-full-redesign-options"
    / "frontend-implementation-boundary.md",
    "codex-readiness-boundary": ROOT
    / "docs"
    / "frontend"
    / "66ui-full-redesign-options"
    / "codex-readiness-boundary.md",
}

MARKER = "STEP66UI1_DESIGN_REVIEW_VERIFY"

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

failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8"
    )


def _ensure_branch_available() -> bool:
    res = _git("cat-file", "-e", f"{DESIGN_BRANCH_REF}")
    if res.returncode == 0:
        return True
    _git("fetch", "origin", DESIGN_BRANCH_NAME)
    return _git("cat-file", "-e", f"{DESIGN_BRANCH_REF}").returncode == 0


def _show(path: str) -> str | None:
    res = _git("show", f"{DESIGN_BRANCH_REF}:{DESIGN_DOC_DIR}/{path}")
    return res.stdout if res.returncode == 0 else None


def main() -> int:
    if not _ensure_branch_available():
        bad(
            f"cannot resolve {DESIGN_BRANCH_REF} locally -- run "
            f"'git fetch origin {DESIGN_BRANCH_NAME}' first"
        )
        print(f"{MARKER}: FAIL")
        return 1

    for commit in EXPECTED_COMMITS:
        if _git("cat-file", "-e", commit).returncode != 0:
            bad(f"expected commit {commit} not found locally")

    design_texts: dict[str, str] = {}
    for name in DESIGN_FILES:
        text = _show(name)
        if text is None:
            bad(f"design file not found on {DESIGN_BRANCH_REF}: {name}")
        else:
            design_texts[name] = text

    for name, p in REVIEW_DOCS.items():
        if not p.is_file():
            bad(f"missing review doc: {p} ({name})")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    review_texts = {name: p.read_text(encoding="utf-8") for name, p in REVIEW_DOCS.items()}
    all_texts = {**design_texts, **review_texts}
    combined_low = re.sub(r"\s+", " ", "\n".join(all_texts.values()).lower())

    # Decision content.
    if "hybrid" not in combined_low:
        bad("Hybrid decision not recorded")
    if "category h" not in combined_low or "platform ops" not in combined_low:
        bad("Category H / Platform Ops inclusion not documented")
    if "grouping only" not in combined_low:
        bad("Category H round-1 'grouping only' scope not documented")
    if "66d" not in combined_low or "not merged" not in combined_low:
        bad("DeliveryPackage/Delivery Inbox deferral to 66D not documented")
    if "read-only" not in combined_low or "drag" not in combined_low:
        bad("Lifecycle Pipeline read-only/deferred decision not documented")

    # No runtime/backend/frontend-implementation change on the design branch.
    diff = _git(
        "diff",
        "--name-only",
        f"{EXPECTED_COMMITS[0]}~1",
        EXPECTED_COMMITS[1],
    )
    if diff.returncode != 0:
        bad("could not diff the design branch commit range")
    else:
        changed = [line for line in diff.stdout.splitlines() if line.strip()]
        non_doc = [f for f in changed if not f.startswith(f"{DESIGN_DOC_DIR}/")]
        if non_doc:
            bad(f"design branch touches non-design-doc paths: {non_doc}")

    # Sensitive identifiers / secrets.
    for name, text in all_texts.items():
        if SECRET_SHAPES.search(text):
            bad(f"{name} contains secret-shaped content")
        if INFRA_SHAPES.search(text):
            bad(f"{name} contains a real internal infrastructure identifier")

    # Forbidden capability claims.
    for name, text in all_texts.items():
        for pattern in FORBIDDEN_CLAIM_PATTERNS:
            if pattern.search(text):
                bad(f"{name} contains a forbidden capability claim: {pattern.pattern}")

    # No production action / no Codex authorization statements in the review docs.
    for name, text in review_texts.items():
        text_low = re.sub(r"\s+", " ", text.lower())
        if "no runtime code changed" not in text_low:
            bad(f"{name} missing 'no runtime code changed' statement")
        if "codex" not in text_low:
            bad(f"{name} missing Codex authorization boundary statement")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    print("  [OK] 10 design files present on the reviewed branch; 3 review docs present on this")
    print("       checkout; Hybrid/Category-H/Delivery-66D/Pipeline-read-only decisions")
    print("       documented; design branch touches no runtime/backend/frontend-implementation")
    print("       path; no sensitive identifiers or forbidden capability claims found")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
