#!/usr/bin/env python3
"""Step 66UI.2-FE.1-M -- Navigation Grouping / IA Shell merge verifier.

Confirms the merge record and test report exist and state the required
facts: Product Owner explicitly authorized the merge, the navigation
grouping artifacts are now present on main, the Delivery Package placement
conflict is closed, the Demo Evidence direct-route gap is recorded as
accepted/non-blocking, no backend/API/database/workflow change is claimed,
no production/external action is claimed, and post-merge verification
results are documented. Also confirms the frontend branch is now merged
into main (the expected post-merge state) and that the merged navigation
source reflects the FIX1 remediation.

This is a documentation + repo-state verifier: it reads files on the current
checkout and local git state; it does not touch any runtime or remote host.

Marker: STEP66UI2_FE1_MERGE_VERIFY: PASS | PASS_WITH_GAPS | FAIL
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FE_BRANCH_REF = "origin/frontend/66ui2-navigation-grouping"
NAV_TSX = ROOT / "apps" / "admin-console" / "src" / "components" / "Nav.tsx"

REVIEW_DOCS = {
    "merge-record": ROOT / "docs" / "frontend" / "66ui2-navigation-ia" / "merge-record.md",
    "fe1-merge-record": ROOT / "docs" / "test" / "step66ui2-fe1-merge-record.md",
}

MARKER = "STEP66UI2_FE1_MERGE_VERIFY"

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


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower())


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8"
    )


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
    for name, p in REVIEW_DOCS.items():
        if not p.is_file():
            bad(f"missing review doc: {p} ({name})")

    if not NAV_TSX.is_file():
        bad("Nav.tsx not found on main -- navigation grouping artifacts not merged")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    texts = {name: p.read_text(encoding="utf-8") for name, p in REVIEW_DOCS.items()}
    combined_low = _norm("\n".join(texts.values()))

    if "product owner explicitly authorized merge" not in combined_low:
        bad("Product Owner explicit merge authorization not recorded")

    if "frontend/66ui2-navigation-grouping" not in combined_low or "main" not in combined_low:
        bad("Merge source/target not recorded")

    if "delivery package" not in combined_low or "closed" not in combined_low:
        bad("Delivery Package placement conflict not recorded as closed")

    if "demo evidence" not in combined_low or "accepted" not in combined_low:
        bad("Demo Evidence direct-route gap not recorded as accepted/non-blocking")

    for name, text in texts.items():
        text_low = _norm(text)
        if "backend changed: no" not in text_low and "no backend changed" not in text_low:
            bad(f"{name} missing 'no backend changed' statement")
        if "api changed: no" not in text_low and "no api changed" not in text_low:
            bad(f"{name} missing 'no API changed' statement")
        if "database changed: no" not in text_low and "no database changed" not in text_low:
            bad(f"{name} missing 'no database changed' statement")
        if "workflow changed: no" not in text_low and "no workflow changed" not in text_low:
            bad(f"{name} missing 'no workflow changed' statement")
        if "no production action" not in text_low and "production action: no" not in text_low:
            bad(f"{name} missing 'no production action' statement")
        if "no external action" not in text_low and "external action: no" not in text_low:
            bad(f"{name} missing 'no external action' statement")

    if (
        "post-merge verification" not in combined_low
        and "post-merge verification results" not in combined_low
    ):
        bad("post-merge verification results not documented")

    # Navigation grouping artifacts now present on main, reflecting the FIX1 remediation.
    nav_source = NAV_TSX.read_text(encoding="utf-8")
    deliveries_section = re.search(
        r'id: "deliveries".*?id: "operator-center"', nav_source, re.DOTALL
    )
    if not deliveries_section or 'to: "/delivery-package"' in deliveries_section.group(0):
        bad("Merged Nav.tsx still places Delivery Package under Deliveries")
    platform_ops_section = re.search(r'id: "platform-ops".*?id: "settings"', nav_source, re.DOTALL)
    if not platform_ops_section or 'to: "/delivery-package"' not in platform_ops_section.group(0):
        bad("Merged Nav.tsx does not place Delivery Package under Platform Ops")

    # Frontend branch is now merged into main (expected post-merge state).
    merged = _git("merge-base", "--is-ancestor", FE_BRANCH_REF, "HEAD")
    if merged.returncode != 0:
        bad(f"{FE_BRANCH_REF} is not an ancestor of HEAD -- merge did not complete as expected")

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

    print("  [OK] merge record + test report present; Product Owner authorization recorded;")
    print("       navigation grouping artifacts present on main with Delivery Package correctly")
    print("       under Platform Ops; Delivery Package conflict closed; Demo Evidence gap accepted")
    print("       non-blocking; no backend/API/database/workflow change or production/external")
    print("       action claimed; frontend branch confirmed merged; no sensitive identifiers")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
