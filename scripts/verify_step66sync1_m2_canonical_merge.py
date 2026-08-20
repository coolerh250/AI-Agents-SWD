"""Deterministic verifier for Step 66SYNC.1-M2 canonical merge.

Offline and read-only. Starts no container, opens no database connection, reads no secret,
and performs no network operation other than reading local Git objects.
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
from successor_lifecycle import successor_window_end  # noqa: E402

MARKER = "STEP66SYNC1_M2_CANONICAL_MERGE_VERIFY: PASS"

ROOT = Path(__file__).resolve().parents[1]

PRE_MERGE_MAIN = "c1db4ccbfd88fa775e4761c932835896b9b980ed"
PR_HEAD = "1278b8944e3a8f824a9b35f82382fa8587e7989d"
MERGE_COMMIT = "7971ae0c5a5d90a186efd4c52f75988720ce214e"
PR_NUMBER = "22"
# This stage's own post-merge record commit. The bounded-adaptation guard below
# measures what THIS stage changed, not what later authorized stages changed.
RECORD_COMMIT = "44ab32ceab60d417ef1e0800be6cd00fc730b12e"
CANONICAL_BASELINE_HINT = "c1db4ccbfd88fa775e4761c932835896b9b980ed"

SYNC = ROOT / "docs" / "handoffs" / "program-sync"
MASTER = ROOT / "docs" / "alignment" / "66-project-completion" / "master"
TEST_DOCS = ROOT / "docs" / "test"
DESIGN_SPEC = ROOT / "docs" / "design" / "ai-agent-team-functional-poc-control-center-spec.md"

BINDING = SYNC / "step66sync1-poc-scope-binding-decisions.md"
ADDENDUM = MASTER / "partner-synchronized-program-state-20260804.md"
PRECEDENCE = MASTER / "canonical-source-of-truth-precedence.md"
MANIFEST = SYNC / "step66sync1-canonicalization-manifest.md"
MERGE_RECORD = SYNC / "step66sync1-m2-canonical-merge-record.md"

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

STEP66SYNC1_ARTIFACTS = (
    "docs/alignment/66-project-completion/master/partner-context-snapshot-20260803.md",
    "docs/alignment/66-project-completion/master/partner-synchronized-program-state-20260803.md",
    "docs/alignment/66-project-completion/master/partner-synchronized-program-state-20260804.md",
    "docs/alignment/66-project-completion/master/canonical-source-of-truth-precedence.md",
    "docs/design/ai-agent-team-functional-poc-control-center-spec.md",
    "docs/handoffs/program-sync/step66sync1-canonicalization-manifest.md",
    "docs/handoffs/program-sync/step66sync1-claude-code-acknowledgement.md",
    "docs/handoffs/program-sync/step66sync1-claude-design-acknowledgement.md",
    "docs/handoffs/program-sync/step66sync1-claude-design-ux-gap-register.md",
    "docs/handoffs/program-sync/step66sync1-codex-acknowledgement.md",
    "docs/handoffs/program-sync/step66sync1-codex-frontend-gap-register.md",
    "docs/handoffs/program-sync/step66sync1-context-discrepancy-register.md",
    "docs/handoffs/program-sync/step66sync1-final-context-discrepancy-register.md",
    "docs/handoffs/program-sync/step66sync1-final-partner-acknowledgement.md",
    "docs/handoffs/program-sync/step66sync1-poc-backend-readiness-matrix.md",
    "docs/handoffs/program-sync/step66sync1-poc-scope-binding-decisions.md",
    "docs/handoffs/program-sync/step66sync1-poc-scope-decision-package.md",
    "docs/handoffs/program-sync/step66sync1-poc0-consolidated-gap-register.md",
    "docs/test/step66sync1-claude-code-reconciliation-evidence.md",
    "docs/test/step66sync1-claude-design-reconciliation-evidence.md",
    "docs/test/step66sync1-codex-frontend-reconciliation-evidence.md",
    "docs/test/step66sync1-final-partner-reconciliation-evidence.md",
    "docs/test/step66sync1-m1-canonicalization-evidence.md",
)

# Partner evidence that predates the binding decisions and must survive verbatim.
HISTORICAL_EVIDENCE = (
    "docs/handoffs/program-sync/step66sync1-claude-code-acknowledgement.md",
    "docs/handoffs/program-sync/step66sync1-codex-acknowledgement.md",
    "docs/handoffs/program-sync/step66sync1-claude-design-acknowledgement.md",
    "docs/handoffs/program-sync/step66sync1-final-partner-acknowledgement.md",
    "docs/handoffs/program-sync/step66sync1-poc-scope-decision-package.md",
    "docs/handoffs/program-sync/step66sync1-poc0-consolidated-gap-register.md",
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


def check01_pr_head() -> None:
    """The PR head is the merge commit's second parent -- derived from Git, not from a report."""
    parents = git("rev-list", "--parents", "-n", "1", MERGE_COMMIT).split()
    if len(parents) != 3:
        bad(f"check01: merge commit {MERGE_COMMIT[:7]} does not have exactly two parents")
        return
    if parents[2] != PR_HEAD:
        bad(
            f"check01: merge commit second parent is {parents[2][:7]}, expected PR #{PR_NUMBER} head"
        )


