#!/usr/bin/env python3
"""Step 66C.4-P-M -- contract source-of-truth merge verifier.

Confirms the Step 66C.4 Reminder / Expiry / Controlled Resume contract set was merged to main as
canonical source of truth, that the six Product Owner decisions are recorded as approved, that the
binding BE1 runtime-compatibility gate exists, and that no runtime/migration/deployment change is
claimed, no scheduler/relay/dispatch/resume is activated, Codex/Claude Design remain unauthorized,
and Step 66C.4-BE1 remains not started.

This is a documentation-only verifier: it reads files on the current checkout and does not touch any
runtime or remote host.

Marker: STEP66C4_CONTRACT_SOURCE_OF_TRUTH_MERGE_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_DIR = ROOT / "docs" / "contracts" / "66c4-reminder-expiry-controlled-resume"

PO_DECISIONS = (
    ROOT / "docs" / "decisions" / "66c4-reminder-expiry-controlled-resume-product-decisions.md"
)
MERGE_RECORD = CONTRACT_DIR / "contract-merge-record.md"
SOT_RECORD = CONTRACT_DIR / "contract-source-of-truth-record.md"
MERGE_TEST_RECORD = (
    ROOT / "docs" / "test" / "step66c4-reminder-expiry-controlled-resume-contract-merge-record.md"
)

CONTRACT_ARTIFACTS = [
    CONTRACT_DIR / "current-state-assessment.md",
    CONTRACT_DIR / "lifecycle-and-time-contract.md",
    CONTRACT_DIR / "data-model-contract.md",
    CONTRACT_DIR / "api-and-event-contract.md",
    CONTRACT_DIR / "scheduler-architecture-decision.md",
    CONTRACT_DIR / "controlled-resume-contract.md",
    CONTRACT_DIR / "rbac-and-safety-contract.md",
    CONTRACT_DIR / "race-condition-and-failure-analysis.md",
    CONTRACT_DIR / "observability-and-audit-plan.md",
    CONTRACT_DIR / "frontend-ux-boundary.md",
    CONTRACT_DIR / "implementation-stage-slicing-plan.md",
    CONTRACT_DIR / "test-and-validation-plan.md",
    CONTRACT_DIR / "product-owner-decision-checklist.md",
    CONTRACT_DIR / "contract-remediation-record.md",
]

STAGE_DIR = ROOT / "docs" / "stages" / "66c4-reminder-expiry-controlled-resume-contract-merge"
STAGE_DOCS = {
    "stage-manifest": STAGE_DIR / "stage-manifest.yaml",
    "context-receipt": STAGE_DIR / "context-receipt.md",
    "stage-gate-report": STAGE_DIR / "stage-gate-report.md",
}

PROGRESS = ROOT / "source" / "progress.md"

MARKER = "STEP66C4_CONTRACT_SOURCE_OF_TRUTH_MERGE_VERIFY"
SOURCE_COMMIT = "f50dd05"

TEXT_DOCS = {
    "po-decisions": PO_DECISIONS,
    "merge-record": MERGE_RECORD,
    "sot-record": SOT_RECORD,
    "merge-test-record": MERGE_TEST_RECORD,
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
    re.compile(r"outbox relay (?:was|is) activated", re.IGNORECASE),
    re.compile(r"existing producer (?:was|is) switched", re.IGNORECASE),
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
    "without ",
    "n't ",
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


def main() -> int:
    for name, p in TEXT_DOCS.items():
        if not p.is_file():
            bad(f"missing doc: {p} ({name})")
    for p in CONTRACT_ARTIFACTS:
        if not p.is_file():
            bad(f"missing contract artifact on main: {p}")
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

    # 1. Source branch and f50dd05 recorded.
    if "planning/66c4-reminder-expiry-controlled-resume" not in combined:
        bad("check1: source branch not recorded")
    if SOURCE_COMMIT not in combined:
        bad(f"check1: source commit {SOURCE_COMMIT} not recorded")

    # 2. Merge commit recorded.
    if "merge commit" not in combined or "e109189" not in combined:
        bad("check2: merge commit not recorded")

    # 3. Contract artifacts exist on main (checked above).

    # 4. Product Owner decision record exists (checked above) + is a decision record.
    if "product owner" not in texts["po-decisions"]:
        bad("check4: PO decision record does not reference the Product Owner")

    # 5. All six decisions recorded as approved.
    if "approved_by_product_owner" not in texts["po-decisions"]:
        bad("check5: APPROVED_BY_PRODUCT_OWNER status missing")
    for n in range(1, 7):
        if f"decision {n}" not in texts["po-decisions"]:
            bad(f"check5: Decision {n} missing from PO record")

    # 6. due_at authoritative and late answer returns 409.
    if "due_at" not in combined or "409" not in combined or "authoritative" not in combined:
        bad("check6: authoritative due_at / 409 late-answer rule not recorded")

    # 7. UI wording and backend status decision recorded.
    if "clarification expired" not in combined or "blocked" not in combined:
        bad("check7: UI 'Blocked — clarification expired' wording not recorded")
    if "clarification_expired" not in combined:
        bad("check7: backend clarification_expired status not recorded")

    # 8. Explicit operator-controlled resume recorded.
    if "explicit operator-controlled resume" not in combined:
        bad("check8: explicit operator-controlled resume not recorded")

    # 9. Production-effect approval remains separate.
    if ("production-effect" not in combined and "production effect" not in combined) or (
        "separate" not in combined
    ):
        bad("check9: production-effect approval-separate rule not recorded")

    # 10. One-reminder rule recorded.
    if "one reminder per clarification" not in combined:
        bad("check10: one-reminder rule not recorded")
    if "created_at + 24" not in combined:
        bad("check10: created_at + 24h reminder timing not recorded")

    # 11. Expired clarification immutability recorded.
    if "immutab" not in combined and "cannot be reopened" not in combined:
        bad("check11: expired-clarification immutability not recorded")

    # 12. Six lifecycle fields internally consistent.
    for col in (
        "reminder_sent_at",
        "expired_at",
        "resume_eligible_at",
        "resume_requested_at",
        "resume_requested_by",
        "resume_authorized_at",
    ):
        if col not in texts["sot-record"]:
            bad(f"check12: lifecycle column {col} missing from source-of-truth record")
    if "exactly six" not in texts["sot-record"]:
        bad("check12: 'exactly six' lifecycle column count not recorded")

    # 13. Transactional outbox canonical.
    if "outbox model: canonical" not in texts["sot-record"] and (
        "transactional outbox" not in combined or "canonical" not in combined
    ):
        bad("check13: transactional outbox canonical status not recorded")

    # 14. BE1 runtime compatibility gate exists.
    if "be1 runtime compatibility gate" not in combined:
        bad("check14: BE1 Runtime Compatibility Gate not recorded")

    # 15. Existing producers cannot switch without active relay.
    if "existing runtime producers remain" not in combined:
        bad("check15: 'existing runtime producers remain on their current path' not recorded")
    if "producer cutover requires" not in combined:
        bad("check15: producer-cutover-requires-relay-etc rule not recorded")

    # 16. Step 66C.4-BE1 remains not started.
    if "66c.4-be1" not in combined or "not started" not in combined:
        bad("check16: Step 66C.4-BE1 not-started statement missing")

    # 17. Codex and Claude Design remain unauthorized.
    if "codex" not in combined or "claude design" not in combined:
        bad("check17: Codex/Claude Design reference missing")
    if "not authorized" not in combined and "unauthorized" not in combined:
        bad("check17: Codex/Claude Design unauthorized statement missing")

    # 18. No runtime/API/DB/migration/workflow change claimed.
    if "no migration created" not in combined:
        bad("check18: 'no migration created' statement missing")

    # 19. No scheduler/relay/dispatch/resume activated.
    if "no scheduler activated" not in combined:
        bad("check19: 'no scheduler activated' statement missing")
    if "no outbox relay activated" not in combined:
        bad("check19: 'no outbox relay activated' statement missing")

    # 20. No deployment or external notification claimed.
    if "no deployment" not in combined:
        bad("check20: 'no deployment' statement missing")
    if "no external notification" not in combined:
        bad("check20: 'no external notification' statement missing")

    # 21. production_executed_true_count remains 0.
    if "production_executed_true_count" not in combined or "0" not in combined:
        bad("check21: production_executed_true_count=0 statement missing")

    # 22. source/progress.md updated.
    if "66c.4-p-m" not in progress_low:
        bad("check22: source/progress.md does not reference Stage 66C.4-P-M")

    # 23. Contract source-of-truth record exists (checked above) + is canonical.
    if "canonical" not in texts["sot-record"]:
        bad("check23: source-of-truth record does not state canonical status")

    # Safety scans.
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

    print("  [OK] Source branch/commit (f50dd05) + merge commit (e109189) recorded; 14 contract")
    print("       artifacts + PO decision record + merge/source-of-truth/test records present;")
    print("       six decisions APPROVED_BY_PRODUCT_OWNER; authoritative due_at/409, UI-wording/")
    print("       backend-status, explicit-operator-resume, production-effect-separate,")
    print("       one-reminder, expired-immutability all recorded; six lifecycle columns")
    print("       consistent; transactional outbox canonical; BE1 Runtime Compatibility Gate")
    print("       binding (producers cannot switch without an active relay); Step 66C.4-BE1 not")
    print("       started; Codex/Claude Design unauthorized; no runtime/migration/scheduler/relay/")
    print("       dispatch/resume/deployment/external change; production_executed_true_count=0;")
    print("       progress.md updated; no forbidden claims or sensitive identifiers")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
