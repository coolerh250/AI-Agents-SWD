#!/usr/bin/env python3
"""Step 66C.4-P-R1 -- reminder/expiry/controlled resume contract remediation verifier.

Confirms the seven corrections (A-G) from the Product Architect PASS_WITH_GAPS review are present
and internally consistent in the planning/contract set, and that no runtime/migration/deployment
change is claimed, Codex/Claude Design remain unauthorized, and Step 66C.4-BE1 remains not started.

This is a documentation-only verifier: it reads files on the current checkout and does not touch any
runtime or remote host.

Marker: STEP66C4_PLANNING_CONTRACT_REMEDIATION_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_DIR = ROOT / "docs" / "contracts" / "66c4-reminder-expiry-controlled-resume"

DATA_MODEL = CONTRACT_DIR / "data-model-contract.md"
LIFECYCLE = CONTRACT_DIR / "lifecycle-and-time-contract.md"
API_EVENT = CONTRACT_DIR / "api-and-event-contract.md"
SCHEDULER = CONTRACT_DIR / "scheduler-architecture-decision.md"
RESUME = CONTRACT_DIR / "controlled-resume-contract.md"
RACE = CONTRACT_DIR / "race-condition-and-failure-analysis.md"
OBSERV = CONTRACT_DIR / "observability-and-audit-plan.md"
SLICING = CONTRACT_DIR / "implementation-stage-slicing-plan.md"
TESTPLAN = CONTRACT_DIR / "test-and-validation-plan.md"
CHECKLIST = CONTRACT_DIR / "product-owner-decision-checklist.md"
REMEDIATION = CONTRACT_DIR / "contract-remediation-record.md"

HANDOFF = (
    ROOT / "docs" / "handoffs" / "66c4-reminder-expiry-controlled-resume" / "planning-handoff.md"
)
TEST_RECORD = (
    ROOT
    / "docs"
    / "test"
    / "step66c4-reminder-expiry-controlled-resume-planning-remediation-record.md"
)

STAGE_DIR = ROOT / "docs" / "stages" / "66c4-reminder-expiry-controlled-resume-planning-remediation"
STAGE_DOCS = {
    "stage-manifest": STAGE_DIR / "stage-manifest.yaml",
    "context-receipt": STAGE_DIR / "context-receipt.md",
    "stage-gate-report": STAGE_DIR / "stage-gate-report.md",
}

PROGRESS = ROOT / "source" / "progress.md"

MARKER = "STEP66C4_PLANNING_CONTRACT_REMEDIATION_VERIFY"

TEXT_DOCS = {
    "data-model": DATA_MODEL,
    "lifecycle": LIFECYCLE,
    "api-event": API_EVENT,
    "scheduler": SCHEDULER,
    "resume": RESUME,
    "race": RACE,
    "observability": OBSERV,
    "slicing": SLICING,
    "test-plan": TESTPLAN,
    "checklist": CHECKLIST,
    "remediation-record": REMEDIATION,
    "handoff": HANDOFF,
    "test-record": TEST_RECORD,
}

SECRET_SHAPES = re.compile(
    r"(-----BEGIN [A-Z ]*PRIVATE KEY|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
    r"AKIA[0-9A-Z]{16}|xoxb-[A-Za-z0-9-]{10,}|sk-ant-[A-Za-z0-9_-]{20,})"
)
INFRA_SHAPES = re.compile(
    r"(10\.0\.1\.31|10\.0\.1\.32|aiagent-swd|itadmin|stpadmin)", re.IGNORECASE
)
WINDOWS_PATH_SHAPE = re.compile(r"[A-Za-z]:[\\/]Users[\\/]", re.IGNORECASE)

FORBIDDEN_CLAIM_PATTERNS = (
    re.compile(r"backend (?:was|is) changed", re.IGNORECASE),
    re.compile(r"api (?:was|is) implemented", re.IGNORECASE),
    re.compile(r"database (?:was|is) changed", re.IGNORECASE),
    re.compile(r"migration (?:was|is) created", re.IGNORECASE),
    re.compile(r"workflow (?:was|is) changed", re.IGNORECASE),
    re.compile(r"scheduler (?:was|is) activated", re.IGNORECASE),
    re.compile(r"resume (?:was|is) dispatched", re.IGNORECASE),
    re.compile(r"deployment (?:was|is) performed", re.IGNORECASE),
    re.compile(r"external notification (?:was|is) sent", re.IGNORECASE),
    re.compile(r"production action (?:was|is) triggered", re.IGNORECASE),
    re.compile(r"codex is authorized", re.IGNORECASE),
    re.compile(r"claude design is authorized", re.IGNORECASE),
    re.compile(r"step 66c\.4-be1 (?:was|is|has) started", re.IGNORECASE),
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
    "gated",
    "disabled",
    "remains not started",
    "not started",
)
NEGATION_WINDOW = 200

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


def _need(name: str, text: str, needle: str, label: str) -> None:
    if needle not in text:
        bad(f"{label}: '{needle}' missing from {name}")


def _exactly_once_not_claimed(combined: str) -> None:
    # Exactly-once must never be positively claimed.
    positive = (
        "guarantees exactly-once",
        "provides exactly-once",
        "exactly-once delivery guarantee",
        "exactly-once is guaranteed",
        "exactly-once delivery is provided",
    )
    for phrase in positive:
        if phrase in combined:
            bad(f"exactly-once is positively claimed: '{phrase}'")
    # And an explicit disclaimer must be present.
    if not any(
        d in combined
        for d in (
            "never exactly-once",
            "not claim exactly-once",
            "exactly-once is not",
            "not exactly-once",
        )
    ):
        bad("no explicit 'exactly-once is not claimed' disclaimer found")


def main() -> int:
    for name, p in TEXT_DOCS.items():
        if not p.is_file():
            bad(f"missing doc: {p} ({name})")
    for name, p in STAGE_DOCS.items():
        if not p.is_file():
            bad(f"missing stage doc: {p} ({name})")
    if not PROGRESS.is_file():
        bad(f"missing progress log: {PROGRESS}")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    texts = {name: _norm(p.read_text(encoding="utf-8")) for name, p in TEXT_DOCS.items()}
    raw_texts = {name: p.read_text(encoding="utf-8") for name, p in TEXT_DOCS.items()}
    combined = "\n".join(texts.values())
    progress_low = _norm(PROGRESS.read_text(encoding="utf-8"))

    # 1. Proposed field count is internally consistent (exactly six lifecycle columns).
    _need(
        "data-model", texts["data-model"], "exactly six new lifecycle columns", "check1-field-count"
    )
    for col in (
        "reminder_sent_at",
        "expired_at",
        "resume_eligible_at",
        "resume_requested_at",
        "resume_requested_by",
        "resume_authorized_at",
    ):
        _need("data-model", texts["data-model"], col, "check1-field-name")
    if "resume_dispatched_at" in texts["data-model"] and "removed" not in texts["data-model"]:
        bad("check1: resume_dispatched_at present without a 'removed' disposition")

    # 2. Every resume field has defined semantics (per-transition state model with actor/trigger).
    for token in (
        "actor:",
        "trigger:",
        "precondition:",
        "resume_requested_by",
        "resume_authorized_at",
    ):
        _need("resume", texts["resume"], token, "check2-resume-semantics")

    # 3. expires_at / due_at is the authoritative deadline.
    _need(
        "lifecycle",
        texts["lifecycle"],
        "authoritative expiry deadline",
        "check3-authoritative-deadline",
    )
    _need("lifecycle", texts["lifecycle"], "exclusive upper bound", "check3-exclusive-bound")

    # 4. Scheduler lag does not extend the answer window.
    _need(
        "lifecycle",
        texts["lifecycle"],
        "scheduler lag never extends the answer window",
        "check4-lag",
    )

    # 5. Answer-at-expiry behavior is defined.
    _need("lifecycle", texts["lifecycle"], "exactly at due_at", "check5-answer-at-expiry")

    # 6. Reminder delivery is at-least-once and idempotent.
    _need("lifecycle", texts["lifecycle"], "at-least-once", "check6-at-least-once")
    if "idempotent" not in texts["lifecycle"]:
        bad("check6: 'idempotent' missing from lifecycle")

    # 7. Exactly-once is not claimed.
    _exactly_once_not_claimed(combined)

    # 8. State/audit/event durability model is binding.
    _need("api-event", texts["api-event"], "atomicity model (binding", "check8-binding-atomicity")

    # 9. Durable outbox (or equivalent) is selected.
    _need("api-event", texts["api-event"], "transactional outbox", "check9-outbox")
    if "selected model" not in texts["api-event"]:
        bad("check9: 'selected model' framing missing from api-event")
    _need(
        "data-model", texts["data-model"], "clarification_lifecycle_outbox", "check9-outbox-table"
    )

    # 10. DB clock wording is not absolute or misleading.
    _need("lifecycle", texts["lifecycle"], "authoritative lifecycle clock", "check10-clock")
    _need("lifecycle", texts["lifecycle"], "does not eliminate", "check10-non-absolute")
    for banned in ("no clock skew risk", "eliminated by design"):
        if banned in combined:
            bad(f"check10: absolute/misleading clock phrase still present: '{banned}'")

    # 11. Automatic and operator recovery are separated.
    _need("race", texts["race"], "automatic recovery", "check11-auto-recovery")
    _need("race", texts["race"], "operator recovery", "check11-operator-recovery")

    # 12. Resume requested and authorized are separate transitions.
    _need("resume", texts["resume"], "resume_requested -> resume_authorized", "check12-req-vs-auth")

    # 13. Resume dispatched and workflow resumed are separate states.
    _need(
        "resume",
        texts["resume"],
        "resume_dispatched -> workflow_resumed",
        "check13-dispatch-vs-resumed",
    )

    # 14. Operator action does not imply resume completed.
    if "never equivalent" not in texts["resume"]:
        bad("check14: operator-request-not-equal-resumed statement missing from resume contract")

    # 15. Cancelled/aborted/terminal protection remains.
    if not re.search(
        r"cancel(?:l?ed)?[^.]{0,80}(cannot|must not|blocked|protection|unconditionally)", combined
    ):
        bad("check15: cancelled/terminal resume protection statement missing")

    # 16. Production-effect protection remains.
    if "production_effect" not in combined and "production-effect" not in combined:
        bad("check16: production-effect reference missing")
    if "blocked" not in texts["resume"]:
        bad("check16: production-effect 'blocked' protection missing from resume contract")

    # 17. Six PO decisions are fully listed.
    for n in range(1, 7):
        if f"decision {n}" not in texts["checklist"]:
            bad(f"check17: 'Decision {n}' missing from checklist")

    # 18. Recommended defaults are advisory, not approved.
    if "advisory" not in combined or "not approved" not in combined:
        bad("check18: advisory-not-approved statement missing")
    if "authorizes nothing" not in texts["checklist"]:
        bad("check18: checklist 'authorizes nothing' statement missing")

    # 19. BE1/BE2/BE3 slicing reflects corrected architecture.
    _need("slicing", texts["slicing"], "atomicity foundation", "check19-be1")
    _need("slicing", texts["slicing"], "outbox relay", "check19-be2")
    _need("slicing", texts["slicing"], "orchestrator resume confirmation", "check19-be3")

    # 20. No runtime code/migration/deployment is claimed.
    for term, phrase in (("migration", "no migration created"), ("deployment", "no deployment")):
        if phrase not in combined:
            bad(f"check20: '{phrase}' statement missing")

    # 21. Codex and Claude Design remain unauthorized.
    if "codex" not in combined or "claude design" not in combined:
        bad("check21: Codex/Claude Design reference missing")
    if "unauthorized" not in combined and "not authorized" not in combined:
        bad("check21: Codex/Claude Design unauthorized statement missing")

    # 22. Step 66C.4-BE1 remains not started.
    if "66c.4-be1" not in combined or "not started" not in combined:
        bad("check22: Step 66C.4-BE1 not-started statement missing")

    # 23. source/progress.md updated.
    if "66c.4-p-r1" not in progress_low:
        bad("check23: source/progress.md does not reference Stage 66C.4-P-R1")

    # Safety scans across remediation-authored docs.
    for name, text in raw_texts.items():
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

    print("  [OK] Seven corrections (A-G) present and internally consistent: six reconciled")
    print("       lifecycle columns + durable outbox; authoritative exclusive deadline with")
    print("       scheduler-lag-does-not-extend-window; at-least-once + idempotent, exactly-once")
    print("       not claimed; binding transactional-outbox atomicity model; non-absolute clock")
    print(
        "       wording; automatic vs operator recovery separated; request/authorized/dispatched/"
    )
    print("       resumed as separate transitions with operator-request != resumed; cancelled &")
    print("       production-effect protection retained; six advisory (not approved) PO decisions;")
    print("       BE1/BE2/BE3 slicing corrected; no runtime/migration/deployment claimed; Codex/")
    print("       Claude Design unauthorized; Step 66C.4-BE1 not started; progress.md updated; no")
    print("       forbidden claims or sensitive identifiers")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