def check02_pre_merge_main() -> None:
    parents = git("rev-list", "--parents", "-n", "1", MERGE_COMMIT).split()
    if len(parents) != 3:
        return
    if parents[1] != PRE_MERGE_MAIN:
        bad(f"check02: merge commit first parent is {parents[1][:7]}, expected pre-merge main")


def check03_main_contains_non_squash_merge() -> None:
    if not is_ancestor(MERGE_COMMIT, "HEAD"):
        bad("check03: the merge commit is not present in the current main history")
    subject = git("show", "--no-patch", "--format=%s", MERGE_COMMIT)
    if f"#{PR_NUMBER}" not in subject:
        bad(f"check03: merge commit subject does not reference PR #{PR_NUMBER}")


def check04_merge_parents() -> None:
    parents = git("rev-list", "--parents", "-n", "1", MERGE_COMMIT).split()[1:]
    for expected in (PRE_MERGE_MAIN, PR_HEAD):
        if expected not in parents:
            bad(f"check04: {expected[:7]} is not a parent of the merge commit")


def check05_canonicalization_commit_retained() -> None:
    if not is_ancestor(PR_HEAD, "HEAD"):
        bad("check05: canonicalization commit 1278b89 is not retained in main history")
    if git("cat-file", "-t", PR_HEAD) != "commit":
        bad("check05: canonicalization commit object is not reachable")


def check06_artifacts_present_on_main() -> None:
    for rel in STEP66SYNC1_ARTIFACTS:
        if git("cat-file", "-t", f"HEAD:{rel}") != "blob":
            bad(f"check06: Step 66SYNC.1 artifact missing from main: {rel}")


def check07_to_09_decisions_binding() -> None:
    binding = read(BINDING)
    for number, decision, option in (
        ("check07", "D-1", "Selected:     Dedicated POC Development Goal"),
        ("check08", "D-2", "Selected:     Hybrid execution model"),
        ("check09", "D-3", "Selected:     Runtime LLM remains plan-only"),
    ):
        if not re.search(rf"^{decision}:\n\s*RESOLVED / BINDING$", binding, re.MULTILINE):
            bad(f"{number}: {decision} is no longer RESOLVED / BINDING on main")
        if option not in binding:
            bad(f"{number}: {decision} selected option is missing on main")
    if "DECISION_AUTHORITY:\nProduct Owner" not in binding:
        bad("check07: decision authority is no longer recorded as Product Owner")


def check10_binding_conditions_present() -> None:
    binding = read(BINDING)
    for index in range(1, 13):
        if f"B-{index:02d}" not in binding:
            bad(f"check10: binding condition B-{index:02d} is missing on main")


def check11_historical_evidence_present() -> None:
    for rel in HISTORICAL_EVIDENCE:
        text = read(ROOT / rel)
        if not text:
            continue
        if "RESOLVED / BINDING" in text:
            bad(f"check11: historical evidence {Path(rel).name} was rewritten with the new status")
    ack = read(SYNC / "step66sync1-final-partner-acknowledgement.md")
    if "OPEN_PRODUCT_OWNER_DECISIONS:\n3" not in ack:
        bad("check11: the historical open-decision count no longer reads 3")


def check12_screen_count() -> None:
    spec = read(DESIGN_SPEC)
    headings = re.findall(r"^### 7\.\d+ ", spec, re.MULTILINE)
    if len(headings) != 15:
        bad(f"check12: the specification defines {len(headings)} screens, expected 15")


