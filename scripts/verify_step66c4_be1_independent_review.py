#!/usr/bin/env python3
"""Step 66C.4-BE1-R -- independent review completeness verifier.

Confirms the independent technical/security/migration review of Step 66C.4-BE1 produced every
required artifact, recorded the two markers SEPARATELY (review process vs. technical verdict), and
that the review itself changed NO implementation path.

This verifier scores the REVIEW PROCESS, not the reviewed implementation. A PASS here means the
review is complete and correctly scoped; it says nothing about whether BE1 passed.

Static/structural + git-diff checks only; it touches no runtime, no database and no remote host.

Marker: STEP66C4_BE1_INDEPENDENT_REVIEW_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_DIR = ROOT / "docs" / "contracts" / "66c4-reminder-expiry-controlled-resume"
STAGE_DIR = ROOT / "docs" / "stages" / "66c4-be1-independent-review"

REVIEW_DOCS = {
    "master": CONTRACT_DIR / "be1-independent-review.md",
    "deadline": CONTRACT_DIR / "be1-deadline-semantics-review.md",
    "outbox": CONTRACT_DIR / "be1-outbox-foundation-sufficiency-review.md",
    "security": CONTRACT_DIR / "be1-security-review.md",
    "migration": CONTRACT_DIR / "be1-migration-review.md",
    "tests": CONTRACT_DIR / "be1-test-quality-review.md",
    "handoff": ROOT
    / "docs"
    / "handoffs"
    / "66c4-reminder-expiry-controlled-resume"
    / "be1-review-result-handoff.md",
    "record": ROOT / "docs" / "test" / "step66c4-be1-independent-review-record.md",
    "manifest": STAGE_DIR / "stage-manifest.yaml",
    "receipt": STAGE_DIR / "context-receipt.md",
    "gate": STAGE_DIR / "stage-gate-report.md",
}

PROCESS_MARKER = "STEP66C4_BE1_INDEPENDENT_REVIEW_VERIFY"
TECHNICAL_MARKER = "BE1_TECHNICAL_VERDICT"
VALID_TECHNICAL_VERDICTS = ("PASS", "REMEDIATION_REQUIRED")

REVIEWED_BRANCH = "origin/feature/66c4-be1-lifecycle-outbox-foundation"

# The review may never modify any of these.
FORBIDDEN_CHANGED_PREFIXES = (
    "migrations/",
    "shared/sdk/",
    "apps/",
    "services/",
    "infra/",
    "helm/",
    "k8s/",
    "frontend/",
    ".github/workflows/",
)

# Identifiers that must never appear in a committed file (standing masking rule).
MASKED_PATTERNS = ("10.0.1.31", "10.0.1.32", "aiagent-swd", "itadmin", "stpadmin")

failures: list[str] = []


def bad(message: str) -> None:
    failures.append(message)
    print(f"  [FAIL] {message}")


def _changed_vs_reviewed_branch() -> list[str]:
    out = subprocess.run(
        ["git", "diff", "--name-only", f"{REVIEWED_BRANCH}...HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    return [line.strip() for line in out.stdout.splitlines() if line.strip()]


def main() -> int:
    # 1. Every required review artifact exists and is non-trivial.
    for name, path in REVIEW_DOCS.items():
        if not path.is_file():
            bad(f"check1: missing review artifact: {path} ({name})")
        elif len(path.read_text(encoding="utf-8").strip()) < 400:
            bad(f"check1: review artifact is too short to be substantive: {path} ({name})")
    if failures:
        print(f"{PROCESS_MARKER}: FAIL")
        return 1

    texts = {name: path.read_text(encoding="utf-8") for name, path in REVIEW_DOCS.items()}

    # 2. The review-process marker is present in the master review and the test record.
    for name in ("master", "record"):
        if PROCESS_MARKER not in texts[name]:
            bad(f"check2: review-process marker missing from {REVIEW_DOCS[name].name}")

    # 3. The technical verdict is recorded SEPARATELY and is one of the two allowed values.
    if TECHNICAL_MARKER not in texts["master"]:
        bad("check3: technical verdict marker missing from the master review")
    if not any(f"{TECHNICAL_MARKER}: {v}" in texts["master"] for v in VALID_TECHNICAL_VERDICTS):
        bad(f"check3: technical verdict is not one of {VALID_TECHNICAL_VERDICTS}")

    # 4. The two markers are never conflated into one statement.
    for name, text in texts.items():
        for line in text.splitlines():
            if PROCESS_MARKER in line and TECHNICAL_MARKER in line:
                bad(f"check4: process and technical markers conflated on one line in {name}")

    # 5. The handoff carries the same technical verdict as the master review.
    verdict = next(
        (v for v in VALID_TECHNICAL_VERDICTS if f"{TECHNICAL_MARKER}: {v}" in texts["master"]),
        None,
    )
    if verdict and f"{TECHNICAL_MARKER}: {verdict}" not in texts["handoff"]:
        bad("check5: the handoff does not carry the master review's technical verdict")

    # 6. Each mandatory reproduction is evidenced in the record.
    for topic in (
        "5.1 Transaction-crossing-deadline",
        "5.2 `due_at IS NULL`",
        "5.3 Migration up / down / reapply",
        "5.4 Concurrent answer CAS",
        "5.5 Outbox durability capability matrix",
        "5.6 No-live-producer verification",
        "5.7 Security probes",
    ):
        if topic not in texts["record"]:
            bad(f"check6: reproduction evidence missing from the record: {topic}")

    # 7. Every outbox capability classification vocabulary term is used in the sufficiency review.
    for term in (
        "SUPPORTED_BY_CURRENT_SCHEMA",
        "SUPPORTED_WITHOUT_SCHEMA_CHANGE",
        "REQUIRES_SCHEMA_CHANGE",
        "UNRESOLVED",
    ):
        if term not in texts["outbox"]:
            bad(f"check7: outbox capability classification term unused: {term}")
    if not any(
        v in texts["outbox"]
        for v in (
            "FOUNDATION_SUFFICIENT_FOR_BE2",
            "FOUNDATION_REMEDIATION_REQUIRED_BEFORE_MERGE",
        )
    ):
        bad("check7: the outbox review states no foundation verdict")

    # 8. The review changed NO implementation path.
    changed = _changed_vs_reviewed_branch()
    for path in changed:
        for prefix in FORBIDDEN_CHANGED_PREFIXES:
            if path.startswith(prefix):
                bad(f"check8: the review modified a forbidden implementation path: {path}")

    # 9. The masking rule holds for every artifact this review committed.
    for path in changed:
        target = ROOT / path
        if not target.is_file():
            continue
        content = target.read_text(encoding="utf-8", errors="ignore")
        for pattern in MASKED_PATTERNS:
            if pattern in content:
                bad(f"check9: unmasked internal identifier '{pattern}' in {path}")

    # 10. The stage manifest declares the required review posture.
    manifest = texts["manifest"]
    for required in (
        'stage: "66C.4-BE1-R"',
        'task_type: "independent-technical-security-migration-review"',
        'status: "review-complete"',
        "reviewer_independent_session_required: true",
        "reviewer_independent_worktree_required: true",
        "isolated_postgresql_testing_allowed: true",
        "product_owner_review_required: true",
    ):
        if required not in manifest:
            bad(f"check10: stage manifest missing required declaration: {required}")
    for must_be_false in (
        "original_implementation_session_allowed",
        "private_reasoning_transfer_allowed",
        "uncommitted_artifact_access_allowed",
        "implementation_change_allowed",
        "migration_change_allowed",
        "backend_change_allowed",
        "api_change_allowed",
        "workflow_change_allowed",
        "scheduler_allowed",
        "relay_allowed",
        "producer_cutover_allowed",
        "merge_allowed",
        "deployment_allowed",
        "be2_authorized",
        "codex_authorized",
        "claude_design_authorized",
    ):
        if f"{must_be_false}: false" not in manifest:
            bad(f"check10: stage manifest must declare {must_be_false}: false")

    # 11. progress.md records the review stage.
    progress = (ROOT / "source" / "progress.md").read_text(encoding="utf-8").lower()
    if "66c.4-be1-r" not in progress:
        bad("check11: source/progress.md does not reference Stage 66C.4-BE1-R")

    # 12. Every artifact carries the house non-production footer and safety comment.
    for name, path in REVIEW_DOCS.items():
        if path.suffix != ".md":
            continue
        text = texts[name]
        if "<!-- staging-safety:" not in text:
            bad(f"check12: staging-safety comment missing from {path.name}")
        if "Non-production only" not in text:
            bad(f"check12: non-production footer missing from {path.name}")

    if failures:
        print(f"{PROCESS_MARKER}: FAIL")
        return 1

    print("  [OK] All eleven review artifacts present and substantive; review-process marker and")
    print("       technical verdict recorded SEPARATELY and consistently across master review and")
    print("       handoff; all seven mandatory reproductions evidenced; outbox capability matrix")
    print("       classified with an explicit foundation verdict; zero implementation/migration/")
    print("       app/infra paths modified by the review; masking rule clean; stage manifest")
    print(
        "       declares the independent-review posture; progress.md updated; house footers present"
    )
    print(f"{PROCESS_MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
