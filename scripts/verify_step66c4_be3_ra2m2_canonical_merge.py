"""Deterministic verifier for Step 66C.4-BE3-RA-2M2 canonical merge.

Offline and read-only. Starts no container, opens no database connection, contacts no Vault, no
OIDC provider, no external identity provider and no Kubernetes API, reads no secret, and performs
no network operation other than reading local Git objects.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

MARKER = "STEP66C4_BE3_RA2M2_CANONICAL_MERGE_VERIFY: PASS"

ROOT = Path(__file__).resolve().parents[1]

PRE_MERGE_MAIN = "44ab32ceab60d417ef1e0800be6cd00fc730b12e"
PR_HEAD = "edafc0ca9111bc6dd76bc3ab59b5ea110f2f05d6"
MERGE_COMMIT = "aa02ad5b7fa5ed3997d44420c2f2ec8a2c87c798"
PLANNING_HEAD = "efa396dee6512d6f15b3fd079df87d2c70ee0c77"
PR_NUMBER = "23"

SECURITY = ROOT / "docs" / "security"
CONTRACTS = ROOT / "docs" / "contracts" / "66c4-reminder-expiry-controlled-resume"
HANDOFFS = ROOT / "docs" / "handoffs" / "66c4-reminder-expiry-controlled-resume"
MASTER = ROOT / "docs" / "alignment" / "66-project-completion" / "master"
TEST_DOCS = ROOT / "docs" / "test"

INVENTORY = SECURITY / "be3-ra2-current-state-identity-secret-inventory.md"
THREAT_MODEL = SECURITY / "be3-ra2-identity-secret-threat-and-trust-analysis.md"
DECISION_PACKAGE = CONTRACTS / "be3-ra2-identity-secret-provisioning-decision-package.md"
STAGE_PROPOSAL = HANDOFFS / "be3-ra2-implementation-stage-decomposition.md"
PLANNING_EVIDENCE = TEST_DOCS / "step66c4-be3-ra2-identity-secret-decision-evidence.md"
STAGE_INDEX = MASTER / "next-executable-stage-sequence.md"

BINDING = CONTRACTS / "step66c4-be3-ra2-binding-decisions.md"
ADDENDUM = MASTER / "step66c4-be3-ra2-current-state-20260804.md"
PRECEDENCE = MASTER / "canonical-source-of-truth-precedence.md"
MERGE_RECORD = HANDOFFS / "step66c4-be3-ra2m2-canonical-merge-record.md"

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

HISTORICAL_EVIDENCE = (
    "docs/security/be3-ra2-current-state-identity-secret-inventory.md",
    "docs/security/be3-ra2-identity-secret-threat-and-trust-analysis.md",
    "docs/contracts/66c4-reminder-expiry-controlled-resume/"
    "be3-ra2-identity-secret-provisioning-decision-package.md",
    "docs/handoffs/66c4-reminder-expiry-controlled-resume/"
    "be3-ra2-implementation-stage-decomposition.md",
    "docs/test/step66c4-be3-ra2-identity-secret-decision-evidence.md",
    "scripts/verify_step66c4_be3_ra2_identity_secret_decision.py",
    "tests/test_step66c4_be3_ra2_identity_secret_decision.py",
    "docs/alignment/66-project-completion/master/next-executable-stage-sequence.md",
)

DECISIONS = tuple(f"RA2-D{index:02d}" for index in range(1, 13))
CONDITIONS = tuple(f"RA2-C{index:02d}" for index in range(1, 7))
STAGES = (
    "RA2I0",
    "RA2I4P",
    "RA2I4A",
    "RA2I4B",
    "RA2I1",
    "RA2I3",
    "RA2I2",
    "RA2I5",
    "RA2I6",
    "RA2R",
    "RA3",
)

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


def is_ancestor(commit: str, descendant: str) -> bool:
    return (
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", commit, descendant],
            cwd=ROOT,
            check=False,
        ).returncode
        == 0
    )


def read(path: Path) -> str:
    if not path.is_file():
        bad(f"missing required file: {path.relative_to(ROOT).as_posix()}")
        return ""
    return path.read_text(encoding="utf-8")


def _parents() -> list[str]:
    return git("rev-list", "--parents", "-n", "1", MERGE_COMMIT).split()


def check01_pr_head() -> None:
    """The PR head is the merge commit's second parent -- derived from Git, not from a report."""
    parents = _parents()
    if len(parents) != 3:
        bad(f"check01: merge commit {MERGE_COMMIT[:7]} does not have exactly two parents")
        return
    if parents[2] != PR_HEAD:
        bad(f"check01: merge second parent is {parents[2][:7]}, expected PR #{PR_NUMBER} head")