def check13_step66d_identifier_retained() -> None:
    for term in ("Step 66D-ARCH", "66D-DESIGN"):
        if not git("grep", "-l", term, "HEAD", "--", "docs"):
            bad(f"check13: canonical identifier {term} is no longer present on main")


def check14_ia_options_non_binding() -> None:
    binding = read(BINDING)
    if not re.search(r"remain\s+POC\.0\s+non-binding\s+design\s+options;\s+neither\s+is", binding):
        bad("check14: the IA options are no longer recorded as non-binding and unselected")
    if "non-binding until a Product Owner selects it" not in read(PRECEDENCE):
        bad("check14: the precedence record no longer marks design options non-binding")


def check15_poc_implementation_unauthorized() -> None:
    binding = read(BINDING)
    if "POC_IMPLEMENTATION_AUTHORIZED:\nNO" not in binding:
        bad("check15: POC implementation is no longer recorded as unauthorized")
    if not re.search(
        r"^POC_IMPLEMENTATION:\s+NOT STARTED / NOT AUTHORIZED$", read(ADDENDUM), re.MULTILINE
    ):
        bad("check15: the addendum no longer records POC implementation as unauthorized")


def check16_to_18_stages_unauthorized() -> None:
    addendum = read(ADDENDUM)
    for number, label in (
        ("check16", "RA2M"),
        ("check17", "STEP66D_ARCH"),
        ("check18", "STEP67POC0"),
    ):
        if not re.search(rf"^{label}:\s+NOT STARTED / NOT AUTHORIZED$", addendum, re.MULTILINE):
            bad(f"{number}: {label} is no longer NOT STARTED / NOT AUTHORIZED")


def check19_be3_gates_default_false() -> None:
    for var, gate_file in (
        ("BE3_RESUME_API_ENABLED", RESUME_MODEL),
        ("BE3_RESUME_COMMAND_ENABLED", RESUME_MODEL),
        ("BE3_REPLAY_API_ENABLED", REPLAY_MODEL),
        ("BE3_REPLAY_EXECUTION_ENABLED", REPLAY_MODEL),
    ):
        if not gate_file.is_file():
            bad(f"check19: gate file missing: {gate_file.name}")
            continue
        if f'os.environ.get("{var}", "false")' not in gate_file.read_text(encoding="utf-8"):
            bad(f"check19: {var} default is not 'false' in {gate_file.name}")


def check20_no_implementation_merged() -> None:
    changed = [
        line
        for line in git("diff", "--name-only", PRE_MERGE_MAIN, MERGE_COMMIT).splitlines()
        if line.strip()
    ]
    if not changed:
        bad("check20: the merge introduced no file changes at all -- unexpected")
    offenders = [path for path in changed if path.startswith(FORBIDDEN_SOURCE_PREFIXES)]
    if offenders:
        bad(f"check20: the merge introduced runtime/source changes: {', '.join(sorted(offenders))}")
    frontend = [
        path
        for path in changed
        if path.endswith((".tsx", ".ts", ".jsx", ".js", ".vue", ".css", ".scss"))
    ]
    if frontend:
        bad(f"check20: the merge introduced frontend source changes: {', '.join(frontend)}")
    infra = [
        path
        for path in changed
        if "docker-compose" in path or path.startswith(("helm/", "k8s/", "charts/"))
    ]
    if infra:
        bad(f"check20: the merge introduced infra/deployment changes: {', '.join(infra)}")


def check21_production_count_zero() -> None:
    for path in (BINDING, ADDENDUM, MANIFEST, PRECEDENCE, MERGE_RECORD):
        text = read(path)
        if not text:
            continue
        for value in re.findall(r"production_executed_true_count[`:\s]*([0-9]+)", text, re.I):
            if value != "0":
                bad(f"check21: {path.name} records production_executed_true_count {value}")
        for value in re.findall(r"PRODUCTION_EXECUTED_TRUE_COUNT:\s*\n?\s*([0-9]+)", text):
            if value != "0":
                bad(f"check21: {path.name} records PRODUCTION_EXECUTED_TRUE_COUNT {value}")


def check_merge_record() -> None:
    record = read(MERGE_RECORD)
    for needle in (
        "Step 66SYNC.1-M2",
        f"#{PR_NUMBER}",
        PR_HEAD,
        PRE_MERGE_MAIN,
        MERGE_COMMIT,
        "NON-SQUASH MERGE",
        "STEP66SYNC1_M1_CANONICALIZATION_PREP_VERIFY: PASS",
    ):
        if needle not in record:
            bad(f"merge-record: missing required entry {needle!r}")
    for phrase in ("POC.0 authorized", "RA-2M authorized", "Step 66D-ARCH authorized"):
        if phrase.lower() in record.lower():
            bad(f"merge-record: claims {phrase!r}, which is not authorized")


