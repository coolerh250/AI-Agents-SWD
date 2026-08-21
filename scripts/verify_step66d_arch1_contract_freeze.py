"""Deterministic verifier for Step 66D-ARCH1 delivery and acceptance contract freeze.

Offline and read-only. Starts no container, opens no database connection, contacts no Vault, OIDC
provider or Kubernetes API, reads no secret, and performs no network operation other than reading
local Git objects.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
import pathlib

# AT-M2 remediation: this stage's rejection window ends where an authorized successor
# milestone takes over. Without one this is HEAD, exactly as before.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
try:
    from successor_lifecycle import live_guard_changed_paths  # noqa: E402
except ModuleNotFoundError:  # isolated probe copies may not carry scripts/

    def live_guard_changed_paths(baseline: str) -> list[str]:
        """Strictest fallback: with no lifecycle module nothing is exempt."""
        current = "HEAD"
        return [
            line.strip().replace("\\", "/")
            for line in git("diff", "--name-only", baseline, current).splitlines()
            if line.strip()
        ]

MARKER = "STEP66D_ARCH1_CONTRACT_FREEZE_VERIFY: PASS"

ROOT = Path(__file__).resolve().parents[1]

CANONICAL_MAIN = "ccfee8ef47f72d5d67ea6bb58845018f306cfa0c"

# BOUNDED POST-MERGE CONTRACT-SCOPE FREEZE (Step 66D-ARCH1-M1). PR #25 is merged, so this
# stage is no longer an open branch: its positive scope is the frozen range below, and the
# registered path set is exact. The denylists in check34/check35 stay HEAD-relative on
# purpose -- they can only reject, never admit.
ARCH1_STAGE_HEAD = "ab19dad7a2e032e421927d71622bb22d6b9e3e36"
ARCH1_EXPECTED_PATHS = (
    "docs/architecture/66d-delivery-acceptance/step66d-arch1-api-event-audit-contracts.md",
    "docs/architecture/66d-delivery-acceptance/step66d-arch1-contract-freeze.md",
    "docs/architecture/66d-delivery-acceptance/step66d-arch1-domain-and-state-model.md",
    "docs/architecture/66d-delivery-acceptance/step66d-arch1-read-model-and-security-boundary.md",
    "docs/decisions/step66d-arch1-architecture-decisions.md",
    "docs/handoffs/66d-delivery-acceptance/step66d-arch1-existing-capability-inventory.md",
    "docs/handoffs/66d-delivery-acceptance/step66d-arch1-gap-and-implementation-slice-plan.md",
    "docs/test/step66d-arch1-contract-freeze-evidence.md",
    "scripts/verify_step66d_arch1_contract_freeze.py",
    "source/progress.md",
    "tests/test_step66d_arch1_contract_freeze.py",
)

ARCH = ROOT / "docs" / "architecture" / "66d-delivery-acceptance"
HANDOFFS = ROOT / "docs" / "handoffs" / "66d-delivery-acceptance"
CONTRACTS = ROOT / "docs" / "contracts" / "66d-delivery-acceptance"

FREEZE = ARCH / "step66d-arch1-contract-freeze.md"
DOMAIN = ARCH / "step66d-arch1-domain-and-state-model.md"
APIDOC = ARCH / "step66d-arch1-api-event-audit-contracts.md"
READMODEL = ARCH / "step66d-arch1-read-model-and-security-boundary.md"
ADRS = ROOT / "docs" / "decisions" / "step66d-arch1-architecture-decisions.md"
INVENTORY = HANDOFFS / "step66d-arch1-existing-capability-inventory.md"
SLICES = HANDOFFS / "step66d-arch1-gap-and-implementation-slice-plan.md"
EVIDENCE = ROOT / "docs" / "test" / "step66d-arch1-contract-freeze-evidence.md"
BINDING = CONTRACTS / "step66d-delivery-decision-model-binding-decisions.md"

REVIEW_ACTIONS = ("ACCEPT", "REJECT", "REQUEST_CHANGES", "RERUN_QA", "ESCALATE", "ARCHIVE")
FINAL_DECISIONS = ("ACCEPTED", "ACCEPTED_WITH_FOLLOW_UP", "REJECTED")
STATUSES = (
    "DRAFT",
    "SUBMITTED",
    "UNDER_REVIEW",
    "CHANGES_REQUESTED",
    "QA_RERUN_REQUESTED",
    "ACCEPTED",
    "REJECTED",
    "ARCHIVED",
    "EXPIRED",
)
ENTITIES = (
    "DeliverySubmission",
    "DeliveryReviewTask",
    "DeliveryReviewAction",
    "ProductOwnerDecision",
    "AcceptanceFollowUpItem",
)
FORBIDDEN_SOURCE_PREFIXES = (
    "apps/",
    "agents/",
    "services/",
    "shared/",
    "migrations/",
    "infra/",
)
ADVISORY_FILES = (
    "scripts/verify_step66sync1_claude_design_reconciliation.py",
    "scripts/verify_step66sync1_codex_frontend_reconciliation.py",
)

FAILURES: list[str] = []


def bad(message: str) -> None:
    FAILURES.append(message)


def git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False
    )
    return result.stdout.decode("utf-8").strip() if result.returncode == 0 else ""


def read(path: Path) -> str:
    if not path.is_file():
        bad(f"missing required file: {path.relative_to(ROOT).as_posix()}")
        return ""
    return path.read_text(encoding="utf-8")


def flat(text: str) -> str:
    return re.sub(r"\s+", " ", text)


def changed_paths() -> list[str]:
    return live_guard_changed_paths(CANONICAL_MAIN)


def check01_baseline() -> None:
    ok = subprocess.run(
        ["git", "merge-base", "--is-ancestor", CANONICAL_MAIN, "HEAD"], cwd=ROOT, check=False
    )
    if ok.returncode != 0:
        bad(f"check01: canonical main {CANONICAL_MAIN[:7]} is not an ancestor of HEAD")
    if CANONICAL_MAIN[:7] not in read(FREEZE):
        bad("check01: the contract freeze does not record its canonical baseline")


def check02_binding_decisions_honoured() -> None:
    freeze = read(FREEZE)
    for decision in ("66D-D01", "66D-D02", "66D-D03", "66D-D04"):
        if decision not in freeze:
            bad(f"check02: {decision} is not referenced by the contract freeze")
    if not BINDING.is_file():
        bad("check02: the canonical binding decision record is missing from main")


def check03_legacy_separated_from_new() -> None:
    freeze = read(FREEZE)
    if "DeliveryPackage" not in freeze or "DeliverySubmission" not in freeze:
        bad("check03: legacy and new aggregates are not both named")
    text = flat(freeze)
    if "legacy Platform Ops evidence object" not in text:
        bad("check03: the legacy object's role is not preserved")
    if "may **not** act as the human review aggregate" not in flat(read(FREEZE)):
        bad("check03: the legacy object is not excluded from being the review aggregate")


def check04_domain_entities_complete() -> None:
    domain = read(DOMAIN)
    for entity in ENTITIES:
        if entity not in domain:
            bad(f"check04: {entity} is missing from the domain model")
    for field in (
        "delivery_submission_id",
        "delivery_review_task_id",
        "submission_version",
        "supersedes_submission_id",
        "row_version",
        "requirements_baseline_id",
        "legacy_delivery_package_refs",
    ):
        if field not in domain:
            bad(f"check04: required field {field} is missing")


def check05_six_review_actions() -> None:
    block = re.search(
        r"### Review Gate Action \(exactly six\)\n\n```text\n(.*?)```", read(FREEZE), re.S
    )
    if not block:
        bad("check05: the Review Gate Action listing is missing")
        return
    found = tuple(line.strip() for line in block.group(1).splitlines() if line.strip())
    if found != REVIEW_ACTIONS:
        bad(f"check05: Review Gate Actions are {found}, expected exactly {REVIEW_ACTIONS}")


def check06_three_final_decisions() -> None:
    block = re.search(
        r"### Product Owner Final Decision \(exactly three\)\n\n```text\n(.*?)```",
        read(FREEZE),
        re.S,
    )
    if not block:
        bad("check06: the Product Owner Final Decision listing is missing")
        return
    found = tuple(line.strip() for line in block.group(1).splitlines() if line.strip())
    if found != FINAL_DECISIONS:
        bad(f"check06: final decisions are {found}, expected exactly {FINAL_DECISIONS}")


def check07_action_and_decision_separated() -> None:
    freeze = read(FREEZE)
    if freeze.count("| none |") != 4:
        bad(f"check07: expected exactly four no-decision actions, found {freeze.count('| none |')}")
    api = read(APIDOC)
    if "review_action.accept" not in api or "po_decision.accepted" not in api:
        bad("check07: review action and decision audit action names are not distinct")


def check08_accept_reject_transactional() -> None:
    text = flat(read(DOMAIN)) + " " + flat(read(APIDOC)) + " " + flat(read(ADRS))
    if "ONE transaction" not in text and "one transaction" not in text:
        bad("check08: ACCEPT/REJECT atomicity is not specified")
    if "ADR-66D-10" not in read(ADRS):
        bad("check08: ADR-66D-10 is missing")
    if "never be a persisted state where an `ACCEPT` action exists without" not in flat(
        read(DOMAIN)
    ):
        bad("check08: the no-orphan-ACCEPT guarantee is not stated")


def check09_follow_up_non_blocking_only() -> None:
    text = flat(read(DOMAIN))
    if "ACCEPTED_WITH_FOLLOW_UP accepts only blocking = false" not in text:
        bad("check09: ACCEPTED_WITH_FOLLOW_UP is not restricted to non-blocking follow-ups")


def check10_blocking_requires_changes() -> None:
    if "BLOCKING_FOLLOW_UP_REQUIRES_CHANGES" not in read(APIDOC):
        bad("check10: the blocking follow-up error code is missing")
    if "REQUEST_CHANGES" not in flat(read(DOMAIN)):
        bad("check10: blocking follow-ups do not route to REQUEST_CHANGES")


def check11_statuses_complete() -> None:
    block = re.search(
        r"### Canonical statuses \(exactly nine\)\n\n```text\n(.*?)```", read(DOMAIN), re.S
    )
    if not block:
        bad("check11: the canonical status listing is missing")
        return
    found = tuple(line.strip() for line in block.group(1).splitlines() if line.strip())
    if found != STATUSES:
        bad(f"check11: statuses are {found}, expected exactly {STATUSES}")


def check12_supersession_exists() -> None:
    domain = read(DOMAIN)
    if "supersedes_decision_id" not in domain:
        bad("check12: decision supersession is not modelled")
    if "### Superseded statement" not in domain:
        bad("check12: superseded decisions are not explicitly preserved")
    if "append-only" not in flat(domain).lower():
        bad("check12: the decision record is not declared append-only")


def check13_dual_anchor() -> None:
    freeze = flat(read(FREEZE))
    if "project_id -> work_item_id -> workflow_id -> run_id" not in freeze:
        bad("check13: the execution lineage is not specified")
    if "delivery_review_task_id" not in freeze:
        bad("check13: the human review anchor is not specified")


def check14_task_not_execution_source() -> None:
    if "Task is not the Agent execution source of truth" not in flat(read(FREEZE)):
        bad("check14: the Task execution-source boundary is not preserved")


def check15_requirement_traceability() -> None:
    domain = read(DOMAIN)
    for token in (
        "requirement_id",
        "acceptance_criterion_id",
        "work_item_id",
        "execution_id",
        "artifact_id",
        "qa_evidence_id",
        "delivery_item_id",
        "review_action_id",
        "decision_id",
    ):
        if token not in domain:
            bad(f"check15: traceability identifier {token} is missing")
    for result in ("PASS", "FAIL", "PARTIAL", "NOT_TESTED", "NOT_APPLICABLE"):
        if result not in domain:
            bad(f"check15: acceptance criterion result {result} is missing")
    if "Agent completion does not imply PASS" not in flat(domain):
        bad("check15: agent completion is not excluded from implying PASS")


def check16_provenance() -> None:
    domain = read(DOMAIN)
    for token in ("actor_type", "runtime_agent", "ai_partner", "generation_mode", "content_hash"):
        if token not in domain:
            bad(f"check16: provenance field {token} is missing")
    if "future_autonomous_runtime_generated" not in domain:
        bad("check16: the forbidden generation mode is not named")
    if "NOT PERMITTED IN THE FIRST POC" not in domain:
        bad("check16: the forbidden generation mode is not excluded from the first POC")
    if "never be described or recorded as `runtime_agent`" not in flat(domain):
        bad("check16: external AI partners are not distinguished from runtime agents")


def check17_api_contracts() -> None:
    api = read(APIDOC)
    for endpoint in (
        "/delivery-submissions",
        "/delivery-submissions/{submission_id}/submit",
        "/delivery-submissions/{submission_id}/review-actions",
        "/delivery-submissions/{submission_id}/po-decisions",
        "/product-owner-decisions/{decision_id}/follow-ups",
        "/acceptance-follow-ups/{follow_up_id}",
    ):
        if endpoint not in api:
            bad(f"check17: endpoint {endpoint} is missing")
    if "NOT IMPLEMENTED" not in api:
        bad("check17: the API contract does not state that it is unimplemented")


def check18_error_semantics() -> None:
    api = read(APIDOC)
    for code in (
        "409 DELIVERY_VERSION_CONFLICT",
        "409 FINAL_DECISION_ALREADY_EXISTS",
        "409 QA_RERUN_LIMIT_REACHED",
        "409 BLOCKING_FOLLOW_UP_REQUIRES_CHANGES",
        "422 ACCEPTANCE_CRITERIA_INCOMPLETE",
        "423 DELIVERY_REVIEW_BLOCKED",
    ):
        if code not in api:
            bad(f"check18: error code {code} is missing")


def check19_event_contracts() -> None:
    api = read(APIDOC)
    for event in (
        "delivery.submission.created",
        "delivery.review_action.recorded",
        "delivery.po_decision.recorded",
        "delivery.po_decision.superseded",
        "delivery.follow_up.created",
    ):
        if event not in api:
            bad(f"check19: event {event} is missing")
    for field in ("correlation_id", "causation_id", "schema_version", "audit_ref"):
        if field not in api:
            bad(f"check19: event envelope field {field} is missing")


def check20_audit_contract() -> None:
    api = read(APIDOC)
    if "production_executed" not in api:
        bad("check20: the audit contract does not record production_executed")
    if "before state" not in api or "after state" not in api:
        bad("check20: the audit contract does not record before/after state")


def check21_outbox_specified_not_built() -> None:
    text = read(APIDOC) + read(ADRS)
    if "transactional outbox" not in text.lower():
        bad("check21: the transactional outbox is not specified")
    if "ADR-66D-08" not in read(ADRS):
        bad("check21: ADR-66D-08 is missing")
    if "OUT OF SCOPE" not in read(APIDOC):
        bad("check21: outbox relay/consumers are not excluded from this stage")


def check22_read_model() -> None:
    rm = read(READMODEL)
    for token in ("read_model_id", "stale indicator", "EVENTUALLY CONSISTENT", "UNKNOWN"):
        if token not in rm:
            bad(f"check22: read model contract is missing {token}")


def check23_security_boundary() -> None:
    rm = flat(read(READMODEL))
    for token in ("private chain of thought", "Request-provided", "masked as 404"):
        if token not in rm:
            bad(f"check23: security boundary is missing {token}")


def check24_cost_contract() -> None:
    api = read(APIDOC)
    for token in ("estimated_cost", "actual_cost", "authorized_limit", "limit_breach"):
        if token not in api:
            bad(f"check24: cost contract is missing {token}")
    if "production_executed_true_count MUST remain 0" not in api:
        bad("check24: the production execution count is not pinned to zero")


def check25_failure_contract() -> None:
    api = read(APIDOC)
    for token in ("artifact missing", "QA rerun limit reached", "identity not verified"):
        if token not in api:
            bad(f"check25: failure/recovery contract is missing {token}")
    if "MUST NOT automatically restart an Agent workflow" not in api:
        bad("check25: rejection must not auto-restart a workflow -- rule missing")


def check26_qa_rerun_limit() -> None:
    freeze = flat(read(FREEZE))
    adrs = read(ADRS)
    if "1 RERUN_QA action per submission version" not in freeze:
        bad("check26: the bounded QA rerun limit is not stated as one per submission version")
    if "ADR-66D-09" not in adrs:
        bad("check26: ADR-66D-09 is missing")
    if "One bounded QA rerun per DeliverySubmission version" not in adrs:
        bad("check26: ADR-66D-09 does not state the bound")


def check27_second_rerun_rejected() -> None:
    if "409 QA_RERUN_LIMIT_REACHED" not in read(APIDOC):
        bad("check27: the second-rerun error code is not defined")
    if "QA_RERUN_LIMIT_REACHED" not in read(FREEZE):
        bad("check27: the contract freeze does not name the rerun limit error")


def check28_ia_still_open() -> None:
    rm = read(READMODEL)
    if "STILL OPEN" not in rm:
        bad("check28: the POC Control Center IA option is not left open")
    if "Unified Control Center" not in rm or "Coordinated Existing Routes" not in rm:
        bad("check28: the two IA options are not both named as unselected")


def check29_slices_unauthorized() -> None:
    slices = read(SLICES)
    count = slices.count("Authorization status   NOT AUTHORIZED")
    if count < 8:
        bad(f"check29: only {count} slices are marked NOT AUTHORIZED, expected at least 8")
    if "Authorized: 0 of 14" not in slices:
        bad("check29: the gap register does not record zero authorized gaps")


def check30_to_32_stages_unauthorized() -> None:
    freeze = read(FREEZE)
    for number, stage in (
        ("check30", "STEP66D_DESIGN"),
        ("check31", "STEP67POC0"),
        ("check32", "RA2I0"),
    ):
        if not re.search(rf"{stage}:\s+NOT STARTED / NOT AUTHORIZED", freeze):
            bad(f"{number}: {stage} is not marked NOT STARTED / NOT AUTHORIZED")


def check33_be3_gates_default_false() -> None:
    for name in ("resume_request_model.py", "replay_request_model.py"):
        path = ROOT / "shared" / "sdk" / "tasks" / name
        if not path.is_file():
            bad(f"check33: gate file missing: {name}")
            continue
        if path.read_text(encoding="utf-8").count('"false"') < 2:
            bad(f"check33: {name} no longer defaults its gates to false")


def check34_advisory_files_untouched() -> None:
    changed = changed_paths()
    for rel in ADVISORY_FILES:
        if rel in changed:
            bad(f"check34: advisory file {rel} was modified; it is out of scope for this stage")


def check35_no_implementation_change() -> None:
    changed = changed_paths()
    offenders = [p for p in changed if p.startswith(FORBIDDEN_SOURCE_PREFIXES)]
    if offenders:
        bad(f"check35: runtime/source paths changed: {', '.join(sorted(offenders))}")
    infra = [
        p
        for p in changed
        if p.endswith((".yaml", ".yml", ".tsx", ".jsx", ".vue", ".sql", ".css", ".scss"))
        or "docker-compose" in p
        or p.startswith(("helm/", "k8s/", "charts/"))
    ]
    if infra:
        bad(f"check35: frontend/infra/migration paths changed: {', '.join(sorted(infra))}")


def check37_positive_scope_frozen() -> None:
    """The stage scope is the frozen range, compared for exact equality."""
    actual = tuple(
        sorted(
            line
            for line in git("diff", "--name-only", CANONICAL_MAIN, ARCH1_STAGE_HEAD).splitlines()
            if line.strip()
        )
    )
    unexpected = sorted(set(actual) - set(ARCH1_EXPECTED_PATHS))
    missing = sorted(set(ARCH1_EXPECTED_PATHS) - set(actual))
    if unexpected:
        bad(f"check37: unregistered path in the frozen ARCH1 range: {', '.join(unexpected)}")
    if missing:
        bad(f"check37: registered path missing from the frozen range: {', '.join(missing)}")
    if len(actual) != 11:
        bad(f"check37: the frozen ARCH1 range holds {len(actual)} paths, expected 11")


def check36_production_count_zero() -> None:
    for path in (FREEZE, DOMAIN, APIDOC, READMODEL, ADRS, INVENTORY, SLICES):
        body = read(path)
        if "production_executed_true_count" not in body:
            bad(f"check36: {path.name} does not record production_executed_true_count")
    if "production_executed_true_count: 0" not in read(FREEZE):
        bad("check36: the contract freeze does not pin the production count to zero")


def main() -> int:
    check01_baseline()
    check02_binding_decisions_honoured()
    check03_legacy_separated_from_new()
    check04_domain_entities_complete()
    check05_six_review_actions()
    check06_three_final_decisions()
    check07_action_and_decision_separated()
    check08_accept_reject_transactional()
    check09_follow_up_non_blocking_only()
    check10_blocking_requires_changes()
    check11_statuses_complete()
    check12_supersession_exists()
    check13_dual_anchor()
    check14_task_not_execution_source()
    check15_requirement_traceability()
    check16_provenance()
    check17_api_contracts()
    check18_error_semantics()
    check19_event_contracts()
    check20_audit_contract()
    check21_outbox_specified_not_built()
    check22_read_model()
    check23_security_boundary()
    check24_cost_contract()
    check25_failure_contract()
    check26_qa_rerun_limit()
    check27_second_rerun_rejected()
    check28_ia_still_open()
    check29_slices_unauthorized()
    check30_to_32_stages_unauthorized()
    check33_be3_gates_default_false()
    check34_advisory_files_untouched()
    check35_no_implementation_change()
    check36_production_count_zero()
    check37_positive_scope_frozen()

    if FAILURES:
        for failure in dict.fromkeys(FAILURES):
            print(f"VERIFY FAILED: {failure}", file=sys.stderr)
        return 1
    print(MARKER)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