def check02_pre_merge_main() -> None:
    parents = _parents()
    if len(parents) == 3 and parents[1] != PRE_MERGE_MAIN:
        bad(f"check02: merge first parent is {parents[1][:7]}, expected pre-merge main")


def check03_main_contains_non_squash_merge() -> None:
    if not is_ancestor(MERGE_COMMIT, "HEAD"):
        bad("check03: the merge commit is not present in the current main history")
    if f"#{PR_NUMBER}" not in git("show", "--no-patch", "--format=%s", MERGE_COMMIT):
        bad(f"check03: merge commit subject does not reference PR #{PR_NUMBER}")


def check04_merge_parents() -> None:
    parents = _parents()[1:]
    for expected in (PRE_MERGE_MAIN, PR_HEAD):
        if expected not in parents:
            bad(f"check04: {expected[:7]} is not a parent of the merge commit")


def check05_canonicalization_commit_retained() -> None:
    if not is_ancestor(PR_HEAD, "HEAD"):
        bad("check05: canonicalization commit edafc0c is not retained in main history")
    if git("cat-file", "-t", PR_HEAD) != "commit":
        bad("check05: canonicalization commit object is not reachable")


def check06_planning_source_unchanged() -> None:
    if git("rev-parse", f"{PLANNING_HEAD}^{{commit}}") != PLANNING_HEAD:
        bad("check06: RA-2 planning source efa396d does not resolve to a commit")
    branch_head = git("rev-parse", "origin/planning/66c4-be3-ra2-identity-secret-decision")
    if branch_head and branch_head != PLANNING_HEAD:
        bad("check06: the RA-2 planning branch head is no longer efa396d")
    if is_ancestor(PLANNING_HEAD, "HEAD"):
        bad("check06: the RA-2 planning branch was merged; it must remain unmerged")


def check07_historical_evidence_present() -> None:
    for path in (
        INVENTORY,
        THREAT_MODEL,
        DECISION_PACKAGE,
        STAGE_PROPOSAL,
        PLANNING_EVIDENCE,
        STAGE_INDEX,
    ):
        if not path.is_file():
            bad(f"check07: historical RA-2 artifact missing from main: {path.name}")
    for rel in HISTORICAL_EVIDENCE:
        source = git("rev-parse", f"{PLANNING_HEAD}:{rel}")
        current = git("rev-parse", f"HEAD:{rel}")
        if not source:
            bad(f"check07: {rel} not found in planning commit efa396d")
        elif source != current:
            bad(f"check07: {rel} on main differs from its planning-commit blob")


def check08_historical_evidence_not_rewritten() -> None:
    package = read(DECISION_PACKAGE)
    if "PENDING" not in package:
        bad("check08: the decision package no longer records PENDING selections")
    if "PRODUCT_OWNER_DECISION_REQUIRED" not in package:
        bad("check08: the decision package no longer records PRODUCT_OWNER_DECISION_REQUIRED")
    if "Decided by Claude Code: 0" not in package:
        bad("check08: the decision package no longer records 'Decided by Claude Code: 0'")
    for path in (
        INVENTORY,
        THREAT_MODEL,
        DECISION_PACKAGE,
        STAGE_PROPOSAL,
        PLANNING_EVIDENCE,
        STAGE_INDEX,
    ):
        if "RESOLVED / BINDING" in read(path):
            bad(f"check08: historical evidence {path.name} was rewritten with the new status")


def check09_historical_test_count_preserved() -> None:
    if "79 tests passed" not in read(STAGE_INDEX):
        bad("check09: the historical '79 tests passed' value was edited out of the stage index")


def check10_current_test_count_correction() -> None:
    addendum = read(ADDENDUM)
    if "100 passed / 0 skipped / 0 failed" not in addendum:
        bad("check10: the current-state addendum does not record the verified 100-test result")
    if "79 tests passed" not in addendum:
        bad("check10: the current-state addendum does not name the superseded historical value")
    if "79 tests passed" not in read(PRECEDENCE):
        bad("check10: the precedence index does not record the test-count resolution")


def _section(decision: str) -> str:
    match = re.search(rf"^## {decision} .*?(?=^## |\Z)", read(BINDING), re.MULTILINE | re.DOTALL)
    return match.group(0) if match else ""


def check11_decisions_binding() -> None:
    binding = read(BINDING)
    for decision in DECISIONS:
        block = _section(decision)
        if not block:
            bad(f"check11: {decision} has no section in the binding record on main")
        elif not re.search(r"STATUS:\s+RESOLVED / BINDING", block):
            bad(f"check11: {decision} is not RESOLVED / BINDING on main")
    if "RA2_D01_D12:\nRESOLVED / BINDING" not in binding:
        bad("check11: the D01-D12 summary status is not RESOLVED / BINDING")
    if "DECISION_AUTHORITY:\nProduct Owner" not in binding:
        bad("check11: decision authority is not recorded as Product Owner")


