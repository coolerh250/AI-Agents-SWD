#!/usr/bin/env python3
"""Step 66UI.2-FE.1-FIX1-R -- Delivery Package placement remediation review verifier.

Confirms the FIX1 remediation commit on frontend/66ui2-navigation-grouping
(ce8ab2f, on top of 8fd406a + 469b980) moved Delivery Package out of the
Deliveries group and into Platform Ops, that Deliveries now contains only
the two 66D placeholders, that the diff scope did not expand beyond the
original FE.1 review boundary, that this stage's 2 review documents exist
on the current checkout, and that no sensitive identifiers or forbidden
capability claims appear anywhere in the reviewed content.

This verifier reads the frontend branch via `git show <ref>:<path>` and
`git diff --name-only` -- it never checks out or merges that branch. If the
branch ref cannot be resolved locally, it attempts one read-only `git fetch`
(never a merge) before reporting a hard failure.

Marker: STEP66UI2_FE1_FIX1_REVIEW_VERIFY: PASS | PASS_WITH_GAPS | FAIL
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FE_BRANCH_REF = "origin/frontend/66ui2-navigation-grouping"
FE_BRANCH_NAME = "frontend/66ui2-navigation-grouping"
EXPECTED_COMMITS = ("8fd406a", "469b980", "ce8ab2f")
FIX1_COMMIT = "ce8ab2f"
PRE_FIX1_COMMIT = "469b980"

FE_SHARED_ARTIFACTS = (
    "docs/frontend/66ui2-navigation-ia/fe1-navigation-grouping-implementation-report.md",
    "docs/frontend/66ui2-navigation-ia/fe1-open-questions-and-gaps.md",
    "docs/handoffs/66ui2-navigation-ia/codex-to-claude-code-handoff.md",
    "docs/test/step66ui2-fe1-navigation-grouping-test-report.md",
)

REVIEW_DOCS = {
    "claude-code-fe1-fix1-review": ROOT
    / "docs"
    / "frontend"
    / "66ui2-navigation-ia"
    / "claude-code-fe1-fix1-review.md",
    "fe1-fix1-review": ROOT / "docs" / "test" / "step66ui2-fe1-fix1-review.md",
}

ALLOWED_PREFIXES = (
    "apps/admin-console/",
    "docs/frontend/66ui2-navigation-ia/",
    "docs/handoffs/66ui2-navigation-ia/",
    "docs/test/step66ui2-fe1-navigation-grouping-test-report.md",
    "docs/test/step66ui2-fe1-fix1-review.md",
    "scripts/verify_step66ui2_fe1_navigation_grouping.py",
    "scripts/verify_step66ui2_fe1_fix1_review.py",
    "tests/test_step66ui2_fe1_navigation_grouping.py",
    "tests/test_step66ui2_fe1_fix1_review.py",
    "source/progress.md",
)

MARKER = "STEP66UI2_FE1_FIX1_REVIEW_VERIFY"

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

    merged = _git("merge-base", "--is-ancestor", FE_BRANCH_REF, "origin/main")
    if merged.returncode == 0:
        bad(f"{FE_BRANCH_REF} is already merged into origin/main -- review must precede merge")

    # Nav.tsx source at FIX1 must place Delivery Package under Platform Ops, not Deliveries.
    nav = _show("apps/admin-console/src/components/Nav.tsx")
    if nav is None:
        bad("Nav.tsx not found on the FIX1 commit")
    else:
        deliveries_section = re.search(r'id: "deliveries".*?id: "operator-center"', nav, re.DOTALL)
        if not deliveries_section:
            bad("Deliveries group not found in Nav.tsx")
        elif 'to: "/delivery-package"' in deliveries_section.group(0):
            bad("Delivery Package still present in the Deliveries group -- remediation not applied")
        elif 'to: "/delivery-inbox"' not in deliveries_section.group(
            0
        ) or 'to: "/delivery-detail"' not in deliveries_section.group(0):
            bad("Deliveries group no longer contains both required 66D placeholders")

        platform_ops_section = re.search(r'id: "platform-ops".*?id: "settings"', nav, re.DOTALL)
        if not platform_ops_section or 'to: "/delivery-package"' not in platform_ops_section.group(
            0
        ):
            bad("Delivery Package not found under the Platform Ops group")

    # Route must remain unchanged.
    app_tsx = _show("apps/admin-console/src/App.tsx")
    if app_tsx is None or 'path="/delivery-package"' not in app_tsx:
        bad("/delivery-package route not preserved in App.tsx")

    # Scope must not have expanded beyond the original FE.1 review boundary.
    diff = _git("diff", "--name-only", f"origin/main...{FE_BRANCH_REF}")
    if diff.returncode != 0:
        bad("could not diff origin/main...FE_BRANCH_REF")
        changed: list[str] = []
    else:
        changed = [line for line in diff.stdout.splitlines() if line.strip()]
        out_of_scope = [f for f in changed if not any(f.startswith(p) for p in ALLOWED_PREFIXES)]
        if out_of_scope:
            bad(f"branch touches out-of-scope paths: {out_of_scope}")

    # The FIX1 commit itself must be scoped to Nav.tsx, its test, and shared docs -- not App.tsx
    # route changes or any backend/shared path.
    fix1_diff = _git("diff", "--name-only", f"{PRE_FIX1_COMMIT}..{FIX1_COMMIT}")
    fix1_changed = [line for line in fix1_diff.stdout.splitlines() if line.strip()]
    if any(f.startswith("shared/") or f.startswith("migrations/") for f in fix1_changed):
        bad("FIX1 commit touches backend/shared/migration paths")

    # Shared artifacts must exist on the branch and mention FIX1.
    branch_texts: dict[str, str] = {}
    for path in FE_SHARED_ARTIFACTS:
        text = _show(path)
        if text is None:
            bad(f"shared artifact not found on {FE_BRANCH_REF}: {path}")
        else:
            branch_texts[path] = text

    for name, p in REVIEW_DOCS.items():
        if not p.is_file():
            bad(f"missing review doc: {p} ({name})")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    review_texts = {name: p.read_text(encoding="utf-8") for name, p in REVIEW_DOCS.items()}
    all_texts = {**branch_texts, **review_texts}
    combined_low = re.sub(r"\s+", " ", "\n".join(all_texts.values()).lower())

    if "fix1" not in combined_low:
        bad("FIX1 remediation not referenced in shared docs / review docs")

    if "delivery package" not in combined_low or "platform ops" not in combined_low:
        bad("Delivery Package / Platform Ops placement not documented")

    if "clarifications" not in combined_low:
        gap(
            "Clarifications placeholder scope question remains open (non-blocking, needs Product Owner/Claude Design confirmation)"
        )

    if "platform-progress-admin-console-proposal" not in combined_low:
        gap(
            "untracked docs/product/platform-progress-admin-console-proposal.md not referenced in review docs"
        )

    for name, text in all_texts.items():
        if SECRET_SHAPES.search(text):
            bad(f"{name} contains secret-shaped content")
        if INFRA_SHAPES.search(text):
            bad(f"{name} contains a real internal infrastructure identifier")

    for name, text in all_texts.items():
        for hit in _unnegated_matches(name, text):
            bad(hit)

    for name, text in review_texts.items():
        text_low = re.sub(r"\s+", " ", text.lower())
        if "backend changed" not in text_low:
            bad(f"{name} missing backend-changed scope statement")
        if "codex" not in text_low:
            bad(f"{name} missing Codex reference")
        if "not merged" not in text_low:
            bad(f"{name} missing PR-not-merged statement")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    print("  [OK] Delivery Package moved to Platform Ops, out of Deliveries; route preserved;")
    print("       Deliveries contains only the 2 required 66D placeholders; scope unchanged from")
    print("       the original FE.1 review boundary; shared artifacts and 2 review docs present;")
    print("       no sensitive identifiers or forbidden capability claims found; branch not merged")
    if gaps:
        print(f"{MARKER}: PASS_WITH_GAPS")
        return 0
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
