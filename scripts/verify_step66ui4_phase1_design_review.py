#!/usr/bin/env python3
"""Step 66UI.4-R -- Phase 1 Product Visual Language design review verifier.

Confirms the four required review docs exist and state: the Product Owner
Hybrid decision, Delivery Package remaining under Platform Ops, Codex still
unauthorized, no runtime/backend/API/database/workflow change claimed, no
production/external action claimed, and that any future frontend
implementation is scoped to frontend-only visual/product-language work.

This is a documentation-only verifier: it reads files on the current
checkout and does not touch any runtime, remote host, or git branch/remote.

Marker: STEP66UI4_PHASE1_DESIGN_REVIEW_VERIFY: PASS | PASS_WITH_GAPS | FAIL
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REVIEW_DOCS = {
    "architecture-review": ROOT
    / "docs"
    / "design"
    / "66ui4-phase1-product-visual-language"
    / "claude-code-architecture-review.md",
    "frontend-implementation-boundary": ROOT
    / "docs"
    / "contracts"
    / "66ui4-phase1-product-visual-language"
    / "frontend-implementation-boundary.md",
    "codex-readiness-boundary": ROOT
    / "docs"
    / "frontend"
    / "66ui4-phase1-product-visual-language"
    / "codex-readiness-boundary.md",
    "design-pr-source-of-truth-review": ROOT
    / "docs"
    / "design"
    / "66ui4-phase1-product-visual-language"
    / "design-pr-source-of-truth-review.md",
}

MARKER = "STEP66UI4_PHASE1_DESIGN_REVIEW_VERIFY"

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
    re.compile(r"production deployment performed", re.IGNORECASE),
    re.compile(r"staging deployment performed", re.IGNORECASE),
    re.compile(r"backend (?:has been|was) changed", re.IGNORECASE),
    re.compile(r"api (?:has been|was) changed", re.IGNORECASE),
    re.compile(r"database (?:has been|was) changed", re.IGNORECASE),
    re.compile(r"codex is authorized to implement", re.IGNORECASE),
    re.compile(r"pr (?:has been|was) merged", re.IGNORECASE),
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
    "unmerged",
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
    for name, p in REVIEW_DOCS.items():
        if not p.is_file():
            bad(f"missing review doc: {p} ({name})")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    texts = {name: p.read_text(encoding="utf-8") for name, p in REVIEW_DOCS.items()}
    combined_low = _norm("\n".join(texts.values()))

    # Product Owner Hybrid decision recorded.
    if "hybrid" not in combined_low:
        bad("Hybrid Product Owner decision not recorded")
    if "direction a" not in combined_low or "direction b" not in combined_low:
        bad("Direction A / Direction B framing not recorded")

    # Delivery Package placement.
    if "delivery package" not in combined_low or "platform ops" not in combined_low:
        bad("Delivery Package under Platform Ops not recorded")

    # Codex remains unauthorized.
    if "not authorized" not in combined_low and "not yet authorized" not in combined_low:
        bad("Codex not-yet-authorized statement missing")
    if "66d" not in combined_low:
        bad("Step 66D contract dependency not recorded")

    # No runtime/backend/API/database/workflow change claimed (checked per-doc for the three
    # docs whose subject matter is architecture/boundary/safety; the source-of-truth review is
    # scoped to PR merge state and is checked only via the combined-text checks below).
    for name, text in texts.items():
        if name == "design-pr-source-of-truth-review":
            continue
        text_low = _norm(text)
        if "no runtime code" not in text_low and "no runtime code changed" not in text_low:
            bad(f"{name} missing no-runtime-code statement")
        if "no backend" not in text_low and "backend impact: none" not in text_low:
            bad(f"{name} missing no-backend-change statement")
        if "workflow dispatch" not in text_low:
            bad(f"{name} missing workflow-dispatch statement")

    # No production/external action claimed.
    if "no production action" not in combined_low:
        bad("no-production-action statement missing")
    if "no external action" not in combined_low and "external action" not in combined_low:
        bad("no-external-action statement missing")

    # PR merge status.
    if "no pr merged" not in combined_low and "not merged" not in combined_low:
        bad("PR-not-merged statement missing")

    # Frontend-only scoping of future implementation.
    if "frontend-only" not in combined_low:
        bad("frontend-only implementation scoping statement missing")

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

    print("  [OK] all four Phase 1 design review docs present; Hybrid PO decision, Delivery")
    print(
        "       Package/Platform Ops, Codex-unauthorized, Step 66D dependency, no runtime/backend/"
    )
    print("       API/database/workflow/production/external claims, PR-not-merged status, and")
    print("       frontend-only implementation scoping all documented; no forbidden capability")
    print("       claims or sensitive identifiers found")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