def check12_conditions_binding() -> None:
    binding = read(BINDING)
    for condition in CONDITIONS:
        if condition not in binding:
            bad(f"check12: {condition} is missing from the binding record on main")
    if "RA2_C01_C06:\nRESOLVED / BINDING" not in binding:
        bad("check12: the C01-C06 summary status is not RESOLVED / BINDING")


def check13_vault_agent_versus_csi_unselected() -> None:
    block = _section("RA2-D07")
    if "Vault Agent versus CSI is NOT selected" not in block:
        bad("check13: Vault Agent versus CSI is no longer recorded as unselected")
    if "RA-2I4P" not in block:
        bad("check13: the deferred mechanism choice is not assigned to RA-2I4P")
    if "DEFERRED TO RA-2I4P" not in read(MERGE_RECORD):
        bad("check13: the merge record does not carry the deferred mechanism choice")


def check14_sequence_present() -> None:
    chain = re.search(r"RA-2M\n(?:\s*->\s*RA-[\w]+\n)+", read(BINDING))
    if chain is None:
        bad("check14: the authorized execution chain block is missing from main")
        return
    expected = [
        "RA-2M",
        "RA-2I0",
        "RA-2I4P",
        "RA-2I4A",
        "RA-2I4B",
        "RA-2I1",
        "RA-2I3",
        "RA-2I2",
        "RA-2I5",
        "RA-2I6",
        "RA-2R",
        "RA-3",
    ]
    if re.findall(r"RA-[\w]+", chain.group(0)) != expected:
        bad("check14: the recorded sequence is not in the authorized order")


def check15_sequence_is_not_authorization() -> None:
    binding = read(BINDING)
    if "APPROVED EXECUTION SEQUENCE" not in binding:
        bad("check15: the sequence is not labelled APPROVED EXECUTION SEQUENCE")
    if "NOT IMPLEMENTATION AUTHORIZATION" not in binding:
        bad("check15: the sequence is not explicitly marked as non-authorizing")
    if "RA2_IMPLEMENTATION:\nNOT STARTED / NOT AUTHORIZED" not in binding:
        bad("check15: RA-2 implementation is not recorded NOT STARTED / NOT AUTHORIZED")


def check16_to_17_stages_unauthorized() -> None:
    binding = read(BINDING)
    for stage in STAGES:
        if not re.search(rf"^{stage}:\s+NOT AUTHORIZED$", binding, re.MULTILINE):
            number = "check17" if stage == "RA3" else "check16"
            bad(f"{number}: {stage} is not recorded NOT AUTHORIZED on main")
    record = read(MERGE_RECORD)
    for stage in (
        "RA-2I0",
        "RA-2I4P",
        "RA-2I4A",
        "RA-2I4B",
        "RA-2I1",
        "RA-2I3",
        "RA-2I2",
        "RA-2I5",
        "RA-2I6",
        "RA-2R",
        "RA-3",
    ):
        if not re.search(rf"^{re.escape(stage)}:\s+NOT AUTHORIZED$", record, re.MULTILINE):
            bad(f"check16: the merge record does not record {stage} NOT AUTHORIZED")


def check18_be3_gates_default_false() -> None:
    for var, gate_file in (
        ("BE3_RESUME_API_ENABLED", RESUME_MODEL),
        ("BE3_RESUME_COMMAND_ENABLED", RESUME_MODEL),
        ("BE3_REPLAY_API_ENABLED", REPLAY_MODEL),
        ("BE3_REPLAY_EXECUTION_ENABLED", REPLAY_MODEL),
    ):
        if not gate_file.is_file():
            bad(f"check18: gate file missing: {gate_file.name}")
            continue
        if f'os.environ.get("{var}", "false")' not in gate_file.read_text(encoding="utf-8"):
            bad(f"check18: {var} default is not 'false' in {gate_file.name}")


def check19_no_implementation_merged() -> None:
    changed = [
        line
        for line in git("diff", "--name-only", PRE_MERGE_MAIN, MERGE_COMMIT).splitlines()
        if line.strip()
    ]
    if not changed:
        bad("check19: the merge introduced no file changes at all -- unexpected")
    offenders = [path for path in changed if path.startswith(FORBIDDEN_SOURCE_PREFIXES)]
    if offenders:
        bad(f"check19: the merge introduced runtime/source changes: {', '.join(sorted(offenders))}")
    frontend = [
        path
        for path in changed
        if path.endswith((".tsx", ".ts", ".jsx", ".js", ".vue", ".css", ".scss"))
    ]
    if frontend:
        bad(f"check19: the merge introduced frontend source changes: {', '.join(frontend)}")
    infra = [
        path
        for path in changed
        if "docker-compose" in path
        or path.startswith(("helm/", "k8s/", "charts/"))
        or path.endswith((".yaml", ".yml"))
    ]
    if infra:
        bad(f"check19: the merge introduced infra/manifest changes: {', '.join(infra)}")


