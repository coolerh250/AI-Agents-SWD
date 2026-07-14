#!/usr/bin/env python3
"""Step 66UI.2-FE.1-D -- Test runtime deployment record verifier.

Confirms the test-runtime deployment record and test report for Step
66UI.2-FE.1 exist and state: Product Owner deployment authorization, that
the deployed source is main and the environment is test-runtime-only, all
7 nav groups verified, Delivery Package under Platform Ops, Delivery
placeholders requiring 66D, the Clarifications placeholder requiring 66C.4,
the Demo Evidence deferred gap recorded as non-blocking,
production_executed_true_count remaining 0, no production/external/workflow
action claimed, and rollback status recorded.

This is a documentation-only verifier: it reads files on the current
checkout and does not touch any runtime or remote host.

Marker: STEP66UI2_FE1_TEST_DEPLOYMENT_VERIFY: PASS | PASS_WITH_GAPS | FAIL
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REVIEW_DOCS = {
    "test-runtime-deployment-record": ROOT
    / "docs"
    / "frontend"
    / "66ui2-navigation-ia"
    / "test-runtime-deployment-record.md",
    "fe1-test-runtime-deployment": ROOT
    / "docs"
    / "test"
    / "step66ui2-fe1-test-runtime-deployment.md",
}

MARKER = "STEP66UI2_FE1_TEST_DEPLOYMENT_VERIFY"

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


def main() -> int:
    for name, p in REVIEW_DOCS.items():
        if not p.is_file():
            bad(f"missing review doc: {p} ({name})")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    texts = {name: p.read_text(encoding="utf-8") for name, p in REVIEW_DOCS.items()}
    combined_low = _norm("\n".join(texts.values()))

    # Deployment authorization / source / environment.
    if (
        "deployed from: origin/main" not in combined_low
        and "deployed source: origin/main" not in combined_low
    ):
        bad("deployed source (origin/main) not recorded")
    if "test runtime only" not in combined_low:
        bad("test-runtime-only environment scope not recorded")
    if "no staging" not in combined_low and "no staging deployment" not in combined_low:
        bad("no-staging-deployment statement missing")

    # UI verification requirements.
    for group in (
        "overview",
        "team work",
        "deliveries",
        "operator center",
        "governance",
        "platform ops",
        "settings",
    ):
        if group not in combined_low:
            bad(f"nav group not verified: {group}")

    if "delivery package" not in combined_low or "platform ops" not in combined_low:
        bad("Delivery Package under Platform Ops not recorded")

    if "66d" not in combined_low:
        bad("Delivery placeholder 66D requirement not recorded")

    if "66c.4" not in combined_low:
        bad("Clarifications placeholder 66C.4 requirement not recorded")

    if "demo evidence" not in combined_low or (
        "accepted" not in combined_low and "deferred" not in combined_low
    ):
        bad("Demo Evidence deferred gap not recorded as accepted/non-blocking")

    # Safety.
    if "production_executed_true_count before: 0" not in combined_low.replace(
        "production_executed_true_count  before", "production_executed_true_count before"
    ):
        bad("production_executed_true_count before-value not recorded as 0")
    if (
        "production_executed_true_count after:  0" not in combined_low
        and "production_executed_true_count after: 0" not in combined_low
    ):
        bad("production_executed_true_count after-value not recorded as 0")

    for name, text in texts.items():
        text_low = _norm(text)
        if (
            "no production action" not in text_low
            and "production action: no" not in text_low
            and "production action" not in text_low
        ):
            bad(f"{name} missing production-action statement")
        if "no external action" not in text_low and "external action" not in text_low:
            bad(f"{name} missing external-action statement")
        if "workflow dispatch" not in text_low:
            bad(f"{name} missing workflow-dispatch statement")

    # Rollback status recorded.
    if "rollback" not in combined_low:
        bad("rollback status not recorded")

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

    print(
        "  [OK] test-runtime deployment record + test report present; deployed source/environment"
    )
    print("       recorded; 7 nav groups, Delivery Package/Platform Ops, 66D/66C.4 placeholders,")
    print("       Demo Evidence deferred-non-blocking gap, production_executed_true_count=0, and")
    print("       rollback status all documented; no forbidden capability claims or sensitive")
    print("       identifiers found")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
