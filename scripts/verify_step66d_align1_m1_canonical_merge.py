"""Deterministic verifier for Step 66D-ALIGN1-M1 canonical merge.

Offline and read-only. Starts no container, opens no database connection, contacts no Vault, OIDC
provider or Kubernetes API, reads no secret, and performs no network operation other than reading
local Git objects.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

MARKER = "STEP66D_ALIGN1_M1_CANONICAL_MERGE_VERIFY: PASS"

ROOT = Path(__file__).resolve().parents[1]

PRE_MERGE_MAIN = "64467fefc9a9ec303f9ddf4c0ce6d46486504d71"
ALIGN1_COMMIT = "f25d12baea7a76e1bc5d29bf884765f16c8536ac"
RM1_COMMIT = "6a8a7bfa2ae758e944b1126881a69fef2d122dcb"
MERGE_COMMIT = "ad2d218186c8cb26af0a2fad6d3fa86a43703db5"

HANDOFFS = ROOT / "docs" / "handoffs" / "66d-delivery-acceptance"
CONTRACTS = ROOT / "docs" / "contracts" / "66d-delivery-acceptance"
RECORD = HANDOFFS / "step66d-align1-m1-canonical-merge-record.md"
MANIFEST = HANDOFFS / "step66d-align1-rm1-stage-boundary-manifest.md"
RETRY = HANDOFFS / "step66d-arch1-retry-readiness.md"
BINDING = CONTRACTS / "step66d-delivery-decision-model-binding-decisions.md"
TERMS = CONTRACTS / "step66d-canonical-terminology-registry.md"

ALIGN1_VERIFIER = ROOT / "scripts" / "verify_step66d_align1_delivery_decision_model.py"
RM1_VERIFIER = ROOT / "scripts" / "verify_step66d_align1_rm1_fixed_range_remediation.py"

# The six historical stages, with the frozen boundary each must still carry.
HISTORICAL_BOUNDARIES = {
    "scripts/verify_step66sync1_claude_code_reconciliation.py": (
        "c1db4ccbfd88fa775e4761c932835896b9b980ed",
        "828ea900d53edab6f8441f50723e52955a1049e1",
    ),
    "scripts/verify_step66sync1_final_partner_reconciliation.py": (
        "c1db4ccbfd88fa775e4761c932835896b9b980ed",
        "2396c6c7002387c886463bd38158b9ddc3bfb9e2",
    ),
    "scripts/verify_step66sync1_m1_canonicalization.py": (
        "c1db4ccbfd88fa775e4761c932835896b9b980ed",
        "1278b8944e3a8f824a9b35f82382fa8587e7989d",
    ),
    "scripts/verify_step66c4_be3_ra2m_canonicalization.py": (
        "44ab32ceab60d417ef1e0800be6cd00fc730b12e",
        "edafc0ca9111bc6dd76bc3ab59b5ea110f2f05d6",
    ),
}
RECORD_RANGE_BOUNDARIES = {
    "scripts/verify_step66sync1_m2_canonical_merge.py": (
        "7971ae0c5a5d90a186efd4c52f75988720ce214e",
        "44ab32ceab60d417ef1e0800be6cd00fc730b12e",
    ),
    "scripts/verify_step66c4_be3_ra2m2_canonical_merge.py": (
        "aa02ad5b7fa5ed3997d44420c2f2ec8a2c87c798",
        "64467fefc9a9ec303f9ddf4c0ce6d46486504d71",
    ),
}

CROSS_STAGE_FILES = tuple(
    sorted(
        {
            *HISTORICAL_BOUNDARIES,
            *RECORD_RANGE_BOUNDARIES,
            *(p.replace("scripts/verify_", "tests/test_") for p in HISTORICAL_BOUNDARIES),
            *(p.replace("scripts/verify_", "tests/test_") for p in RECORD_RANGE_BOUNDARIES),
        }
    )
)

RUNTIME_PREFIXES = ("apps/", "agents/", "services/", "shared/", "migrations/", "infra/")

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


def check01_pre_merge_main() -> None:
    if git("rev-parse", f"{PRE_MERGE_MAIN}^{{commit}}") != PRE_MERGE_MAIN:
        bad("check01: pre-merge main does not resolve")
    if not is_ancestor(PRE_MERGE_MAIN, "HEAD"):
        bad("check01: pre-merge main is not an ancestor of HEAD")


def check02_pr_head() -> None:
    if git("rev-parse", f"{RM1_COMMIT}^{{commit}}") != RM1_COMMIT:
        bad("check02: the PR head commit does not resolve")


def check03_pr_had_exactly_two_commits() -> None:
    count = git("rev-list", "--count", f"{PRE_MERGE_MAIN}..{RM1_COMMIT}")
    if count != "2":
        bad(f"check03: the merged branch carried {count} commits, expected exactly 2")


def check04_align1_commit_preserved() -> None:
    if not is_ancestor(ALIGN1_COMMIT, "HEAD"):
        bad("check04: the original ALIGN1 commit is not preserved in main history")


def check05_rm1_commit_preserved() -> None:
    if not is_ancestor(RM1_COMMIT, "HEAD"):
        bad("check05: the RM1 commit is not preserved in main history")


def check06_non_squash_two_parent_merge() -> None:
    parents = git("show", "--no-patch", "--format=%P", MERGE_COMMIT).split()
    if len(parents) != 2:
        bad(f"check06: merge commit has {len(parents)} parent(s); a non-squash merge has 2")


def check07_merge_parents_exact() -> None:
    parents = git("show", "--no-patch", "--format=%P", MERGE_COMMIT).split()
    if parents != [PRE_MERGE_MAIN, RM1_COMMIT]:
        bad(f"check07: merge parents are {parents}, expected [{PRE_MERGE_MAIN}, {RM1_COMMIT}]")


def check08_findings_closed() -> None:
    record = read(RECORD)
    for finding in ("R1-F01", "R1-F02", "R1-F03", "R1-F04", "R1-F05"):
        if not re.search(rf"{finding}:\s+CLOSED", record):
            bad(f"check08: {finding} is not recorded as CLOSED in the merge record")


def check09_r2_pass_recorded() -> None:
    if not re.search(r"R2:\s+PASS", read(RECORD)):
        bad("check09: the R2 closure verdict is not recorded as PASS")


def check10_historical_scopes_fixed() -> None:
    for rel, (base, head) in HISTORICAL_BOUNDARIES.items():
        body = read(ROOT / rel)
        if f'STAGE_BASELINE = "{base}"' not in body or f'STAGE_HEAD = "{head}"' not in body:
            bad(f"check10: {rel} no longer pins its frozen boundary")
    for rel, (base, head) in RECORD_RANGE_BOUNDARIES.items():
        body = read(ROOT / rel)
        if f'MERGE_COMMIT = "{base}"' not in body or f'RECORD_COMMIT = "{head}"' not in body:
            bad(f"check10: {rel} no longer pins its frozen merge/record range")


def check11_align1_scope_frozen() -> None:
    body = read(ALIGN1_VERIFIER)
    if f'ALIGN1_STAGE_HEAD = "{RM1_COMMIT}"' not in body:
        bad("check11: the ALIGN1 verifier does not pin its post-merge stage head")
    if '"--name-only", CANONICAL_MAIN, ALIGN1_STAGE_HEAD' not in body:
        bad("check11: the ALIGN1 positive scope is not evaluated over the frozen range")
    if f'"{PRE_MERGE_MAIN}"' not in body:
        bad("check11: the ALIGN1 verifier does not pin its baseline")


def check12_align1_thirty_four_paths() -> None:
    actual = [p for p in git("diff", "--name-only", PRE_MERGE_MAIN, RM1_COMMIT).splitlines() if p]
    if len(actual) != 34:
        bad(f"check12: the frozen ALIGN1 range yields {len(actual)} paths, expected 34")
    body = read(ALIGN1_VERIFIER)
    match = re.search(r"(?m)^ALIGN1_EXPECTED_PATHS\s*=\s*\((.*?)^\)", body, re.DOTALL)
    if not match:
        bad("check12: the ALIGN1 verifier has no registered path set")
        return
    registered = sorted(re.findall(r'"([^"]+)"', match.group(1)))
    if registered != sorted(actual):
        bad("check12: the registered ALIGN1 path set no longer equals its frozen range")


def check13_no_positive_head_endpoint() -> None:
    for rel in (*CROSS_STAGE_FILES, "scripts/verify_step66d_align1_delivery_decision_model.py"):
        body = read(ROOT / rel)
        for offender in re.findall(r'diff", "--name-only", [^)]*"HEAD"', body):
            if "RUNTIME_GUARD_ANCHOR" in offender:
                continue
            bad(f"check13: {rel} resolves a positive scope against HEAD: {offender}")


def check14_head_only_in_runtime_guard() -> None:
    for rel in CROSS_STAGE_FILES:
        body = read(ROOT / rel)
        if "RUNTIME_GUARD_ANCHOR" not in body:
            bad(f"check14: {rel} lost its runtime rejection guard")
        elif not re.search(r'"--name-only", RUNTIME_GUARD_ANCHOR, "HEAD"', body):
            bad(f"check14: {rel} runtime guard no longer scans current state")


def _acceptance_body(body: str) -> str:
    kept: list[str] = []
    skipping = False
    for line in body.splitlines():
        if "FORBIDDEN" in line and line.rstrip().endswith("("):
            skipping = True
            continue
        if skipping:
            if line.strip() == ")":
                skipping = False
            continue
        if " not in " in line or "for generic in" in line:
            continue
        kept.append(line)
    return "\n".join(kept)


def check15_to_17_no_generic_admission() -> None:
    for number, needle in (
        ("check15", '"docs/",'),
        ("check16", '"scripts/verify_step66",'),
        ("check17", '"tests/test_step66",'),
    ):
        for rel in CROSS_STAGE_FILES:
            if needle in _acceptance_body(read(ROOT / rel)):
                bad(f"{number}: {rel} reintroduced the generic admission {needle}")


def check18_runtime_guard_covers_protected_prefixes() -> None:
    for rel in CROSS_STAGE_FILES:
        body = read(ROOT / rel)
        if "RUNTIME_GUARD_ANCHOR" not in body:
            continue
        guard = body[body.index("RUNTIME_GUARD_ANCHOR") :]
        for prefix in RUNTIME_PREFIXES:
            if f'"{prefix}"' not in guard:
                bad(f"check18: {rel} runtime guard no longer names {prefix}")


def check19_decisions_binding() -> None:
    binding = read(BINDING)
    for decision in ("66D-D01", "66D-D02", "66D-D03", "66D-D04"):
        if decision not in binding:
            bad(f"check19: {decision} is missing from the binding record")
    record = read(RECORD)
    for decision in ("66D-D01", "66D-D02", "66D-D03", "66D-D04"):
        if not re.search(rf"{decision}:\s+RESOLVED / BINDING / CANONICALIZED", record):
            bad(f"check19: {decision} is not recorded as canonicalized")


def check20_legacy_delivery_package_preserved() -> None:
    changed = git("diff", "--name-only", PRE_MERGE_MAIN, RM1_COMMIT).splitlines()
    touched = [p for p in changed if "delivery_package" in p.lower() or "DeliveryPackage" in p]
    if touched:
        bad(f"check20: legacy DeliveryPackage source was modified: {', '.join(touched)}")
    if "DeliveryPackage" not in read(TERMS):
        bad("check20: the legacy DeliveryPackage entry is missing from the terminology registry")


def check21_new_aggregate_is_delivery_submission() -> None:
    if "DeliverySubmission" not in read(BINDING):
        bad("check21: DeliverySubmission is missing from the binding record")
    if "## DeliverySubmission" not in read(TERMS):
        bad("check21: DeliverySubmission has no terminology-registry entry")


def check22_arch1_not_started_or_authorized() -> None:
    if "NOT AUTHORIZED" not in read(RETRY):
        bad("check22: the retry readiness record no longer states NOT AUTHORIZED")
    record = read(RECORD)
    if "NOT STARTED / READY FOR SEPARATE PRODUCT OWNER AUTHORIZATION" not in record:
        bad("check22: the merge record does not keep Step 66D-ARCH1 unstarted and unauthorized")
    for claim in ("Step 66D-ARCH1 authorized", "ARCH1 complete", "implementation authorized"):
        if claim.lower() in re.sub(r"\s+", " ", record).lower():
            bad(f"check22: the merge record claims {claim!r}")


def check23_no_implementation_change() -> None:
    changed = [p for p in git("diff", "--name-only", PRE_MERGE_MAIN, RM1_COMMIT).splitlines() if p]
    offenders = [p for p in changed if p.startswith(RUNTIME_PREFIXES)]
    if offenders:
        bad(f"check23: runtime/source paths changed: {', '.join(sorted(offenders))}")
    infra = [
        p
        for p in changed
        if p.endswith((".yaml", ".yml", ".tsx", ".jsx", ".vue", ".sql"))
        or "docker-compose" in p
        or p.startswith(("helm/", "k8s/", "charts/"))
    ]
    if infra:
        bad(f"check23: frontend/infra paths changed: {', '.join(sorted(infra))}")


def check24_be3_gates_default_false() -> None:
    for name in ("resume_request_model.py", "replay_request_model.py"):
        path = ROOT / "shared" / "sdk" / "tasks" / name
        if not path.is_file():
            bad(f"check24: gate file missing: {name}")
            continue
        if path.read_text(encoding="utf-8").count('"false"') < 2:
            bad(f"check24: {name} no longer defaults its gates to false")


def check25_production_count_zero() -> None:
    record = read(RECORD)
    if "production_executed_true_count:           0" not in record.replace("\t", " "):
        if "production_executed_true_count" not in record or "0" not in record:
            bad("check25: the merge record does not record production_executed_true_count: 0")
    if MERGE_COMMIT not in read(MANIFEST):
        bad("check25: the boundary manifest does not record the merge commit")


def main() -> int:
    check01_pre_merge_main()
    check02_pr_head()
    check03_pr_had_exactly_two_commits()
    check04_align1_commit_preserved()
    check05_rm1_commit_preserved()
    check06_non_squash_two_parent_merge()
    check07_merge_parents_exact()
    check08_findings_closed()
    check09_r2_pass_recorded()
    check10_historical_scopes_fixed()
    check11_align1_scope_frozen()
    check12_align1_thirty_four_paths()
    check13_no_positive_head_endpoint()
    check14_head_only_in_runtime_guard()
    check15_to_17_no_generic_admission()
    check18_runtime_guard_covers_protected_prefixes()
    check19_decisions_binding()
    check20_legacy_delivery_package_preserved()
    check21_new_aggregate_is_delivery_submission()
    check22_arch1_not_started_or_authorized()
    check23_no_implementation_change()
    check24_be3_gates_default_false()
    check25_production_count_zero()

    if FAILURES:
        for failure in dict.fromkeys(FAILURES):
            print(f"VERIFY FAILED: {failure}", file=sys.stderr)
        return 1
    print(MARKER)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