def check20_production_count_zero() -> None:
    for path in (BINDING, ADDENDUM, MERGE_RECORD, PRECEDENCE):
        text = read(path)
        if not text:
            continue
        for value in re.findall(r"production_executed_true_count[`:\s]*([0-9]+)", text, re.I):
            if value != "0":
                bad(f"check20: {path.name} records production_executed_true_count {value}")
        for value in re.findall(r"PRODUCTION_EXECUTED_TRUE_COUNT:\s*\n?\s*([0-9]+)", text):
            if value != "0":
                bad(f"check20: {path.name} records PRODUCTION_EXECUTED_TRUE_COUNT {value}")


def check_merge_record() -> None:
    record = read(MERGE_RECORD)
    for needle in (
        "Step 66C.4-BE3-RA-2M2",
        f"#{PR_NUMBER}",
        PR_HEAD,
        PRE_MERGE_MAIN,
        MERGE_COMMIT,
        PLANNING_HEAD,
        "NON-SQUASH MERGE",
        "STEP66C4_BE3_RA2M_CANONICALIZATION_PREP_VERIFY: PASS",
        "Canonicalization commit preserved:\nYES",
        "Historical evidence:\nPRESERVED",
        "79 tests passed",
        "100 tests passed",
    ):
        if needle not in record:
            bad(f"merge-record: missing required entry {needle!r}")


def check_merge_record_scope() -> None:
    """The post-merge record commit must add nothing beyond its own artifacts."""
    changed = [
        line
        for line in git("diff", "--name-only", MERGE_COMMIT, "HEAD").splitlines()
        if line.strip()
    ]
    allowed = {
        "docs/handoffs/66c4-reminder-expiry-controlled-resume/"
        "step66c4-be3-ra2m2-canonical-merge-record.md",
        "scripts/verify_step66c4_be3_ra2m2_canonical_merge.py",
        "tests/test_step66c4_be3_ra2m2_canonical_merge.py",
        "source/progress.md",
        # Bounded post-merge verifier adaptation: the RA-2M1 scope allowlist predates the two
        # RA-2M2 filenames, which the merge could not have contained. Nothing else was touched.
        "scripts/verify_step66c4_be3_ra2m_canonicalization.py",
        "tests/test_step66c4_be3_ra2m_canonicalization.py",
    }
    stray = [path for path in changed if path not in allowed]
    if stray:
        bad(f"merge-record-scope: unexpected paths after the merge: {', '.join(stray)}")

    for rel in (
        "scripts/verify_step66c4_be3_ra2m_canonicalization.py",
        "tests/test_step66c4_be3_ra2m_canonicalization.py",
    ):
        numstat = git("diff", "--numstat", MERGE_COMMIT, "HEAD", "--", rel)
        if not numstat:
            continue
        added, deleted = numstat.split("\t")[:2]
        if int(added) > 4 or int(deleted) > 0:
            bad(f"merge-record-scope: {rel} changed beyond the bounded allowlist adaptation")
        body = (ROOT / rel).read_text(encoding="utf-8")
        for runtime_prefix in FORBIDDEN_SOURCE_PREFIXES:
            if f'"{runtime_prefix}"' in body.split("allowed_exact")[-1][:900]:
                bad(
                    f"merge-record-scope: {rel} adaptation admitted runtime prefix {runtime_prefix}"
                )


def main() -> int:
    check01_pr_head()
    check02_pre_merge_main()
    check03_main_contains_non_squash_merge()
    check04_merge_parents()
    check05_canonicalization_commit_retained()
    check06_planning_source_unchanged()
    check07_historical_evidence_present()
    check08_historical_evidence_not_rewritten()
    check09_historical_test_count_preserved()
    check10_current_test_count_correction()
    check11_decisions_binding()
    check12_conditions_binding()
    check13_vault_agent_versus_csi_unselected()
    check14_sequence_present()
    check15_sequence_is_not_authorization()
    check16_to_17_stages_unauthorized()
    check18_be3_gates_default_false()
    check19_no_implementation_merged()
    check20_production_count_zero()
    check_merge_record()
    check_merge_record_scope()

    if FAILURES:
        for failure in dict.fromkeys(FAILURES):
            print(f"VERIFY FAILED: {failure}", file=sys.stderr)
        return 1
    print(MARKER)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
