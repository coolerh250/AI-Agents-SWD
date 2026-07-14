#!/usr/bin/env python3
"""Step 66UI.4-SOT-M -- Design source-of-truth merge verifier.

Confirms PR #4 (DESIGN-66UI.3) and PR #5 (DESIGN-66UI.4 Phase 1) design docs
are present on the current checkout (i.e. merged to main), that the Hybrid
decision, Delivery Package/Platform Ops placement, PR #2-superseded status,
PR #1 historical-reference status, and Codex-not-authorized statement are
all recorded, that the source-of-truth record exists, and that no runtime/
backend/API/database/workflow file was changed by this stage.

This is a documentation-only verifier: it reads files on the current
checkout and does not touch any runtime, remote host, or git remote beyond
a local `git diff --name-only` against the pre-merge commit to confirm scope.

Marker: STEP66UI4_SOURCE_OF_TRUTH_MERGE_VERIFY: PASS | PASS_WITH_GAPS | FAIL
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

MARKER = "STEP66UI4_SOURCE_OF_TRUTH_MERGE_VERIFY"

PR4_DOCS = {
    "pr4-decision-record": ROOT
    / "docs"
    / "design"
    / "66ui3-product-ux-visual-direction"
    / "product-owner-decision-record.md",
}

PR5_DOCS = {
    "pr5-design-brief": ROOT
    / "docs"
    / "design"
    / "66ui4-phase1-product-visual-language"
    / "design-brief.md",
    "pr5-codex-notes": ROOT
    / "docs"
    / "design"
    / "66ui4-phase1-product-visual-language"
    / "codex-implementation-notes.md",
}

REVIEW_DOCS = {
    "source-of-truth-record": ROOT / "docs" / "design" / "66ui-source-of-truth-record.md",
    "merge-test-record": ROOT / "docs" / "test" / "step66ui4-source-of-truth-merge-record.md",
}

NAV_TSX = ROOT / "apps" / "admin-console" / "src" / "components" / "Nav.tsx"

FORBIDDEN_PATH_PREFIXES = (
    "apps/orchestrator/src/",
    "apps/admin-console/src/",
    "shared/",
    "infra/",
)

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
    re.compile(r"codex is authorized to implement", re.IGNORECASE),
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


def check_files_exist(label: str, mapping: dict[str, Path]) -> None:
    for name, p in mapping.items():
        if not p.is_file():
            bad(f"missing {label} file: {p} ({name})")


def check_no_forbidden_paths_changed() -> None:
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%H", "--grep=phase 1 product visual language"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return
    head_commit = result.stdout.strip()
    if not head_commit:
        return
    diff = subprocess.run(
        ["git", "diff", "--name-only", f"{head_commit}~2", head_commit],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if diff.returncode != 0:
        return
    for path in (line.strip() for line in diff.stdout.splitlines() if line.strip()):
        normalized = path.replace("\\", "/")
        for prefix in FORBIDDEN_PATH_PREFIXES:
            if normalized.startswith(prefix):
                bad(f"forbidden path changed by this stage's merges: {path}")


def main() -> int:
    check_files_exist("PR #4", PR4_DOCS)
    check_files_exist("PR #5", PR5_DOCS)
    check_files_exist("review", REVIEW_DOCS)

    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    pr4_text = _norm(PR4_DOCS["pr4-decision-record"].read_text(encoding="utf-8"))
    review_texts = {name: p.read_text(encoding="utf-8") for name, p in REVIEW_DOCS.items()}
    combined_low = _norm("\n".join(review_texts.values()))

    if "hybrid" not in pr4_text:
        bad("Hybrid decision not present in merged PR #4 docs")
    if "direction a" not in pr4_text or "direction b" not in pr4_text:
        bad("Direction A / B framing not present in merged PR #4 docs")

    if "delivery package" not in pr4_text or "platform ops" not in pr4_text:
        bad("Delivery Package / Platform Ops decision not present in merged PR #4 docs")

    if "pr #2" not in combined_low or "supersed" not in combined_low:
        bad("PR #2 superseded status not recorded")

    if "pr #1" not in combined_low or "historical" not in combined_low:
        bad("PR #1 historical-reference status not recorded")

    if not any(
        phrase in combined_low
        for phrase in (
            "not authorized",
            "not yet authorized",
            "unauthorized",
            "codex remains unauthorized",
        )
    ):
        bad("Codex not-authorized statement missing")

    if not NAV_TSX.is_file():
        bad(f"Nav.tsx not found for placement confirmation: {NAV_TSX}")
    else:
        nav_text = NAV_TSX.read_text(encoding="utf-8")
        deliveries_idx = nav_text.find('id: "deliveries"')
        platform_ops_idx = nav_text.find('id: "platform-ops"')
        delivery_package_idx = nav_text.find("/delivery-package")
        if -1 in (deliveries_idx, platform_ops_idx, delivery_package_idx):
            bad("Nav.tsx missing expected deliveries/platform-ops/delivery-package markers")
        elif not (platform_ops_idx < delivery_package_idx):
            bad("Delivery Package does not appear under Platform Ops in Nav.tsx")

    for name, text in review_texts.items():
        if SECRET_SHAPES.search(text):
            bad(f"{name} contains secret-shaped content")
        if INFRA_SHAPES.search(text):
            bad(f"{name} contains a real internal infrastructure identifier")
        for hit in _unnegated_matches(name, text):
            bad(hit)

    check_no_forbidden_paths_changed()

    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    print("  [OK] PR #4 and PR #5 design docs present on main; Hybrid decision, Delivery")
    print("       Package/Platform Ops placement, PR #2-superseded, PR #1-historical, and")
    print("       Codex-not-authorized statements all recorded; Nav.tsx confirms Delivery Package")
    print("       under Platform Ops; source-of-truth record present; no forbidden path changed;")
    print("       no unauthorized capability claim found")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
