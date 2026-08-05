"""Deterministic verifier for Step 66D-ARCH1-M1 canonical merge.

Offline and read-only. Starts no container, opens no database connection, contacts no Vault, OIDC
provider or Kubernetes API, reads no secret, and performs no network operation other than reading
local Git objects.

Every count below is DERIVED from the merged artifacts, never trusted from a stated figure.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

MARKER = "STEP66D_ARCH1_M1_CANONICAL_MERGE_VERIFY: PASS"

ROOT = Path(__file__).resolve().parents[1]

PRE_MERGE_MAIN = "ccfee8ef47f72d5d67ea6bb58845018f306cfa0c"
ARCH1_COMMIT = "ab19dad7a2e032e421927d71622bb22d6b9e3e36"
MERGE_COMMIT = "d411da52b240bef361a4af8588e6bb156a53ef40"

ARCH = ROOT / "docs" / "architecture" / "66d-delivery-acceptance"
HANDOFFS = ROOT / "docs" / "handoffs" / "66d-delivery-acceptance"

FREEZE = ARCH / "step66d-arch1-contract-freeze.md"
DOMAIN = ARCH / "step66d-arch1-domain-and-state-model.md"
APIDOC = ARCH / "step66d-arch1-api-event-audit-contracts.md"
READMODEL = ARCH / "step66d-arch1-read-model-and-security-boundary.md"
ADRS = ROOT / "docs" / "decisions" / "step66d-arch1-architecture-decisions.md"
SLICES = HANDOFFS / "step66d-arch1-gap-and-implementation-slice-plan.md"
RECORD = HANDOFFS / "step66d-arch1-m1-canonical-merge-record.md"
ARCH1_VERIFIER = ROOT / "scripts" / "verify_step66d_arch1_contract_freeze.py"

REVIEW_ACTIONS = ("ACCEPT", "REJECT", "REQUEST_CHANGES", "RERUN_QA", "ESCALATE", "ARCHIVE")
FINAL_DECISIONS = ("ACCEPTED", "ACCEPTED_WITH_FOLLOW_UP", "REJECTED")
ENTITIES = (
    "DeliverySubmission",
    "DeliveryReviewTask",
    "DeliveryReviewAction",
    "ProductOwnerDecision",
    "AcceptanceFollowUpItem",
)
RUNTIME_PREFIXES = ("apps/", "agents/", "services/", "shared/", "migrations/", "infra/")
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


def is_ancestor(commit: str, of: str) -> bool:
    return (
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", commit, of], cwd=ROOT, check=False
        ).returncode
        == 0
    )


def read(path: Path) -> str:
    if not path.is_file():
        bad(f"missing required file: {path.relative_to(ROOT).as_posix()}")
        return ""
    return path.read_text(encoding="utf-8")


def flat(text: str) -> str:
    return re.sub(r"\s+", " ", text)


def enum(doc: str, heading: str) -> tuple[str, ...]:
    match = re.search(rf"{heading}\n\n```text\n(.*?)```", doc, re.S)
    if not match:
        return ()
    return tuple(line.strip() for line in match.group(1).splitlines() if line.strip())


def frozen_paths() -> list[str]:
    return [p for p in git("diff", "--name-only", PRE_MERGE_MAIN, ARCH1_COMMIT).splitlines() if p]


def check01_pre_merge_main() -> None:
    if git("rev-parse", f"{PRE_MERGE_MAIN}^{{commit}}") != PRE_MERGE_MAIN:
        bad("check01: pre-merge main does not resolve")
    if not is_ancestor(PRE_MERGE_MAIN, "HEAD"):
        bad("check01: pre-merge main is not an ancestor of HEAD")


def check02_pr_head() -> None:
    if git("rev-parse", f"{ARCH1_COMMIT}^{{commit}}") != ARCH1_COMMIT:
        bad("check02: the ARCH1 commit does not resolve")


def check03_single_commit() -> None:
    count = git("rev-list", "--count", f"{PRE_MERGE_MAIN}..{ARCH1_COMMIT}")
    if count != "1":
        bad(f"check03: the merged branch carried {count} commits, expected exactly 1")


def check04_non_squash_two_parent() -> None:
    parents = git("show", "--no-patch", "--format=%P", MERGE_COMMIT).split()
    if len(parents) != 2:
        bad(f"check04: merge commit has {len(parents)} parent(s); a non-squash merge has 2")


def check05_merge_parents_exact() -> None:
    parents = git("show", "--no-patch", "--format=%P", MERGE_COMMIT).split()
    if parents != [PRE_MERGE_MAIN, ARCH1_COMMIT]:
        bad(f"check05: merge parents are {parents}")


def check06_arch1_commit_preserved() -> None:
    if not is_ancestor(ARCH1_COMMIT, "HEAD"):
        bad("check06: the ARCH1 commit is not preserved in main history")


def check07_positive_scope_frozen() -> None:
    body = read(ARCH1_VERIFIER)
    if f'ARCH1_STAGE_HEAD = "{ARCH1_COMMIT}"' not in body:
        bad("check07: the ARCH1 verifier does not pin its post-merge stage head")
    if '"--name-only", CANONICAL_MAIN, ARCH1_STAGE_HEAD' not in body:
        bad("check07: the ARCH1 positive scope is not evaluated over the frozen range")


def check08_exact_eleven_paths() -> None:
    actual = frozen_paths()
    if len(actual) != 11:
        bad(f"check08: the frozen ARCH1 range holds {len(actual)} paths, expected 11")
    body = read(ARCH1_VERIFIER)
    match = re.search(r"(?m)^ARCH1_EXPECTED_PATHS\s*=\s*\((.*?)^\)", body, re.DOTALL)
    if not match:
        bad("check08: the ARCH1 verifier has no registered path set")
        return
    registered = sorted(re.findall(r'"([^"]+)"', match.group(1)))
    if registered != sorted(actual):
        bad("check08: the registered ARCH1 path set does not equal its frozen range")


def check09_positive_scope_not_head() -> None:
    body = read(ARCH1_VERIFIER)
    for offender in re.findall(r'diff", "--name-only", [^)]*"HEAD"', body):
        bad(f"check09: the ARCH1 verifier resolves a scope against HEAD: {offender}")


def check10_binding_decisions() -> None:
    freeze = read(FREEZE)
    for decision in ("66D-D01", "66D-D02", "66D-D03", "66D-D04"):
        if decision not in freeze:
            bad(f"check10: {decision} is not referenced by the merged contract freeze")
    record = read(RECORD)
    for decision in ("66D-D01", "66D-D02", "66D-D03", "66D-D04"):
        if not re.search(rf"{decision}:\s+BINDING / CANONICALIZED", record):
            bad(f"check10: {decision} is not recorded as binding and canonicalized")


def check11_domain_entities() -> None:
    domain = read(DOMAIN)
    for entity in ENTITIES:
        if entity not in domain:
            bad(f"check11: {entity} is missing from the merged domain model")


def check12_legacy_separated() -> None:
    freeze = read(FREEZE)
    if "may **not** act as the human review aggregate" not in freeze:
        bad("check12: the legacy object is no longer excluded from being the review aggregate")
    changed = frozen_paths()
    if [p for p in changed if "delivery_package" in p.lower()]:
        bad("check12: legacy DeliveryPackage source was modified by the merged branch")


def check13_six_review_actions() -> None:
    found = enum(read(FREEZE), r"### Review Gate Action \(exactly six\)")
    if found != REVIEW_ACTIONS:
        bad(f"check13: Review Gate Actions are {found}")


def check14_three_final_decisions() -> None:
    found = enum(read(FREEZE), r"### Product Owner Final Decision \(exactly three\)")
    if found != FINAL_DECISIONS:
        bad(f"check14: Product Owner Final Decisions are {found}")


def check15_enums_disjoint() -> None:
    freeze = read(FREEZE)
    actions = set(enum(freeze, r"### Review Gate Action \(exactly six\)"))
    decisions = set(enum(freeze, r"### Product Owner Final Decision \(exactly three\)"))
    if actions & decisions:
        bad(f"check15: the two enums overlap on {sorted(actions & decisions)}")
    if freeze.count("| none |") != 4:
        bad("check15: the four no-decision actions are no longer exactly four")


def check16_decision_immutable_supersedable() -> None:
    domain = flat(read(DOMAIN))
    if "never updated in place" not in domain.lower():
        bad("check16: the decision record is no longer append-only")
    if "supersedes_decision_id" not in domain:
        bad("check16: decision supersession is missing")
    if "Superseded statement" not in domain:
        bad("check16: superseded decisions are no longer explicitly preserved")


def check17_accept_reject_atomic() -> None:
    if "never be a persisted state where an `ACCEPT` action exists without" not in flat(
        read(DOMAIN)
    ):
        bad("check17: the no-orphan-ACCEPT guarantee is missing")
    if "ADR-66D-10" not in read(ADRS):
        bad("check17: ADR-66D-10 is missing")


def check18_blocking_follow_up_rejected() -> None:
    if "accepts only blocking = false" not in flat(read(DOMAIN)):
        bad("check18: ACCEPTED_WITH_FOLLOW_UP is no longer restricted to non-blocking follow-ups")
    if "BLOCKING_FOLLOW_UP_REQUIRES_CHANGES" not in read(APIDOC):
        bad("check18: the blocking follow-up error code is missing")


def check19_qa_rerun_limit_one() -> None:
    if "1 RERUN_QA action per submission version" not in flat(read(FREEZE)):
        bad("check19: the QA rerun limit is no longer one per submission version")
    if "One bounded QA rerun per DeliverySubmission version" not in read(ADRS):
        bad("check19: ADR-66D-09 no longer states the bound")


def check20_second_rerun_error() -> None:
    if "409 QA_RERUN_LIMIT_REACHED" not in read(APIDOC):
        bad("check20: the second-rerun error code is missing")


def check21_contracts_not_implemented() -> None:
    api = read(APIDOC)
    if "NOT IMPLEMENTED" not in api:
        bad("check21: the API contract no longer states that it is unimplemented")
    if "no producer" not in flat(api).lower() and "producer candidate" not in api:
        bad("check21: the event contract no longer states that no producer exists")


def check22_outbox_specified_not_activated() -> None:
    api = read(APIDOC)
    if "transactional outbox" not in api.lower():
        bad("check22: the transactional outbox is no longer specified")
    if "OUT OF SCOPE" not in api:
        bad("check22: outbox relay/consumers are no longer excluded")


def check23_ia_unresolved() -> None:
    rm = read(READMODEL)
    if "STILL OPEN" not in rm:
        bad("check23: the POC Control Center IA is no longer left open")
    if "Unified Control Center" not in rm or "Coordinated Existing Routes" not in rm:
        bad("check23: the two IA options are no longer both named")
    if "UNRESOLVED" not in read(RECORD):
        bad("check23: the merge record does not carry the IA as unresolved")


def check24_legacy_migration_deferred() -> None:
    if "DEFERRED" not in read(RECORD):
        bad("check24: the merge record does not record legacy migration as deferred")


def check25_design_not_started() -> None:
    record = read(RECORD)
    if "READY FOR SEPARATE PRODUCT OWNER AUTHORIZATION" not in record:
        bad("check25: Step 66D-DESIGN readiness is not recorded")
    if "not started" not in flat(record).lower():
        bad("check25: Step 66D-DESIGN is not recorded as unstarted")


def check26_slices_unauthorized() -> None:
    slices = read(SLICES)
    if slices.count("Authorization status   NOT AUTHORIZED") < 8:
        bad("check26: not all eight implementation slices are marked NOT AUTHORIZED")
    if "0 of 8 authorized" not in read(RECORD):
        bad("check26: the merge record does not record zero authorized slices")


def check27_task_roles_untouched() -> None:
    changed = frozen_paths()
    for rel in ("shared/sdk/tasks/rbac.py", "shared/sdk/tasks/authorization_policy.py"):
        if rel in changed:
            bad(f"check27: TASK_ROLES implementation {rel} was modified")


def check28_no_implementation_change() -> None:
    changed = frozen_paths()
    offenders = [p for p in changed if p.startswith(RUNTIME_PREFIXES)]
    if offenders:
        bad(f"check28: runtime/source paths changed: {', '.join(sorted(offenders))}")
    infra = [
        p
        for p in changed
        if p.endswith((".yaml", ".yml", ".tsx", ".jsx", ".vue", ".sql", ".css", ".scss"))
        or "docker-compose" in p
        or p.startswith(("helm/", "k8s/", "charts/"))
    ]
    if infra:
        bad(f"check28: frontend/infra/migration paths changed: {', '.join(sorted(infra))}")


def check29_advisory_files_untouched() -> None:
    changed = [p for p in git("diff", "--name-only", MERGE_COMMIT).splitlines() if p]
    for rel in ADVISORY_FILES:
        if rel in changed or rel in frozen_paths():
            bad(f"check29: advisory file {rel} was modified")


def check30_be3_gates_default_false() -> None:
    for name in ("resume_request_model.py", "replay_request_model.py"):
        path = ROOT / "shared" / "sdk" / "tasks" / name
        if not path.is_file():
            bad(f"check30: gate file missing: {name}")
            continue
        if path.read_text(encoding="utf-8").count('"false"') < 2:
            bad(f"check30: {name} no longer defaults its gates to false")


def check31_production_count_zero() -> None:
    if "production_executed_true_count:  0" not in read(RECORD).replace("\t", " "):
        if "production_executed_true_count" not in read(RECORD):
            bad("check31: the merge record does not record production_executed_true_count")


def check32_derived_counts_recorded() -> None:
    """The three corrected counts must be derived from the artifacts, not restated."""
    api = read(APIDOC)
    endpoints = len(re.findall(r"^\| (?:GET|POST|PATCH|PUT|DELETE) \| `[^`]+` \|", api, re.M))
    events_block = re.search(r"## 3\. Durable event contracts.*?```text\n(.*?)```", api, re.S)
    events = (
        len([x for x in events_block.group(1).splitlines() if x.strip()]) if events_block else 0
    )
    errors_block = re.search(r"## 2\. Error semantics\n\n```text\n(.*?)```", api, re.S)
    errors = (
        len([x for x in errors_block.group(1).splitlines() if x.strip()]) if errors_block else 0
    )
    if endpoints != 17:
        bad(f"check32: derived endpoint count is {endpoints}, expected 17")
    if events != 20:
        bad(f"check32: derived event count is {events}, expected 20")
    if errors != 18:
        bad(f"check32: derived error-code count is {errors}, expected 18")
    record = read(RECORD)
    for value in ("17", "20", "18"):
        if value not in record:
            bad(f"check32: the merge record does not carry the corrected count {value}")


def main() -> int:
    check01_pre_merge_main()
    check02_pr_head()
    check03_single_commit()
    check04_non_squash_two_parent()
    check05_merge_parents_exact()
    check06_arch1_commit_preserved()
    check07_positive_scope_frozen()
    check08_exact_eleven_paths()
    check09_positive_scope_not_head()
    check10_binding_decisions()
    check11_domain_entities()
    check12_legacy_separated()
    check13_six_review_actions()
    check14_three_final_decisions()
    check15_enums_disjoint()
    check16_decision_immutable_supersedable()
    check17_accept_reject_atomic()
    check18_blocking_follow_up_rejected()
    check19_qa_rerun_limit_one()
    check20_second_rerun_error()
    check21_contracts_not_implemented()
    check22_outbox_specified_not_activated()
    check23_ia_unresolved()
    check24_legacy_migration_deferred()
    check25_design_not_started()
    check26_slices_unauthorized()
    check27_task_roles_untouched()
    check28_no_implementation_change()
    check29_advisory_files_untouched()
    check30_be3_gates_default_false()
    check31_production_count_zero()
    check32_derived_counts_recorded()

    if FAILURES:
        for failure in dict.fromkeys(FAILURES):
            print(f"VERIFY FAILED: {failure}", file=sys.stderr)
        return 1
    print(MARKER)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
