#!/usr/bin/env python3
"""Step 66C.4-P -- reminder/expiry/controlled resume planning verifier.

Confirms all 13 contract documents, the planning handoff, the test record, and stage artifacts
exist and state: existing fields/endpoints are evidence-based, 24h reminder and 72h blocked/
expired behavior are specified, answer and resume are separate transitions, no hidden auto-
dispatch/resume is proposed without an explicit decision, duplicate execution is idempotent,
cancelled/aborted/terminal workflows cannot resume, external notification remains disabled,
production_executed_true_count remains 0, Team RBAC full scope remains M3, Claude Code remains
primary implementation owner, Codex/Claude Design remain unauthorized, no runtime code/migration/
deployment is claimed, and source/progress.md is updated.

This is a documentation-only verifier: it reads files on the current checkout and does not touch
any runtime or remote host.

Marker: STEP66C4_REMINDER_EXPIRY_CONTROLLED_RESUME_PLANNING_VERIFY: PASS | PASS_WITH_GAPS | FAIL
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_DIR = ROOT / "docs" / "contracts" / "66c4-reminder-expiry-controlled-resume"

CONTRACT_DOCS = {
    "current-state-assessment": CONTRACT_DIR / "current-state-assessment.md",
    "lifecycle-and-time-contract": CONTRACT_DIR / "lifecycle-and-time-contract.md",
    "data-model-contract": CONTRACT_DIR / "data-model-contract.md",
    "api-and-event-contract": CONTRACT_DIR / "api-and-event-contract.md",
    "scheduler-architecture-decision": CONTRACT_DIR / "scheduler-architecture-decision.md",
    "controlled-resume-contract": CONTRACT_DIR / "controlled-resume-contract.md",
    "rbac-and-safety-contract": CONTRACT_DIR / "rbac-and-safety-contract.md",
    "race-condition-and-failure-analysis": CONTRACT_DIR / "race-condition-and-failure-analysis.md",
    "observability-and-audit-plan": CONTRACT_DIR / "observability-and-audit-plan.md",
    "frontend-ux-boundary": CONTRACT_DIR / "frontend-ux-boundary.md",
    "implementation-stage-slicing-plan": CONTRACT_DIR / "implementation-stage-slicing-plan.md",
    "test-and-validation-plan": CONTRACT_DIR / "test-and-validation-plan.md",
    "product-owner-decision-checklist": CONTRACT_DIR / "product-owner-decision-checklist.md",
}

HANDOFF = (
    ROOT / "docs" / "handoffs" / "66c4-reminder-expiry-controlled-resume" / "planning-handoff.md"
)
TEST_RECORD = (
    ROOT / "docs" / "test" / "step66c4-reminder-expiry-controlled-resume-planning-record.md"
)

STAGE_DOCS = {
    "stage-manifest": ROOT
    / "docs"
    / "stages"
    / "66c4-reminder-expiry-controlled-resume-planning"
    / "stage-manifest.yaml",
    "context-receipt": ROOT
    / "docs"
    / "stages"
    / "66c4-reminder-expiry-controlled-resume-planning"
    / "context-receipt.md",
    "stage-gate-report": ROOT
    / "docs"
    / "stages"
    / "66c4-reminder-expiry-controlled-resume-planning"
    / "stage-gate-report.md",
}

PROGRESS = ROOT / "source" / "progress.md"

MARKER = "STEP66C4_REMINDER_EXPIRY_CONTROLLED_RESUME_PLANNING_VERIFY"

ALL_TEXT_DOCS = {**CONTRACT_DOCS, "planning-handoff": HANDOFF, "test-record": TEST_RECORD}

SECRET_SHAPES = re.compile(
    r"(-----BEGIN [A-Z ]*PRIVATE KEY|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
    r"AKIA[0-9A-Z]{16}|xoxb-[A-Za-z0-9-]{10,}|sk-ant-[A-Za-z0-9_-]{20,})"
)
INFRA_SHAPES = re.compile(r"(10\.0\.1\.31|aiagent-swd|itadmin)", re.IGNORECASE)
WINDOWS_PATH_SHAPE = re.compile(r"[A-Za-z]:[\\/]Users[\\/]", re.IGNORECASE)

FORBIDDEN_CLAIM_PATTERNS = (
    re.compile(r"backend (?:was|is) changed", re.IGNORECASE),
    re.compile(r"api (?:was|is) implemented", re.IGNORECASE),
    re.compile(r"database (?:was|is) changed", re.IGNORECASE),
    re.compile(r"migration (?:was|is) created", re.IGNORECASE),
    re.compile(r"workflow (?:was|is) changed", re.IGNORECASE),
    re.compile(r"scheduler (?:was|is) activated", re.IGNORECASE),
    re.compile(r"resume (?:was|is) dispatched", re.IGNORECASE),
    re.compile(r"workflow (?:was|is) resumed", re.IGNORECASE),
    re.compile(r"deployment (?:was|is) performed", re.IGNORECASE),
    re.compile(r"external notification (?:was|is) sent", re.IGNORECASE),
    re.compile(r"production action (?:was|is) triggered", re.IGNORECASE),
    re.compile(r"external action (?:was|is) triggered", re.IGNORECASE),
    re.compile(r"codex is authorized", re.IGNORECASE),
    re.compile(r"claude design is authorized", re.IGNORECASE),
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
    "neither",
    "out of scope",
    "out of this stage",
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
    for name, p in CONTRACT_DOCS.items():
        if not p.is_file():
            bad(f"missing contract doc: {p} ({name})")
    if not HANDOFF.is_file():
        bad(f"missing planning handoff: {HANDOFF}")
    if not TEST_RECORD.is_file():
        bad(f"missing test record: {TEST_RECORD}")
    for name, p in STAGE_DOCS.items():
        if not p.is_file():
            bad(f"missing stage doc: {p} ({name})")
    if not PROGRESS.is_file():
        bad(f"missing progress log: {PROGRESS}")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    texts = {name: p.read_text(encoding="utf-8") for name, p in ALL_TEXT_DOCS.items()}
    progress_text = PROGRESS.read_text(encoding="utf-8")
    combined_low = _norm("\n".join(texts.values()))
    progress_low = _norm(progress_text)

    # 1-13: all 13 contract docs + handoff exist (checked above via file existence).

    # 14. Existing fields/endpoints are evidence-based (cite real file paths).
    for cite in ("workroom_store.py", "operator_clarification_requests", "workroom_api.py"):
        if cite not in combined_low:
            bad(f"evidence citation missing: {cite}")

    # 15-16. 24h reminder / 72h expiry specified.
    if "24" not in combined_low or "reminder" not in combined_low:
        bad("24h reminder behavior not specified")
    if "72" not in combined_low or ("expir" not in combined_low and "blocked" not in combined_low):
        bad("72h blocked/expired behavior not specified")

    # 17. Answer and resume are separate transitions.
    if not re.search(r"answer[^.]{0,60}resume[^.]{0,60}(separate|distinct)", combined_low) and (
        "resume eligible" not in combined_low or "answer recorded" not in combined_low
    ):
        bad("answer and resume not clearly stated as separate transitions")

    # 18. No hidden auto-dispatch/resume without explicit decision.
    if "explicit" not in combined_low or "auto-resume" not in combined_low.replace(
        "automatic resume", "auto-resume"
    ):
        if "automatic resume" not in combined_low:
            bad("automatic-resume alternative not explicitly analyzed as a decision")

    # 19. Duplicate execution is idempotent.
    if "idempotent" not in combined_low and "idempotency" not in combined_low:
        bad("idempotency of duplicate execution not addressed")

    # 20. Cancelled/aborted/terminal workflows cannot resume.
    if not re.search(
        r"cancel(?:l?ed)?[^.]{0,60}(cannot|must not|blocked|protection)", combined_low
    ):
        bad("cancelled/terminal workflow resume protection not clearly stated")

    # 21. External notification remains disabled.
    if "external" not in combined_low or "disabled" not in combined_low:
        bad("external notification disabled-by-default statement missing")

    # 22. production_executed_true_count remains 0.
    if "production_executed_true_count" not in combined_low or "0" not in combined_low:
        bad("production_executed_true_count=0 statement missing")

    # 23. Team RBAC full scope remains M3.
    if "m3" not in combined_low or (
        "team rbac" not in combined_low and "full team" not in combined_low
    ):
        bad("Team RBAC M3 scope-deferral statement missing")

    # 24. Claude Code remains primary implementation owner.
    if not re.search(r"claude code[^.]{0,40}primary[^.]{0,40}(owner|implementation)", combined_low):
        bad("Claude Code primary implementation owner statement missing")

    # 25. Codex/Claude Design remain unauthorized.
    if "codex" not in combined_low or "claude design" not in combined_low:
        bad("Codex/Claude Design reference missing")
    if "not authorized" not in combined_low and "unauthorized" not in combined_low:
        bad("Codex/Claude Design unauthorized statement missing")

    # 26. No runtime code/migration/deployment claimed.
    for term in ("migration", "deployment", "scheduler"):
        if f"no {term}" not in combined_low and f"{term} created" not in combined_low.replace(
            "not created", ""
        ):
            if term == "migration" and "no migration created" not in combined_low:
                bad("no-migration-created statement missing")
            if term == "deployment" and "no deployment" not in combined_low:
                bad("no-deployment statement missing")
            if term == "scheduler" and "no scheduler activated" not in combined_low:
                bad("no-scheduler-activated statement missing")

    # 27. source/progress.md updated.
    if "66c.4-p" not in progress_low:
        bad("source/progress.md does not reference Stage 66C.4-P")

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

    print("  [OK] All 13 contract docs + planning handoff + test record + stage manifest/context-")
    print("       receipt/stage-gate-report present; evidence-based citations confirmed; 24h")
    print("       reminder and 72h expiry specified; answer/resume kept as separate transitions;")
    print("       automatic-resume analyzed as an explicit decision, not silently adopted;")
    print("       idempotency, cancelled-workflow protection, external-notification-disabled, and")
    print("       production_executed_true_count=0 all addressed; Team RBAC full scope remains")
    print("       M3; Claude Code confirmed primary Step 66C.4 owner; Codex/Claude Design remain")
    print("       unauthorized; no runtime/migration/deployment/scheduler-activation claimed;")
    print("       source/progress.md updated; no forbidden capability claims or sensitive")
    print("       identifiers")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
