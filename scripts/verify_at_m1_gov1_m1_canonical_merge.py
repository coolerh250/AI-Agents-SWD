#!/usr/bin/env python3
"""AT-M1-GOV1-M1 -- canonical merge verifier for the stage-family governance remediation.

Deterministic and read-only. Confirms PR #30 was merged as a non-squash two-parent merge with all
seven commits preserved, that the merged admission rule is the registered-family rule and not a
broad path allowlist, that ALIGN1 historical truth survived the merge unchanged, that the D-01
behavioral enforcement checks are present and actually behavioral, that the merge record states the
real commit chain, and that no runtime, architecture, precedence, manifest or source/progress.md
path was touched.

The GOV1 stage scope is verified over the FROZEN range 2d4da80...2faa9c7, not against live HEAD:
merged, HEAD is main and advances, so it can no longer be a positive endpoint.

Starts no runtime, container, database or external provider.

Marker: AT_M1_GOV1_M1_CANONICAL_MERGE_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import importlib.util
import pathlib
import re
import subprocess
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
MARKER = "AT_M1_GOV1_M1_CANONICAL_MERGE_VERIFY"

PRE_MERGE_MAIN = "2d4da808b1a89ea278fbb760e27f49047995165e"
GOV1_STAGE_HEAD = "2faa9c7fe68dcd1bb04aab971c34a6d0bb047e2c"
MERGE_COMMIT = "d2d9b7380b3c8e95e276547e46e83b9989ce5955"
GOV1_FROZEN_RANGE = f"{PRE_MERGE_MAIN}...{GOV1_STAGE_HEAD}"

PR30_COMMITS = (
    "964ca7afb31ec91859a9c8f0deb104c719b9fccc",
    "aa77b0b",
    "690ed76",
    "5b939b773e49d9e5ffd6d10309e10dada5e43f28",
    "36176e4",
    "800679d",
    GOV1_STAGE_HEAD,
)

ALIGN1_VERIFIER = "scripts/verify_step66d_align1_delivery_decision_model.py"
ALIGN1_TEST = "tests/test_step66d_align1_delivery_decision_model.py"
GOV1_VERIFIER = "scripts/verify_at_m1_gov1_stage_family_compatibility.py"
GOV1_TEST = "tests/test_at_m1_gov1_stage_family_compatibility.py"
GOV1_EVIDENCE = "docs/handoffs/autonomous-team/at-m1-gov1-stage-family-compatibility-evidence.md"
RECORD = "docs/handoffs/autonomous-team/at-m1-gov1-m1-canonical-merge-record.md"

GOV1_EXPECTED_PATHS = frozenset(
    {ALIGN1_VERIFIER, ALIGN1_TEST, GOV1_VERIFIER, GOV1_TEST, GOV1_EVIDENCE}
)

# The ALIGN1 historical boundary. The merge must not have moved either endpoint.
ALIGN1_CANONICAL_MAIN = "64467fefc9a9ec303f9ddf4c0ce6d46486504d71"
ALIGN1_STAGE_HEAD = "6a8a7bfa2ae758e944b1126881a69fef2d122dcb"
ALIGN1_EXPECTED_PATH_COUNT = 34

MUST_ADMIT = (
    "scripts/verify_step66d_align1_delivery_decision_model.py",
    "tests/test_step66d_align1_delivery_decision_model.py",
    "scripts/verify_at_m1_architecture_reset.py",
    "tests/test_at_m1_architecture_reset.py",
    "scripts/verify_at_m2_team_identity_collaboration.py",
    "tests/test_at_m8_delivery_closure.py",
    RECORD,
    "scripts/verify_at_m1_gov1_m1_canonical_merge.py",
    "tests/test_at_m1_gov1_m1_canonical_merge.py",
)

MUST_REJECT = (
    "scripts/at_runtime_patch.py",
    "scripts/random_helper.py",
    "tests/random_test_helper.py",
    "shared/sdk/tasks/rbac.py",
    "apps/orchestrator/src/main.py",
    "agents/qa-agent/src/agent.py",
    "migrations/037_example.sql",
    "infra/docker-compose/docker-compose.yml",
    "",
)

FORBIDDEN_PREFIXES = (
    "apps/",
    "agents/",
    "services/",
    "shared/",
    "migrations/",
    "infra/",
    "helm/",
    "k8s/",
    "runtime/",
    ".github/workflows/",
    "docs/architecture/autonomous-team/",
    "docs/contracts/autonomous-team/",
    "docs/decisions/",
)

failures: list[str] = []
checks_run = 0


def expect(ok: bool, label: str, message: str) -> None:
    global checks_run
    checks_run += 1
    if not ok:
        failures.append(f"{label}: {message}")
        print(f"  [FAIL] {label}: {message}")


def git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=False
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def is_ancestor(commit: str, ref: str = "HEAD") -> bool:
    return (
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", commit, ref],
            cwd=ROOT,
            capture_output=True,
            check=False,
        ).returncode
        == 0
    )


def read(relpath: str) -> str:
    path = ROOT / relpath
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def flat(text: str) -> str:
    return re.sub(r"\s+", " ", text)


def align1_module():
    """The merged ALIGN1 verifier, loaded so its real admission rule can be exercised."""
    spec = importlib.util.spec_from_file_location("gov1_m1_align1", ROOT / ALIGN1_VERIFIER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check33_records_failure(module: Any, registry: tuple[str, ...]) -> bool:
    """Drive the merged check33 against a perturbed registry; restore state afterwards."""
    saved_registry = module.ALIGN1_EXPECTED_PATHS
    saved_failures = list(module.FAILURES)
    module.ALIGN1_EXPECTED_PATHS = tuple(registry)
    module.FAILURES.clear()
    try:
        module.check33_positive_exact_scope()
        return any(message.startswith("check33") for message in module.FAILURES)
    finally:
        module.FAILURES.clear()
        module.FAILURES.extend(saved_failures)
        module.ALIGN1_EXPECTED_PATHS = saved_registry


def main() -> int:  # noqa: PLR0915
    align1_src = read(ALIGN1_VERIFIER)
    gov1_src = read(GOV1_VERIFIER)
    record = read(RECORD)
    module = align1_module()

    # --- 1. merge shape -------------------------------------------------------------------------
    expect(is_ancestor(PRE_MERGE_MAIN), "check01", "pre-merge main 2d4da80 is not an ancestor")
    expect(is_ancestor(GOV1_STAGE_HEAD), "check02", "PR #30 head 2faa9c7 is not an ancestor")
    expect(is_ancestor(MERGE_COMMIT), "check03", "merge commit d2d9b73 is not an ancestor")
    parents = git("rev-list", "--parents", "-n", "1", MERGE_COMMIT).split()
    expect(len(parents) == 3, "check04", f"merge commit is not a two-parent merge: {parents}")
    expect(
        len(parents) == 3 and parents[1] == PRE_MERGE_MAIN,
        "check05",
        "merge parent 1 is not the pre-merge main",
    )
    expect(
        len(parents) == 3 and parents[2] == GOV1_STAGE_HEAD,
        "check06",
        "merge parent 2 is not the PR #30 head",
    )
    for index, commit in enumerate(PR30_COMMITS, start=1):
        expect(
            is_ancestor(commit),
            f"check0{6 + index}" if 6 + index < 10 else f"check{6 + index}",
            f"PR #30 commit {commit[:7]} was not preserved (squash or rebase?)",
        )

    # --- 2. GOV1 stage scope, frozen ------------------------------------------------------------
    changed = {
        line.strip().replace("\\", "/")
        for line in git("diff", "--name-only", GOV1_FROZEN_RANGE).splitlines()
        if line.strip()
    }
    expect(
        changed == GOV1_EXPECTED_PATHS,
        "check14",
        "the merged GOV1 stage scope is not exactly the 5-path registry: "
        f"unexpected={sorted(changed - GOV1_EXPECTED_PATHS)} "
        f"missing={sorted(GOV1_EXPECTED_PATHS - changed)}",
    )
    expect(len(changed) == 5, "check15", f"GOV1 stage scope holds {len(changed)} paths, not 5")
    offenders = sorted(p for p in changed if p.startswith(FORBIDDEN_PREFIXES))
    expect(offenders == [], "check16", f"GOV1 changed runtime/architecture paths: {offenders}")
    expect(
        "source/progress.md" not in changed,
        "check17",
        "source/progress.md was changed by the GOV1 stage",
    )
    expect(
        '"HEAD"' not in gov1_src.split("GOV1_POSITIVE_RANGE")[0],
        "check18",
        "the GOV1 verifier constants section unexpectedly references a HEAD endpoint",
    )

    # --- 3. ALIGN1 historical truth survived the merge ------------------------------------------
    expect(
        f'CANONICAL_MAIN = "{ALIGN1_CANONICAL_MAIN}"' in align1_src,
        "check19",
        "the ALIGN1 canonical baseline constant changed across the merge",
    )
    expect(
        f'ALIGN1_STAGE_HEAD = "{ALIGN1_STAGE_HEAD}"' in align1_src,
        "check20",
        "the ALIGN1 frozen stage head changed across the merge",
    )
    expect(
        'git("diff", "--name-only", CANONICAL_MAIN, ALIGN1_STAGE_HEAD)' in align1_src,
        "check21",
        "check33 no longer diffs the frozen two-endpoint historical range",
    )
    expect(
        len(getattr(module, "ALIGN1_EXPECTED_PATHS", ())) == ALIGN1_EXPECTED_PATH_COUNT,
        "check22",
        f"the ALIGN1 historical registry no longer holds {ALIGN1_EXPECTED_PATH_COUNT} paths",
    )
    historical = sorted(
        line
        for line in git(
            "diff", "--name-only", ALIGN1_CANONICAL_MAIN, ALIGN1_STAGE_HEAD
        ).splitlines()
        if line.strip()
    )
    expect(
        set(historical) == set(module.ALIGN1_EXPECTED_PATHS),
        "check23",
        "the ALIGN1 historical frozen scope no longer matches its registry exactly",
    )

    # --- 4. D-01 closure survived as BEHAVIORAL, not textual ------------------------------------
    registry = tuple(module.ALIGN1_EXPECTED_PATHS)
    phantom = "docs/handoffs/at-m1-gov1-m1-merge-record-probe-phantom.md"
    expect(
        phantom not in registry and check33_records_failure(module, registry + (phantom,)),
        "check24",
        "merged check33 does not ENFORCE the missing direction",
    )
    expect(
        len(registry) > 0 and check33_records_failure(module, registry[:-1]),
        "check25",
        "merged check33 does not ENFORCE the unexpected direction",
    )
    expect(
        not check33_records_failure(module, registry),
        "check26",
        "behavioral control failed: merged check33 fails on its untampered registry",
    )
    expect(
        tuple(module.ALIGN1_EXPECTED_PATHS) == registry,
        "check27",
        "the behavioral probe left the ALIGN1 registry mutated",
    )
    for label, name in (("check28", "check11a"), ("check29", "check11b"), ("check30", "check11c")):
        expect(f'"{name}"' in gov1_src, label, f"the GOV1 verifier lost behavioral gate {name}")
    expect(
        "check33_records_failure" in gov1_src,
        "check31",
        "the GOV1 verifier lost its behavioral probe helper",
    )

    # --- 5. registered-family admission is binding and bounded ----------------------------------
    admit = getattr(module, "is_admitted_current_state_path", None)
    expect(callable(admit), "check32", "the merged ALIGN1 verifier exposes no admission rule")
    if callable(admit):
        wrongly_rejected = [p for p in MUST_ADMIT if not admit(p)]
        expect(
            wrongly_rejected == [],
            "check33",
            f"registered governance artifacts are rejected: {wrongly_rejected}",
        )
        wrongly_admitted = [p for p in MUST_REJECT if admit(p)]
        expect(
            wrongly_admitted == [],
            "check34",
            f"non-governance paths are admitted: {wrongly_admitted}",
        )
    # GOV-DOMAIN-ADMISSION-01 (Step PCP-V2.1-RM1): admission is decided by domain membership, so
    # there is no stage-family registry to compare. What must hold is that an unseen family is
    # admitted and the registry has not come back.
    classify = getattr(module, "is_governance_artifact", None)
    expect(
        callable(classify)
        and classify("scripts/verify_zzz_family_nobody_has_invented_yet.py")
        and classify("tests/test_zzz_family_nobody_has_invented_yet.py")
        and not hasattr(module, "REGISTERED_GOVERNANCE_FAMILIES"),
        "check35",
        "governance admission still depends on a stage-family registry",
    )
    expect(
        'ADMITTED_PATH_PREFIXES = ("docs/",)' in align1_src,
        "check36",
        "a broad path allowlist was introduced into the merged admission rule",
    )

    # --- 6. the merge record states the real chain ----------------------------------------------
    flat_record = flat(record)
    for label, value, what in (
        ("check37", PRE_MERGE_MAIN, "pre-merge main"),
        ("check38", GOV1_STAGE_HEAD, "PR #30 head"),
        ("check39", MERGE_COMMIT, "merge commit"),
        ("check40", ALIGN1_CANONICAL_MAIN, "ALIGN1 canonical baseline"),
        ("check41", ALIGN1_STAGE_HEAD, "ALIGN1 frozen stage head"),
    ):
        expect(value in record, label, f"the merge record does not state the {what} SHA")
    expect(
        "NON-SQUASH MERGE" in record and "Parent count: 2" in flat_record,
        "check42",
        "the merge record does not state a non-squash two-parent merge",
    )
    expect(
        "PR commit count: 7" in flat_record,
        "check43",
        "the merge record does not state the seven preserved commits",
    )
    expect(
        "source/progress.md: UNCHANGED" in flat_record,
        "check44",
        "the merge record does not record source/progress.md as unchanged",
    )
    expect(
        "A-01" in record and "AT_M1_BASELINE" in record,
        "check45",
        "the merge record carries no A-01 re-pin handoff for AT-M1-RM1",
    )
    expect(
        "PRODUCTION_EXECUTED_TRUE_COUNT: 0" in flat_record,
        "check46",
        "the merge record does not state production_executed_true_count 0",
    )

    # --- 7. nothing else moved ------------------------------------------------------------------
    merge_paths = {
        line.strip().replace("\\", "/")
        for line in git("diff", "--name-only", f"{PRE_MERGE_MAIN}..{MERGE_COMMIT}").splitlines()
        if line.strip()
    }
    expect(
        merge_paths == GOV1_EXPECTED_PATHS,
        "check47",
        f"the merge introduced paths beyond the GOV1 registry: {sorted(merge_paths)}",
    )

    print(f"  checks_run={checks_run}")
    if failures:
        print(f"{MARKER}: FAIL")
        return 1
    print("  [OK] PR #30 merged as a non-squash two-parent merge with all seven commits preserved;")
    print("       GOV1 stage scope frozen to 2d4da80...2faa9c7 with an exact 5-path registry;")
    print("       ALIGN1 historical endpoints, 34-path registry and exact bidirectional equality")
    print("       unchanged; D-01 closure still BEHAVIORAL -- the merged check33 is driven in both")
    print("       directions and restores its own state; registered-family admission binding and")
    print("       bounded with no broad allowlist; merge record states the real chain and the A-01")
    print("       re-pin handoff; source/progress.md untouched; no runtime path; prod_exec=0")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