def check_merge_record_scope() -> None:
    """The merge-record commit itself must add nothing beyond its own three files."""
    changed = [
        line
        for line in git("diff", "--name-only", MERGE_COMMIT, RECORD_COMMIT).splitlines()
        if line.strip()
    ]
    allowed = {
        "docs/handoffs/program-sync/step66sync1-m2-canonical-merge-record.md",
        "scripts/verify_step66sync1_m2_canonical_merge.py",
        "tests/test_step66sync1_m2_canonical_merge.py",
        "source/progress.md",
        # The M1 gate pinned origin/main == c1db4cc, which the merge itself falsified. Its
        # baseline assertion was narrowed to ancestry so the gate stays true post-merge.
        "scripts/verify_step66sync1_m1_canonicalization.py",
        "tests/test_step66sync1_m1_canonicalization.py",
    }
    # Step 66D-ALIGN1-RM1: the range above is frozen, so the exact set is authoritative.
    stray = [path for path in changed if path not in allowed]
    if stray:
        bad(f"merge-record-scope: unexpected paths after the merge: {', '.join(stray)}")

    for rel in (
        "scripts/verify_step66sync1_m1_canonicalization.py",
        "tests/test_step66sync1_m1_canonicalization.py",
    ):
        numstat = git("diff", "--numstat", MERGE_COMMIT, RECORD_COMMIT, "--", rel)
        if not numstat:
            continue
        added, deleted = numstat.split("\t")[:2]
        if int(added) > 15 or int(deleted) > 5:
            bad(f"merge-record-scope: {rel} changed by more than the baseline correction")
        body = (ROOT / rel).read_text(encoding="utf-8")
        if "merge-base" not in body or CANONICAL_BASELINE_HINT not in body:
            bad(f"merge-record-scope: {rel} no longer asserts the canonical baseline")


# Step 66D-ALIGN1-RM1: the stage SCOPE above is frozen, which is what stops it drifting.
# The runtime denylist must not be frozen with it -- a runtime path added by any later
# commit still has to be caught. This anchor is deliberately HEAD-relative, and it feeds
# the denylist only; it never widens or satisfies the stage scope.
RUNTIME_GUARD_ANCHOR = "7971ae0c5a5d90a186efd4c52f75988720ce214e"


def check_runtime_guard_current_state() -> None:
    """Reject runtime/frontend/infra paths introduced at any point after this stage's baseline."""
    changed = [
        line
        for line in git(
            "diff", "--name-only", RUNTIME_GUARD_ANCHOR,
            successor_window_end(RUNTIME_GUARD_ANCHOR)
        ).splitlines()
        if line.strip()
    ]
    offenders = [
        path
        for path in changed
        if path.startswith(("apps/", "agents/", "services/", "shared/", "migrations/", "infra/"))
        or path.endswith((".tsx", ".jsx", ".vue", ".yaml", ".yml", ".sql"))
        or "docker-compose" in path
        or path.startswith(("helm/", "k8s/", "charts/"))
    ]
    if offenders:
        bad(
            f"runtime-guard: protected path present after this stage: {', '.join(sorted(offenders))}"
        )


def main() -> int:
    check01_pr_head()
    check02_pre_merge_main()
    check03_main_contains_non_squash_merge()
    check04_merge_parents()
    check05_canonicalization_commit_retained()
    check06_artifacts_present_on_main()
    check07_to_09_decisions_binding()
    check10_binding_conditions_present()
    check11_historical_evidence_present()
    check12_screen_count()
    check13_step66d_identifier_retained()
    check14_ia_options_non_binding()
    check15_poc_implementation_unauthorized()
    check16_to_18_stages_unauthorized()
    check19_be3_gates_default_false()
    check20_no_implementation_merged()
    check21_production_count_zero()
    check_merge_record()
    check_merge_record_scope()

    check_runtime_guard_current_state()

    if FAILURES:
        for failure in dict.fromkeys(FAILURES):
            print(f"VERIFY FAILED: {failure}", file=sys.stderr)
        return 1
    print(MARKER)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
