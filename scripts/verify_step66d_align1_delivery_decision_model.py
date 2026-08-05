"""Deterministic verifier for Step 66D-ALIGN1 delivery decision model alignment.

Offline and read-only. Starts no container, opens no database connection, contacts no Vault, OIDC
provider or Kubernetes API, reads no secret, and performs no network operation other than reading
local Git objects.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

MARKER = "STEP66D_ALIGN1_DELIVERY_DECISION_MODEL_VERIFY: PASS"

ROOT = Path(__file__).resolve().parents[1]

CANONICAL_MAIN = "64467fefc9a9ec303f9ddf4c0ce6d46486504d71"

# BOUNDED POST-MERGE SCOPE FREEZE (Step 66D-ALIGN1-M1). PR #24 is merged, so this stage
# is no longer an open branch: its positive scope becomes the frozen range below. The
# runtime denylists in this file stay HEAD-relative on purpose -- they can only reject.
ALIGN1_STAGE_HEAD = "6a8a7bfa2ae758e944b1126881a69fef2d122dcb"

# Step 66D-ALIGN1-RM1 (fixes R1-F01/F02/F03). Before this, the only scope control here was a
# runtime denylist, so any unregistered docs/, verify_step66* or test_step66* file passed. The
# registered set below is compared for EXACT equality against what the branch actually changed:
# an unregistered path fails, and a registered path that vanished fails too. While the PR is
# open the comparison runs against the working branch; the post-merge fixed boundary is the
# future authorized merge-record stage's responsibility, not this stage's.
ALIGN1_EXPECTED_PATHS = (
    "docs/alignment/66-project-completion/master/canonical-milestone-manifest.md",
    "docs/alignment/66-project-completion/master/canonical-source-of-truth-precedence.md",
    "docs/alignment/66-project-completion/master/product-and-technical-gates.md",
    "docs/alignment/66-project-completion/master/project-completion-master-plan.md",
    "docs/alignment/66-project-completion/master/project-definition-of-done.md",
    "docs/contracts/66d-delivery-acceptance/step66d-canonical-terminology-registry.md",
    "docs/contracts/66d-delivery-acceptance/step66d-delivery-decision-model-binding-decisions.md",
    "docs/design/ai-agent-team-functional-poc-control-center-spec.md",
    "docs/handoffs/66d-delivery-acceptance/step66d-align1-gap-register.md",
    "docs/handoffs/66d-delivery-acceptance/step66d-align1-rm1-stage-boundary-manifest.md",
    "docs/handoffs/66d-delivery-acceptance/step66d-arch1-retry-readiness.md",
    "docs/handoffs/66d-delivery-acceptance/step66d-canonical-conflict-supersession-matrix.md",
    "docs/handoffs/program-sync/step66sync1-canonicalization-manifest.md",
    "docs/handoffs/program-sync/step66sync1-claude-design-ux-gap-register.md",
    "docs/handoffs/program-sync/step66sync1-poc0-consolidated-gap-register.md",
    "docs/test/step66d-align1-canonical-alignment-evidence.md",
    "docs/test/step66d-align1-rm1-verifier-remediation-evidence.md",
    "scripts/verify_step66c4_be3_ra2m2_canonical_merge.py",
    "scripts/verify_step66c4_be3_ra2m_canonicalization.py",
    "scripts/verify_step66d_align1_delivery_decision_model.py",
    "scripts/verify_step66d_align1_rm1_fixed_range_remediation.py",
    "scripts/verify_step66sync1_claude_code_reconciliation.py",
    "scripts/verify_step66sync1_final_partner_reconciliation.py",
    "scripts/verify_step66sync1_m1_canonicalization.py",
    "scripts/verify_step66sync1_m2_canonical_merge.py",
    "source/progress.md",
    "tests/test_step66c4_be3_ra2m2_canonical_merge.py",
    "tests/test_step66c4_be3_ra2m_canonicalization.py",
    "tests/test_step66d_align1_delivery_decision_model.py",
    "tests/test_step66d_align1_rm1_fixed_range_remediation.py",
    "tests/test_step66sync1_claude_code_reconciliation.py",
    "tests/test_step66sync1_final_partner_reconciliation.py",
    "tests/test_step66sync1_m1_canonicalization.py",
    "tests/test_step66sync1_m2_canonical_merge.py",
)

CONTRACTS = ROOT / "docs" / "contracts" / "66d-delivery-acceptance"
HANDOFFS = ROOT / "docs" / "handoffs" / "66d-delivery-acceptance"
MASTER = ROOT / "docs" / "alignment" / "66-project-completion" / "master"
SYNC = ROOT / "docs" / "handoffs" / "program-sync"

BINDING = CONTRACTS / "step66d-delivery-decision-model-binding-decisions.md"
TERMS = CONTRACTS / "step66d-canonical-terminology-registry.md"
MATRIX = HANDOFFS / "step66d-canonical-conflict-supersession-matrix.md"
GAPS = HANDOFFS / "step66d-align1-gap-register.md"
RETRY = HANDOFFS / "step66d-arch1-retry-readiness.md"
EVIDENCE = ROOT / "docs" / "test" / "step66d-align1-canonical-alignment-evidence.md"

GATES = MASTER / "product-and-technical-gates.md"
DOD = MASTER / "project-definition-of-done.md"
MANIFEST = MASTER / "canonical-milestone-manifest.md"
PLAN = MASTER / "project-completion-master-plan.md"
PRECEDENCE = MASTER / "canonical-source-of-truth-precedence.md"

DESIGN_SPEC = ROOT / "docs" / "design" / "ai-agent-team-functional-poc-control-center-spec.md"
UX_GAPS = SYNC / "step66sync1-claude-design-ux-gap-register.md"
POC0_GAPS = SYNC / "step66sync1-poc0-consolidated-gap-register.md"

RESUME_MODEL = ROOT / "shared" / "sdk" / "tasks" / "resume_request_model.py"
REPLAY_MODEL = ROOT / "shared" / "sdk" / "tasks" / "replay_request_model.py"

FORBIDDEN_SOURCE_PREFIXES = (
    "apps/",
    "agents/",
    "shared/",
    "services/",
    "migrations/",
    "infra/",
)

REVIEW_ACTIONS = ("ACCEPT", "REJECT", "REQUEST_CHANGES", "RERUN_QA", "ESCALATE", "ARCHIVE")
FINAL_DECISIONS = ("ACCEPTED", "ACCEPTED_WITH_FOLLOW_UP", "REJECTED")
DECISIONS = ("66D-D01", "66D-D02", "66D-D03", "66D-D04")
CONFLICTS = ("66D-CONFLICT-01", "66D-CONFLICT-02", "66D-CONFLICT-03", "66D-CONFLICT-04")
ANNOTATED = (DESIGN_SPEC, UX_GAPS, POC0_GAPS)
ANNOTATION_MARKER = "<!-- SUPERSESSION-NOTE-BEGIN: Step 66D-ALIGN1 -->"

FAILURES: list[str] = []


def bad(message: str) -> None:
    FAILURES.append(message)


def git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def read(path: Path) -> str:
    if not path.is_file():
        bad(f"missing required file: {path.relative_to(ROOT).as_posix()}")
        return ""
    return path.read_text(encoding="utf-8")


def _section(text: str, heading: str) -> str:
    match = re.search(rf"^## {re.escape(heading)}.*?(?=^## |\Z)", text, re.MULTILINE | re.DOTALL)
    return match.group(0) if match else ""


def check01_baseline_main() -> None:
    reachable = subprocess.run(
        ["git", "merge-base", "--is-ancestor", CANONICAL_MAIN, "HEAD"], cwd=ROOT, check=False
    )
    if reachable.returncode != 0:
        bad("check01: canonical baseline 64467fe is not an ancestor of HEAD")
    if git("cat-file", "-t", CANONICAL_MAIN) != "commit":
        bad("check01: canonical baseline 64467fe is not a reachable commit")


def check02_all_decisions_present() -> None:
    binding = read(BINDING)
    for decision in DECISIONS:
        if decision not in binding:
            bad(f"check02: {decision} is missing from the binding decision record")


def check03_all_decisions_binding() -> None:
    binding = read(BINDING)
    for decision in DECISIONS:
        if not re.search(rf"^{decision}:\n\s*RESOLVED / BINDING$", binding, re.MULTILINE):
            bad(f"check03: {decision} is not recorded RESOLVED / BINDING")
    if "DECISION_AUTHORITY:\nProduct Owner" not in binding:
        bad("check03: decision authority is not recorded as Product Owner")


def check04_six_review_actions() -> None:
    block = _section(read(BINDING), "66D-D01 — Layered review and final-decision model")
    listing = re.search(r"### Review Gate Action \(exactly six\)\n\n```text\n(.*?)```", block, re.S)
    if listing is None:
        bad("check04: the six Review Gate Actions block was not found")
        return
    found = tuple(line.strip() for line in listing.group(1).splitlines() if line.strip())
    if found != REVIEW_ACTIONS:
        bad(f"check04: Review Gate Actions are {found}, expected exactly {REVIEW_ACTIONS}")


def check05_three_final_decisions() -> None:
    block = _section(read(BINDING), "66D-D01 — Layered review and final-decision model")
    listing = re.search(
        r"### Product Owner Final Decision \(exactly three\)\n\n```text\n(.*?)```", block, re.S
    )
    if listing is None:
        bad("check05: the three Product Owner Final Decisions block was not found")
        return
    found = tuple(line.strip() for line in listing.group(1).splitlines() if line.strip())
    if found != FINAL_DECISIONS:
        bad(f"check05: Final Decisions are {found}, expected exactly {FINAL_DECISIONS}")


def check06_enums_separated() -> None:
    binding = read(BINDING)
    if "Review Gate Action != Product Owner Final Decision." not in binding:
        bad("check06: the two contracts are not explicitly declared distinct")
    for requirement, label in (
        ("D01-R2", "different enums"),
        ("D01-R3", "different schemas"),
        ("D01-R4", "different command / API semantics"),
        ("D01-R5", "different durable events"),
        ("D01-R6", "different audit actions"),
        ("D01-R7", "different authorization boundaries"),
    ):
        if requirement not in binding:
            bad(f"check06: {requirement} ({label}) is missing")


def check07_request_changes_and_rerun_are_not_decisions() -> None:
    binding = read(BINDING)
    if "D01-R8" not in binding:
        bad("check07: D01-R8 is missing")
    flat = re.sub(r"\s+", " ", binding)
    needle = (
        "REQUEST_CHANGES, RERUN_QA, ESCALATE and ARCHIVE must never be added to the Product Owner "
        "Final Decision enum."
    )
    if needle not in flat:
        bad("check07: the record does not forbid review actions in the final-decision enum")
    decisions_block = re.search(
        r"### Product Owner Final Decision \(exactly three\)\n\n```text\n(.*?)```", binding, re.S
    )
    if decisions_block:
        for forbidden in ("REQUEST_CHANGES", "RERUN_QA", "ESCALATE", "ARCHIVE"):
            if forbidden in decisions_block.group(1):
                bad(f"check07: {forbidden} appears inside the final-decision enum")


def check08_accepted_with_follow_up_is_non_blocking() -> None:
    binding = read(BINDING)
    flat = re.sub(r"\s+", " ", binding)
    if "ACCEPTED_WITH_FOLLOW_UP may contain only non-blocking follow-up items." not in flat:
        bad("check08: the non-blocking-only rule for ACCEPTED_WITH_FOLLOW_UP is missing")
    if "D02-R6" not in binding:
        bad("check08: D02-R6 is missing")


def check09_blocking_maps_to_request_changes() -> None:
    flat = re.sub(r"\s+", " ", read(BINDING))
    if "Whenever a blocking follow-up exists, REQUEST_CHANGES must be used instead." not in flat:
        bad("check09: blocking follow-ups are not mapped to REQUEST_CHANGES")


def check10_review_status_may_carry_outcomes() -> None:
    binding = read(BINDING)
    listing = re.search(
        r"### Delivery review status \(permitted values\)\n\n```text\n(.*?)```", binding, re.S
    )
    if listing is None:
        bad("check10: the delivery review status block was not found")
        return
    values = {line.strip() for line in listing.group(1).splitlines() if line.strip()}
    for expected in ("ACCEPTED", "REJECTED", "CHANGES_REQUESTED", "QA_RERUN_REQUESTED"):
        if expected not in values:
            bad(f"check10: delivery review status is missing {expected}")


def check11_decision_record_is_immutable() -> None:
    binding = read(BINDING)
    flat = re.sub(r"\s+", " ", binding)
    for needle in (
        "ProductOwnerDecision must never be overwritten in place.",
        "supersedes_decision_id",
        "Decision history must never be deleted.",
    ):
        if needle not in flat:
            bad(f"check11: the immutability rule is missing: {needle!r}")
    if "projection of the current effective decision" not in flat:
        bad("check11: the projection relationship is not recorded")


def check12_execution_lineage() -> None:
    flat = re.sub(r"\s+", " ", read(BINDING))
    if "project_id -> work_item_id -> workflow_id -> run_id" not in flat:
        bad("check12: the execution lineage chain is not recorded")
    if "Agent execution source of truth" not in flat:
        bad("check12: the lineage is not declared the Agent execution source of truth")


def check13_human_review_anchor() -> None:
    binding = read(BINDING)
    if "delivery_review_task_id" not in binding:
        bad("check13: the human review anchor is not recorded")
    if "Task is the human-review and RBAC anchor." not in re.sub(r"\s+", " ", binding):
        bad("check13: the human-review anchor boundary is not stated")


def check14_task_is_not_execution_source() -> None:
    flat = re.sub(r"\s+", " ", read(BINDING))
    if "Task is not the Agent execution source of truth." not in flat:
        bad("check14: the record does not deny the Task the execution-source role")
    if "must not be re-described as an Agent pipeline entry point" not in flat:
        bad("check14: D03-R3 does not forbid re-describing the Task API as a pipeline entry")


def check15_legacy_delivery_package_preserved() -> None:
    binding = read(BINDING)
    flat = re.sub(r"\s+", " ", binding)
    if "legacy Platform Ops evidence package" not in flat:
        bad("check15: the legacy DeliveryPackage meaning is not preserved")
    for requirement in ("D04-R1", "D04-R2", "D04-R3", "D04-R4"):
        if requirement not in binding:
            bad(f"check15: {requirement} is missing")
    changed = git("diff", "--name-only", CANONICAL_MAIN).splitlines()
    touched = [p for p in changed if "delivery_package" in p.lower() or "DeliveryPackage" in p]
    if touched:
        bad(f"check15: legacy DeliveryPackage source was modified: {', '.join(touched)}")


def check16_to_19_new_entities() -> None:
    binding = read(BINDING)
    terms = read(TERMS)
    for number, entity in (
        ("check16", "DeliverySubmission"),
        ("check17", "DeliveryReviewAction"),
        ("check18", "ProductOwnerDecision"),
        ("check19", "AcceptanceFollowUpItem"),
    ):
        if entity not in binding:
            bad(f"{number}: {entity} is missing from the binding record")
        if f"## {entity}" not in terms:
            bad(f"{number}: {entity} has no terminology-registry entry")
    if "DeliveryReviewTask" not in binding:
        bad("check16: DeliveryReviewTask is missing from the binding record")


def check20_product_surface_names() -> None:
    binding = read(BINDING)
    for surface in ("Delivery Inbox", "Delivery Review"):
        if surface not in binding:
            bad(f"check20: product surface name {surface!r} is not recorded")


def check21_active_canonical_consistent() -> None:
    gates = read(GATES)
    if "Product Owner Decision Gate" not in gates:
        bad("check21: product-and-technical-gates.md has no separate PO Decision Gate")
    if "6-action Review Gate" not in gates:
        bad("check21: product-and-technical-gates.md does not name the Review Gate as six actions")

    dod = read(DOD)
    for fragment in (
        "Review Gate Action contract complete",
        "Product Owner Final Decision contract complete",
        "Bounded QA rerun rule complete",
        "Blocking versus non-blocking follow-up rule complete",
        "Immutable decision history complete",
        "Dual-anchor traceability complete",
        "Legacy/new entity separation complete",
    ):
        if fragment.lower() not in dod.lower():
            bad(f"check21: Definition of Done is missing {fragment!r}")

    manifest = read(MANIFEST)
    for entity in (
        "DeliverySubmission",
        "DeliveryReviewTask",
        "DeliveryReviewAction",
        "ProductOwnerDecision",
        "AcceptanceFollowUpItem",
    ):
        if entity not in manifest:
            bad(f"check21: canonical-milestone-manifest.md does not require {entity}")
    if "legacy `DeliveryPackage` remains the Step 47/49 Platform Ops evidence object" not in (
        re.sub(r"\s+", " ", manifest)
    ):
        bad("check21: canonical-milestone-manifest.md does not preserve the legacy object")

    if "66D-D01..66D-D04" not in read(PLAN):
        bad("check21: project-completion-master-plan.md does not reference the binding decisions")


def check22_design_spec_separates_layers() -> None:
    spec = read(DESIGN_SPEC)
    if ANNOTATION_MARKER not in spec:
        bad("check22: the design specification carries no Step 66D-ALIGN1 supersession note")
        return
    note = spec.partition(ANNOTATION_MARKER)[2]
    flat = re.sub(r"\s+", " ", note)
    for needle in (
        "Review Gate Action -- exactly six",
        "Product Owner Final Decision -- exactly three",
        "REQUEST_CHANGES != RERUN_QA",
        "ACCEPTED_WITH_FOLLOW_UP requires at least one NON-BLOCKING follow-up",
        "The Delivery Inbox is task-anchored",
        "Execution evidence remains project/work-item/workflow/run anchored",
    ):
        if needle not in flat:
            bad(f"check22: the design-spec note is missing {needle!r}")
    if "Neither is selected" not in flat:
        bad("check22: the design-spec note does not keep the IA options unselected")


def check23_precedence_updated() -> None:
    precedence = read(PRECEDENCE)
    flat = re.sub(r"\s+", " ", precedence)
    if "66D-D01..66D-D04 RESOLVED / BINDING" not in flat:
        bad("check23: the precedence index does not record the 66D binding decisions")
    needle = (
        "binding decision record supersedes conflicting active terminology without rewriting "
        "historical evidence"
    )
    if needle not in flat:
        bad("check23: the precedence index does not state the supersession rule")


def check24_conflicts_resolved() -> None:
    matrix = read(MATRIX)
    for conflict in CONFLICTS:
        if conflict not in matrix:
            bad(f"check24: {conflict} is missing from the supersession matrix")
    for path in (UX_GAPS, POC0_GAPS):
        text = read(path)
        if ANNOTATION_MARKER not in text:
            bad(f"check24: {path.name} carries no supersession note")
            continue
        note = text.partition(ANNOTATION_MARKER)[2]
        for conflict in CONFLICTS:
            if conflict not in note:
                bad(f"check24: {path.name} note does not record {conflict}")


def check25_qa_rerun_count_not_decided() -> None:
    binding = read(BINDING)
    flat = re.sub(r"\s+", " ", binding)
    if "deferred to Step 66D-ARCH contract freeze. NOT decided in this stage." not in flat:
        bad("check25: the bounded QA rerun count is not explicitly deferred")
    for forbidden in (
        r"maximum rerun count\s*[:=]\s*\d",
        r"rerun limit\s*[:=]\s*\d",
        r"cooldown\s*[:=]\s*\d",
    ):
        if re.search(forbidden, binding, re.IGNORECASE):
            bad("check25: this stage appears to have fixed a numeric rerun bound")


def check26_to_29_stages_not_started() -> None:
    binding = read(BINDING)
    retry = read(RETRY)
    for number, label in (
        ("check26", "STEP66D_ARCH1"),
        ("check27", "STEP66D_DESIGN"),
        ("check28", "STEP67POC0"),
        ("check29", "RA2I0"),
    ):
        if not re.search(rf"^{label}:\s+NOT STARTED / NOT AUTHORIZED$", binding, re.MULTILINE):
            bad(f"{number}: {label} is not recorded NOT STARTED / NOT AUTHORIZED")
    if "READY_FOR_PRODUCT_OWNER_AUTHORIZATION" not in retry:
        bad("check26: the retry readiness record has no readiness marker")
    if not re.search(r"^STEP66D_ARCH1:\n\s*NOT STARTED / NOT AUTHORIZED$", retry, re.MULTILINE):
        bad("check26: the retry readiness record does not keep Step 66D-ARCH1 unauthorized")
    if "Readiness is not authorization." not in retry:
        bad("check26: the retry readiness record does not disclaim authorization")


def check30_no_implementation_change() -> None:
    changed = [line for line in git("diff", "--name-only", CANONICAL_MAIN).splitlines() if line]
    offenders = [p for p in changed if p.startswith(FORBIDDEN_SOURCE_PREFIXES)]
    if offenders:
        bad(f"check30: runtime/source paths changed: {', '.join(sorted(offenders))}")
    frontend = [
        p for p in changed if p.endswith((".tsx", ".ts", ".jsx", ".js", ".vue", ".css", ".scss"))
    ]
    if frontend:
        bad(f"check30: frontend source changed: {', '.join(frontend)}")
    infra = [
        p
        for p in changed
        if "docker-compose" in p
        or p.startswith(("helm/", "k8s/", "charts/"))
        or p.endswith((".yaml", ".yml"))
    ]
    if infra:
        bad(f"check30: infra/manifest paths changed: {', '.join(infra)}")
    stray = [
        p
        for p in changed
        if not p.startswith(("docs/", "scripts/verify_step66", "tests/test_step66"))
        and p != "source/progress.md"
    ]
    if stray:
        bad(f"check30: changes outside the allowed alignment scope: {', '.join(stray)}")


def check31_be3_gates_default_false() -> None:
    for var, gate_file in (
        ("BE3_RESUME_API_ENABLED", RESUME_MODEL),
        ("BE3_RESUME_COMMAND_ENABLED", RESUME_MODEL),
        ("BE3_REPLAY_API_ENABLED", REPLAY_MODEL),
        ("BE3_REPLAY_EXECUTION_ENABLED", REPLAY_MODEL),
    ):
        if not gate_file.is_file():
            bad(f"check31: gate file missing: {gate_file.name}")
            continue
        if f'os.environ.get("{var}", "false")' not in gate_file.read_text(encoding="utf-8"):
            bad(f"check31: {var} default is not 'false' in {gate_file.name}")


def check32_production_count_zero() -> None:
    for path in (BINDING, TERMS, MATRIX, GAPS, RETRY, EVIDENCE):
        text = read(path)
        if not text:
            continue
        for value in re.findall(r"production_executed_true_count[`:\s]*([0-9]+)", text, re.I):
            if value != "0":
                bad(f"check32: {path.name} records production_executed_true_count {value}")


def check_annotations_are_append_only() -> None:
    for path in ANNOTATED:
        rel = path.relative_to(ROOT).as_posix()
        numstat = git("diff", "--numstat", CANONICAL_MAIN, "--", rel)
        if not numstat:
            bad(f"annotation: {rel} carries no Step 66D-ALIGN1 note")
            continue
        added, deleted = numstat.split("\t")[:2]
        if deleted != "0":
            bad(f"annotation: {rel} deleted {deleted} line(s); notes must be append-only")
        if int(added) <= 0:
            bad(f"annotation: {rel} added no lines")
        if ANNOTATION_MARKER not in read(path):
            bad(f"annotation: {rel} is missing the annotation marker")


def check_gaps_unauthorized() -> None:
    gaps = read(GAPS)
    if "Authorized: 0 of 10" not in gaps:
        bad("gap-register: does not record 0 of 10 authorized")
    for index in range(1, 11):
        gap = f"ALIGN1-G{index:02d}"
        if gap not in gaps:
            bad(f"gap-register: {gap} is missing")
    if gaps.count("NOT IMPLEMENTED / NOT AUTHORIZED") < 10:
        bad("gap-register: not every gap is marked NOT IMPLEMENTED / NOT AUTHORIZED")


def check33_positive_exact_scope() -> None:
    """Step 66D-ALIGN1-RM1: what the branch changed must equal the registered set exactly."""
    changed = tuple(
        sorted(
            line
            for line in git("diff", "--name-only", CANONICAL_MAIN, ALIGN1_STAGE_HEAD).splitlines()
            if line
        )
    )
    unexpected = sorted(set(changed) - set(ALIGN1_EXPECTED_PATHS))
    missing = sorted(set(ALIGN1_EXPECTED_PATHS) - set(changed))
    if unexpected:
        bad(f"check33: unregistered path changed by this stage: {', '.join(unexpected)}")
    if missing:
        bad(f"check33: registered path not changed by this stage: {', '.join(missing)}")


def main() -> int:
    check01_baseline_main()
    check02_all_decisions_present()
    check03_all_decisions_binding()
    check04_six_review_actions()
    check05_three_final_decisions()
    check06_enums_separated()
    check07_request_changes_and_rerun_are_not_decisions()
    check08_accepted_with_follow_up_is_non_blocking()
    check09_blocking_maps_to_request_changes()
    check10_review_status_may_carry_outcomes()
    check11_decision_record_is_immutable()
    check12_execution_lineage()
    check13_human_review_anchor()
    check14_task_is_not_execution_source()
    check15_legacy_delivery_package_preserved()
    check16_to_19_new_entities()
    check20_product_surface_names()
    check21_active_canonical_consistent()
    check22_design_spec_separates_layers()
    check23_precedence_updated()
    check24_conflicts_resolved()
    check25_qa_rerun_count_not_decided()
    check26_to_29_stages_not_started()
    check30_no_implementation_change()
    check31_be3_gates_default_false()
    check32_production_count_zero()
    check_annotations_are_append_only()
    check_gaps_unauthorized()
    check33_positive_exact_scope()

    if FAILURES:
        for failure in dict.fromkeys(FAILURES):
            print(f"VERIFY FAILED: {failure}", file=sys.stderr)
        return 1
    print(MARKER)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
