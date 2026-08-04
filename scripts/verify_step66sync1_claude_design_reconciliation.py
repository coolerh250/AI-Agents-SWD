#!/usr/bin/env python3
"""Step 66SYNC.1-C -- Claude Design POC journey / UX reconciliation verifier.

Deterministic, read-only. Confirms the Claude Design reconciliation deliverables exist and are
internally consistent with the canonical baseline and both partner sync heads, that the full
Product Owner POC journey and all required screens are documented, that delivery/acceptance and
failure/recovery flows are covered, that private reasoning/secrets are excluded, that D-1/D-2/D-3
are carried forward, and that no frontend/runtime/deployment/action was performed.

Does not start any runtime or container. Only reads committed/working files and computes a local
git diff against origin/main to confirm scope.

Marker: STEP66SYNC1_CLAUDE_DESIGN_RECONCILIATION_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "STEP66SYNC1_CLAUDE_DESIGN_RECONCILIATION_VERIFY"

SPEC = ROOT / "docs" / "design" / "ai-agent-team-functional-poc-control-center-spec.md"
ACK = ROOT / "docs" / "handoffs" / "program-sync" / "step66sync1-claude-design-acknowledgement.md"
GAPS = ROOT / "docs" / "handoffs" / "program-sync" / "step66sync1-claude-design-ux-gap-register.md"
EVID = ROOT / "docs" / "test" / "step66sync1-claude-design-reconciliation-evidence.md"

CANONICAL_MAIN = "c1db4cc"
CC_HEAD = "828ea90"
CODEX_HEAD = "78aa4ee"
CONTEXT_ID = "AIAT-SYNC-20260803-01"

REQUIRED_SCREENS = [
    "POC Goal Entry",
    "Scope and Acceptance Review",
    "Execution Plan",
    "Project Overview",
    "Task Graph",
    "Agent/Partner Timeline",
    "Artifact Explorer",
    "Approval Center",
    "Blocker and Failure Center",
    "QA Dashboard",
    "Delivery Package",
    "Final Acceptance",
    "Cost and External Actions",
    "Safety Summary",
    "Retrospective",
]

# Sentinel phrases proving each of the 13 journey steps is documented.
JOURNEY_MARKERS = [
    "inputs a development goal",
    "interprets the problem statement",
    "reviews scope and non-scope",
    "approves requirements and acceptance criteria",
    "builds an execution plan",
    "reviews task graph and responsibility",
    "begin collaboration",
    "observes real-time progress and artifacts",
    "handles approval, blocker, or scope change",
    "QA runs verification",
    "builds the delivery package",
    "performs final acceptance",
    "presents a retrospective",
]

MUST_NOT_DISPLAY = [
    "private chain of thought",
    "raw system prompt",
    "raw token",
    "secret",
    "credential",
]

SECRET_SHAPES = re.compile(
    r"(-----BEGIN [A-Z ]*PRIVATE KEY|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
    r"AKIA[0-9A-Z]{16}|xoxb-[A-Za-z0-9-]{10,}|sk-ant-[A-Za-z0-9_-]{20,})"
)
# Local absolute paths that must never be committed.
ABS_PATH_SHAPES = re.compile(r"(C:\\\\Users|C:/Users|/home/[A-Za-z0-9._-]+/|/Users/[A-Za-z0-9._-]+/)")

FORBIDDEN_RUNTIME_PREFIXES = (
    "apps/",
    "services/",
    "infra/",
    "migrations/",
    "database/",
    "shared/",
    ".github/workflows/",
)

failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8") if p.is_file() else ""


def contains(text: str, needle: str) -> bool:
    return needle.lower() in text.lower()


def check_exist() -> None:
    for p in (SPEC, ACK, GAPS, EVID):
        if not p.is_file():
            bad(f"missing deliverable: {p}")


def check_context() -> None:
    for name, p in (("spec", SPEC), ("ack", ACK), ("gaps", GAPS), ("evid", EVID)):
        t = read(p)
        if CONTEXT_ID not in t:
            bad(f"{name}: Context ID {CONTEXT_ID} missing")
        if CANONICAL_MAIN not in t:
            bad(f"{name}: canonical main {CANONICAL_MAIN} missing")
    # heads must appear in ack + spec + evid
    for name, p in (("spec", SPEC), ("ack", ACK), ("evid", EVID)):
        t = read(p)
        if CC_HEAD not in t:
            bad(f"{name}: Claude Code sync head {CC_HEAD} missing")
        if CODEX_HEAD not in t:
            bad(f"{name}: Codex sync head {CODEX_HEAD} missing")
    ack = read(ACK)
    if "context_match" not in ack.lower():
        bad("ack: RESULT CONTEXT_MATCH missing")
    if "unresolved_canonical_mismatches: 0" not in ack.lower():
        bad("ack: canonical mismatches != 0")
    if "open_product_owner_decisions: 3" not in ack.lower():
        bad("ack: open PO decisions != 3")
    if "production_executed_true_count=0" not in ack.lower().replace(" ", ""):
        bad("ack: production_executed_true_count=0 missing")


def check_decisions_carried() -> None:
    for tag in ("D-1", "D-2", "D-3"):
        for name, p in (("spec", SPEC), ("ack", ACK), ("gaps", GAPS)):
            if tag not in read(p):
                bad(f"{name}: {tag} not carried forward")
    spec = read(SPEC)
    if "product_owner_decision_required" not in spec.lower():
        bad("spec: PRODUCT_OWNER_DECISION_REQUIRED marker missing")
    if "decision_dependent" not in (read(GAPS).lower()):
        bad("gaps: DECISION_DEPENDENT classification missing")


def check_journey() -> None:
    spec = read(SPEC)
    for i, marker in enumerate(JOURNEY_MARKERS, start=1):
        if not contains(spec, marker):
            bad(f"spec: journey step {i} marker missing ('{marker}')")


def check_screens() -> None:
    spec = read(SPEC)
    for screen in REQUIRED_SCREENS:
        if not contains(spec, screen):
            bad(f"spec: required screen missing ('{screen}')")


def check_flows() -> None:
    spec = read(SPEC)
    # delivery + acceptance
    for term in ("delivery package", "final acceptance", "accepted_with_follow_up", "rejected"):
        if not contains(spec, term):
            bad(f"spec: delivery/acceptance term missing ('{term}')")
    # failure/recovery
    for term in ("dlq", "retry", "manual remediation", "abort", "partial delivery"):
        if not contains(spec, term):
            bad(f"spec: failure/recovery term missing ('{term}')")
    # status model + mapping gap
    if not contains(spec, "mapping_gap"):
        bad("spec: MAPPING_GAP not present in status mapping")


def check_privacy_exclusions() -> None:
    spec = read(SPEC)
    for term in MUST_NOT_DISPLAY:
        if not contains(spec, term):
            bad(f"spec: must-not-display exclusion missing ('{term}')")


def check_no_impl_claims() -> None:
    ack = read(ACK).lower()
    if "final visual design started:\nno" not in ack and "final visual design started: no" not in ack:
        # tolerate whitespace variants
        if "final visual design" not in ack or "no" not in ack.split("final visual design")[1][:40]:
            bad("ack: 'Final visual design started: NO' missing")
    if "frontend implementation authorized:\nno" not in ack and "frontend implementation authorized: no" not in ack:
        if "frontend implementation authorized" not in ack or "no" not in ack.split("frontend implementation authorized")[1][:40]:
            bad("ack: 'Frontend implementation authorized: NO' missing")


def check_secrets_paths() -> None:
    for p in (SPEC, ACK, GAPS, EVID):
        t = read(p)
        if SECRET_SHAPES.search(t):
            bad(f"{p}: possible secret shape")
        if ABS_PATH_SHAPES.search(t):
            bad(f"{p}: local absolute path committed")


def check_no_runtime_changed() -> None:
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "origin/main...HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        bad("git not available; cannot confirm scope")
        return
    if result.returncode != 0:
        bad("could not compute diff against origin/main")
        return
    for line in result.stdout.splitlines():
        path = line.strip().replace("\\", "/")
        if not path:
            continue
        for prefix in FORBIDDEN_RUNTIME_PREFIXES:
            if path.startswith(prefix):
                bad(f"forbidden/runtime path changed: {path}")


def main() -> int:
    check_exist()
    check_context()
    check_decisions_carried()
    check_journey()
    check_screens()
    check_flows()
    check_privacy_exclusions()
    check_no_impl_claims()
    check_secrets_paths()
    check_no_runtime_changed()

    if failures:
        print(f"{MARKER}: FAIL")
        return 1
    print("  [OK] canonical main c1db4cc; CC head 828ea90; Codex head 78aa4ee; Context ID matched;")
    print("       0 canonical mismatches; 3 open PO decisions; D-1/D-2/D-3 carried; 13/13 journey")
    print("       steps; 15/15 screens; delivery+acceptance + failure/recovery covered; private")
    print("       reasoning/secrets excluded; no frontend/runtime/deployment/action; prod_exec=0")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
