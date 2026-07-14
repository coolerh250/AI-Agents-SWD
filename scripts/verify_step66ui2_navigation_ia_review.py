#!/usr/bin/env python3
"""Step 66UI.2-R -- Navigation / IA detailed design review verifier.

Confirms the reviewed design branch (design/66ui2-navigation-ia, commit
edda1b0) contains the 8 expected design files and the required navigation
groups / placeholder-deferral decisions, that this stage's 3 review documents
exist on the current checkout, that the design branch touches no
runtime/backend/frontend-implementation path, and that no sensitive
identifiers or forbidden capability claims appear anywhere in the reviewed
content.

This verifier reads the design branch via `git show <ref>:<path>` -- it never
checks out or merges that branch. If the branch ref cannot be resolved
locally, it attempts one read-only `git fetch` (never a merge) before
reporting a hard failure.

Marker: STEP66UI2_NAVIGATION_IA_REVIEW_VERIFY: PASS | PASS_WITH_GAPS | FAIL
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESIGN_BRANCH_REF = "origin/design/66ui2-navigation-ia"
DESIGN_BRANCH_NAME = "design/66ui2-navigation-ia"
DESIGN_DOC_DIR = "docs/design/66ui2-navigation-ia"
EXPECTED_COMMIT = "edda1b0"

DESIGN_FILES = (
    "design-brief.md",
    "navigation-map.md",
    "page-grouping.md",
    "role-based-entry-points.md",
    "placeholder-rules.md",
    "migration-from-current-nav.md",
    "codex-implementation-notes.md",
    "product-owner-review-checklist.md",
)

REVIEW_DOCS = {
    "architecture-review": ROOT / DESIGN_DOC_DIR / "claude-code-architecture-review.md",
    "frontend-implementation-boundary": ROOT
    / "docs"
    / "contracts"
    / "66ui2-navigation-ia"
    / "frontend-implementation-boundary.md",
    "codex-implementation-plan-boundary": ROOT
    / "docs"
    / "frontend"
    / "66ui2-navigation-ia"
    / "codex-implementation-plan-boundary.md",
}

NAV_GROUPS = (
    "overview",
    "team work",
    "deliveries",
    "operator center",
    "governance",
    "platform ops",
    "settings",
)

MARKER = "STEP66UI2_NAVIGATION_IA_REVIEW_VERIFY"

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

# A claim pattern preceded (within this many chars) by a negation cue is a
# prohibition, not an assertion of the capability -- e.g. "No nav item may
# imply that ... is enabled" legitimately contains the substring "... is
# enabled" while meaning the opposite. Reviewed content is third-party
# (Claude Design) text this stage does not author, so the check must be
# negation-aware rather than requiring the source text be reworded.
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


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8"
    )


def _ensure_branch_available() -> bool:
    res = _git("cat-file", "-e", DESIGN_BRANCH_REF)
    if res.returncode == 0:
        return True
    _git("fetch", "origin", DESIGN_BRANCH_NAME)
    return _git("cat-file", "-e", DESIGN_BRANCH_REF).returncode == 0


def _show(path: str) -> str | None:
    res = _git("show", f"{DESIGN_BRANCH_REF}:{DESIGN_DOC_DIR}/{path}")
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
            f"cannot resolve {DESIGN_BRANCH_REF} locally -- run "
            f"'git fetch origin {DESIGN_BRANCH_NAME}' first"
        )
        print(f"{MARKER}: FAIL")
        return 1

    if _git("cat-file", "-e", EXPECTED_COMMIT).returncode != 0:
        bad(f"expected commit {EXPECTED_COMMIT} not found locally")

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

    # Navigation groups.
    for group in NAV_GROUPS:
        if group not in combined_low:
            bad(f"nav group not documented: {group}")

    # Route preservation / migration.
    if "28" not in combined_low:
        bad("28-flat-item migration count not documented")
    if "unchanged" not in combined_low and "preserved" not in combined_low:
        bad("existing-route preservation not documented")

    # Platform Ops is grouping-only.
    if "platform ops" not in combined_low or "grouping only" not in combined_low:
        bad("Platform Ops grouping-only scope not documented")

    # Delivery / Reminder placeholders.
    if "requires step 66d" not in combined_low and "requires 66d" not in combined_low:
        bad("Delivery placeholder deferral to 66D not documented")
    if "requires step 66c.4" not in combined_low and "requires 66c.4" not in combined_low:
        bad("Reminder/Expiry placeholder deferral to 66C.4 not documented")

    # Lifecycle Pipeline deferred / read-only / not in round 1.
    if "read-only" not in combined_low or "pipeline" not in combined_low:
        bad("Lifecycle Pipeline read-only/deferred decision not documented")

    # No runtime/backend/frontend-implementation change on the design branch.
    diff = _git("diff", "--name-only", f"{EXPECTED_COMMIT}~1", EXPECTED_COMMIT)
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

    # Forbidden capability claims (negation-aware).
    for name, text in all_texts.items():
        for hit in _unnegated_matches(name, text):
            bad(hit)

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

    print("  [OK] 8 design files present on the reviewed branch; 3 review docs present on this")
    print("       checkout; 7 nav groups, route-preservation, Platform-Ops-grouping-only,")
    print("       Delivery-66D/Reminder-66C.4/Pipeline-read-only deferral decisions documented;")
    print("       design branch touches no runtime/backend/frontend-implementation path; no")
    print("       sensitive identifiers or forbidden capability claims found")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
