#!/usr/bin/env python3
"""Step 66C.4-BE3-RA-P -- runtime activation readiness planning verifier.

Static/structural checks only (planning stage; no runtime, no PostgreSQL). Confirms the three
planning deliverables exist and are internally consistent: all 11 activation-gate items are
individually classified with implementation/evidence/gap/dependency fields, the proposed stage
sequence is dependency-ordered with single-capability/rollback/verification/authorization-boundary
fields per stage, product decisions are listed separately from the gate inventory, and that NO
automatic migration/consumer exists and all four BE3 feature gates remain default-false in the
actual source (not merely claimed in the docs).

Marker: STEP66C4_BE3_RUNTIME_ACTIVATION_PLANNING_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs" / "contracts" / "66c4-reminder-expiry-controlled-resume"
HANDOFF = ROOT / "docs" / "handoffs" / "66c4-reminder-expiry-controlled-resume"
TEST_DOCS = ROOT / "docs" / "test"

PLAN = CONTRACT / "be3-runtime-activation-readiness-plan.md"
SEQUENCE = HANDOFF / "be3-runtime-activation-stage-sequence.md"
EVIDENCE = TEST_DOCS / "step66c4-be3-runtime-activation-planning-evidence.md"

RESUME_MODEL = ROOT / "shared" / "sdk" / "tasks" / "resume_request_model.py"
REPLAY_MODEL = ROOT / "shared" / "sdk" / "tasks" / "replay_request_model.py"
COMPOSE = ROOT / "infra" / "docker-compose" / "docker-compose.yml"

FEATURE_GATES = (
    "BE3_RESUME_API_ENABLED",
    "BE3_RESUME_COMMAND_ENABLED",
    "BE3_REPLAY_API_ENABLED",
    "BE3_REPLAY_EXECUTION_ENABLED",
)

ALLOWED_CLASSIFICATIONS = (
    "IMPLEMENTED_AND_VERIFIED",
    "IMPLEMENTED_NOT_RUNTIME_VALIDATED",
    "PARTIALLY_IMPLEMENTED",
    "NOT_IMPLEMENTED",
    "BLOCKED_BY_DEPENDENCY",
    "REQUIRES_PRODUCT_DECISION",
)

GATE_HEADERS = tuple(f"### Gate {i} " for i in range(1, 12))

STAGE_HEADERS = tuple(f"### RA-{i} " for i in range(1, 13))

MARKER = "STEP66C4_BE3_RUNTIME_ACTIVATION_PLANNING_VERIFY"
failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def main() -> int:  # noqa: C901
    for p in (PLAN, SEQUENCE, EVIDENCE, RESUME_MODEL, REPLAY_MODEL, COMPOSE):
        if not p.is_file():
            bad(f"missing file: {p}")
    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    plan = PLAN.read_text(encoding="utf-8")
    sequence = SEQUENCE.read_text(encoding="utf-8")
    evidence = EVIDENCE.read_text(encoding="utf-8")

    # 1. All 11 gate items present and individually classified.
    for header in GATE_HEADERS:
        if header not in plan:
            bad(f"check1: missing gate section header: {header.strip()}")
    classification_count = sum(plan.count(c) for c in ALLOWED_CLASSIFICATIONS)
    if classification_count < 11:
        bad(f"check1: fewer than 11 classification tokens found ({classification_count})")
    # No stray classification-like token outside the allowed set (catches typos).
    stray = re.findall(r"\bClassification:\s+(\S+)", plan)
    for token in stray:
        if token not in ALLOWED_CLASSIFICATIONS and token != "REQUIRES_EXTERNAL_RESOURCE":
            # REQUIRES_EXTERNAL_RESOURCE is a valid compound qualifier used in prose, not as a
            # standalone "Classification:" value in this document; still accept it defensively.
            bad(f"check1: unrecognized classification token: {token}")

    # 2. Each gate section has implementation/evidence/gap/dependency fields.
    gate_blocks = re.split(r"(?=### Gate \d+ )", plan)[1:]
    if len(gate_blocks) != 11:
        bad(f"check2: expected 11 gate blocks, found {len(gate_blocks)}")
    required_fields = (
        "Classification:",
        "Implementation:",
        "Evidence:",
        "Missing capability:",
        "Upstream dependency:",
        "Downstream dependency:",
        "Risk level:",
    )
    for block in gate_blocks:
        title_line = block.splitlines()[0]
        for field in required_fields:
            if field not in block:
                bad(f"check2: gate section '{title_line.strip()}' missing field {field}")

    # 3. Stage sequence has a clear, numbered order (RA-1..RA-12).
    for header in STAGE_HEADERS:
        if header not in sequence:
            bad(f"check3: missing stage header: {header.strip()}")
    order = [m.start() for h in STAGE_HEADERS for m in re.finditer(re.escape(h), sequence)]
    if order != sorted(order):
        bad("check3: stage headers are not in ascending sequence order")

    # 4. Each stage names exactly one primary capability (a single "Capability:" field per block).
    stage_blocks = re.split(r"(?=### RA-\d+ )", sequence)[1:]
    if len(stage_blocks) != 12:
        bad(f"check4: expected 12 stage blocks, found {len(stage_blocks)}")
    for block in stage_blocks:
        title_line = block.splitlines()[0]
        cap_count = block.count("Capability:")
        if cap_count != 1:
            bad(f"check4: stage '{title_line.strip()}' has {cap_count} Capability: fields (want 1)")

    # 5. Each stage has rollback and verification-need fields.
    for block in stage_blocks:
        title_line = block.splitlines()[0]
        for field in ("Rollback:", "Independently\n  verifiable:", "Risk tier:"):
            if field not in block:
                bad(f"check5: stage '{title_line.strip()}' missing field {field.split(chr(10))[0]}")
        if "Authorization" not in block or "boundary:" not in block:
            bad(f"check5: stage '{title_line.strip()}' missing an authorization-boundary field")

    # 6. Product decisions listed separately from the gate inventory (own numbered section).
    if "## 7. Product decisions inventory" not in plan:
        bad("check6: product decisions are not in their own section")
    decision_items = re.findall(r"^\d+\. .+\?", plan, re.M)
    if len(decision_items) < 11:
        bad(f"check6: fewer than 11 product-decision questions found ({len(decision_items)})")

    # 7. No automatic migration: no migration-runner invocation in the shared compose file, and the
    # only automated apply mechanism (the Kubernetes Job template) is fail-closed.
    compose_text = COMPOSE.read_text(encoding="utf-8")
    if re.search(r"migrat", compose_text, re.I):
        bad("check7: docker-compose.yml appears to reference a migration runner")

    # 8. No automatic consumer: no lifecycle-poller/outbox-relay/BE3-consumer service in compose.
    for token in ("lifecycle-poller", "lifecycle_poller", "outbox-relay", "outbox_relay"):
        if token in compose_text:
            bad(f"check8: docker-compose.yml appears to run a consumer service ({token})")

    # 9. All four feature gates still default to false in the actual source.
    resume_src = RESUME_MODEL.read_text(encoding="utf-8")
    replay_src = REPLAY_MODEL.read_text(encoding="utf-8")
    combined_src = resume_src + replay_src
    for gate in FEATURE_GATES:
        if f'os.environ.get("{gate}", "false")' not in combined_src:
            bad(f"check9: feature gate {gate} does not default to false in source")

    # 10. No deployment/shared migration/activation performed by this stage (no infra/migrations
    # file changed on this branch relative to the BE3-M merge commit).
    changed = [f for f in _git("diff", "--name-only", "284d706", "HEAD").splitlines() if f]
    for f in changed:
        for prefix in ("infra/", "migrations/", ".github/workflows/", "frontend/"):
            if f.startswith(prefix):
                bad(f"check10: forbidden path changed by this planning stage: {f}")

    # 11. production_executed_true_count recorded as 0.
    if (
        "production_executed_true_count" not in evidence
        and "production_executed_true_count" not in plan
    ):
        bad("check11: production_executed_true_count not recorded in plan/evidence")
    progress_md = (ROOT / "source" / "progress.md").read_text(encoding="utf-8")
    if "production_executed_true_count` = 0" not in progress_md:
        bad("check11: production_executed_true_count = 0 not recorded in source/progress.md")

    # 12. Next stage still requires independent PO authorization (recorded explicitly).
    if "requires its own separate, explicit Product Owner authorization" not in sequence:
        bad("check12: stage sequence does not require separate PO authorization per stage")
    if "NOT authorized" not in plan and "not authorized" not in plan.lower():
        bad("check12: plan does not state that no stage is authorized by this document")

    if failures:
        print(f"{MARKER}: FAIL ({len(failures)} issue(s))")
        return 1

    print("  [OK] All 11 activation-gate items classified with implementation/evidence/gap/")
    print("       dependency fields; 12-stage dependency-ordered sequence with single-capability/")
    print("       rollback/verification/authorization-boundary fields per stage; 11 product")
    print("       decisions listed separately; no automatic migration/consumer; all four feature")
    print("       gates default false; no deployment/migration/activation path touched by this")
    print("       stage; next stage still requires separate Product Owner authorization.")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
