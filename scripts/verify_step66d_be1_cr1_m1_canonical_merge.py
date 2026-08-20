#!/usr/bin/env python3
"""Step 66D-BE1-CR1-M1 -- canonical merge verifier for the 66D-D05 active-state contract.

Deterministic and read-only. Confirms PR #27 was merged as a non-squash two-parent merge with both
contract commits preserved, that 66D-D05 is binding with its exact predicates and deferrals, that
the CR1 positive scope is frozen to the immutable af40b3b...4fe5204 range while the rejection guard
stays HEAD-relative, that the historical DESIGN-M1 repair survived, that source/progress.md was not
touched, and that no BE1 implementation exists.

Starts no runtime, container, database or external provider.

Marker: STEP66D_BE1_CR1_M1_CANONICAL_MERGE_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys

# AT-M2 remediation: this stage's rejection window ends where an authorized successor
# milestone takes over. Without one this is HEAD, exactly as before.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
from successor_lifecycle import successor_window_end  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
MARKER = "STEP66D_BE1_CR1_M1_CANONICAL_MERGE_VERIFY"

PRE_MERGE_MAIN = "af40b3bf9792fe8182e9620fb9d134af67cf4a12"
CR1_COMMIT = "c820dfbfefbc5d33a442ed011e6ed9b5ef6c5593"
CR1_STAGE_HEAD = "4fe5204e74774d2087c69bea7358f4739122880e"
MERGE_COMMIT = "0fa1a4191a2b28340e7155dafaebea631a29c9ee"

DESIGN_M1_MERGE_COMMIT = "e4efb88bad01f72ccc73bdd0d13ff9b8e29fbda2"
DESIGN_M1_RECORD_COMMIT = "af40b3bf9792fe8182e9620fb9d134af67cf4a12"

CONTRACTS = "docs/contracts/66d-delivery-acceptance"
ARCH = "docs/architecture/66d-delivery-acceptance"
DESIGN = "docs/design/66d-delivery-acceptance"
HANDOFF = "docs/handoffs/66d-delivery-acceptance"

D05 = f"{CONTRACTS}/step66d-d05-review-task-active-state-amendment.md"
BINDING = f"{CONTRACTS}/step66d-delivery-decision-model-binding-decisions.md"
REGISTRY = f"{CONTRACTS}/step66d-canonical-terminology-registry.md"
DOMAIN = f"{ARCH}/step66d-arch1-domain-and-state-model.md"
INBOX = f"{DESIGN}/step66d-design-delivery-inbox-spec.md"
MANIFEST = f"{DESIGN}/step66d-design-contract-manifest.json"
MATRIX = f"{HANDOFF}/step66d-canonical-conflict-supersession-matrix.md"
EVIDENCE = f"{HANDOFF}/step66d-be1-cr1-active-state-contract-evidence.md"
RECORD = f"{HANDOFF}/step66d-be1-cr1-m1-canonical-merge-record.md"
CR1_VERIFIER = "scripts/verify_step66d_be1_cr1_active_state_contract.py"
CR1_TESTS = "tests/test_step66d_be1_cr1_active_state_contract.py"
M1_TEST = "tests/test_step66d_design_m1_canonical_merge.py"

CR1_EXPECTED_PATHS = frozenset(
    {
        D05,
        BINDING,
        REGISTRY,
        DOMAIN,
        INBOX,
        MANIFEST,
        MATRIX,
        EVIDENCE,
        CR1_VERIFIER,
        CR1_TESTS,
        M1_TEST,
    }
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


def manifest() -> dict:
    try:
        return json.loads(read(MANIFEST))
    except json.JSONDecodeError:
        return {}


def main() -> int:
    data = manifest()
    block = data.get("review_task_active_state", {})
    d05 = read(D05)
    binding = read(BINDING)
    domain = read(DOMAIN)
    inbox = read(INBOX)
    record = read(RECORD)
    cr1_src = read(CR1_VERIFIER)
    m1_test = read(M1_TEST)

    # --- 1-4. merge shape -----------------------------------------------------------------------
    expect(is_ancestor(PRE_MERGE_MAIN), "check01", "pre-merge main af40b3b is not an ancestor")
    expect(is_ancestor(CR1_STAGE_HEAD), "check02", "PR head 4fe5204 is not an ancestor")
    expect(
        git("rev-list", "--count", f"{PRE_MERGE_MAIN}..{CR1_STAGE_HEAD}") == "2",
        "check03",
        "the PR does not contain exactly 2 commits",
    )
    for label, commit in (("c820dfb", CR1_COMMIT), ("4fe5204", CR1_STAGE_HEAD)):
        expect(is_ancestor(commit), "check04", f"contract commit {label} was not preserved")

    parents = git("show", "--no-patch", "--format=%P", MERGE_COMMIT).split()
    expect(len(parents) == 2, "check05", f"not a two-parent merge: {parents}")
    expect(
        parents[:2] == [PRE_MERGE_MAIN, CR1_STAGE_HEAD],
        "check06",
        f"merge parents are {parents}",
    )
    expect(is_ancestor(MERGE_COMMIT), "check07", "the merge commit is not an ancestor of HEAD")

    # --- 5. 66D-D05 binding ---------------------------------------------------------------------
    expect("66D-D05" in d05 and "BINDING" in d05, "check08", "66D-D05 is not recorded as binding")
    expect("66D-D05" in binding, "check09", "the binding registry does not carry 66D-D05")
    for n in range(1, 11):
        expect(f"D05-R{n}" in binding, "check10", f"binding registry is missing D05-R{n}")

    # --- 6. predicates --------------------------------------------------------------------------
    for label, text in (("D05", d05), ("binding", binding), ("domain", domain)):
        expect("closed_at IS NULL" in text, "check11", f"{label} lacks the active predicate")
        expect("closed_at IS NOT NULL" in text, "check12", f"{label} lacks the closed predicate")
    expect(
        block.get("review_task_active_predicate") == "closed_at_is_null",
        "check13",
        f"manifest active predicate is {block.get('review_task_active_predicate')!r}",
    )
    expect(
        block.get("review_task_closed_predicate") == "closed_at_is_not_null",
        "check14",
        f"manifest closed predicate is {block.get('review_task_closed_predicate')!r}",
    )

    # --- 7. deferrals and prohibitions ----------------------------------------------------------
    expect(
        block.get("review_task_lifecycle_enum") == "deferred",
        "check15",
        "the review-task lifecycle enum is not deferred",
    )
    expect(
        block.get("submission_status_mirroring") == "forbidden",
        "check16",
        "submission-status mirroring is not forbidden",
    )
    expect(
        block.get("delivery_review_task_status") == "planned_not_implemented",
        "check17",
        "delivery_review_task_status is not planned/not implemented",
    )
    expect(
        block.get("persistence_invariant") == "at_most_one_active_per_delivery_submission_id",
        "check18",
        f"persistence invariant is {block.get('persistence_invariant')!r}",
    )
    expect(
        block.get("partial_unique_boundary") == "delivery_submission_id",
        "check19",
        "the partial unique boundary is not delivery_submission_id",
    )
    expect(
        block.get("required_existence_semantics") == "deferred",
        "check20",
        "required-existence semantics are not deferred",
    )
    expect(
        block.get("transition_semantics") == "deferred",
        "check21",
        "transition semantics are not deferred",
    )
    expect(
        block.get("closed_at_implies_decision") is False,
        "check22",
        "closed_at is not recorded as implying no decision",
    )
    expect(
        re.search(r"(?i)at most one", flat(d05)) is not None
        and re.search(r"(?i)exactly one .{0,40}always exists", flat(d05)) is None,
        "check23",
        "66D-D05 does not state AT MOST ONE, or claims a task always exists",
    )
    # No review-task lifecycle enum may be declared.
    for label, text in (("D05", d05), ("binding", binding), ("domain", domain)):
        spans = [
            (m.start(), min(len(text), m.start() + 900))
            for m in re.finditer(r"(?im)^.*DeliveryReviewTask.*$", text)
        ]
        for value in ("OPEN", "IN_PROGRESS", "CLOSED", "CANCELLED", "PENDING", "ACTIVE"):
            for m in re.finditer(rf"\b{value}\b", text):
                if not any(s <= m.start() < e for s, e in spans):
                    continue
                if text[m.end() : m.end() + 6].upper().startswith(("-STATE", "_STATE")):
                    continue
                window = flat(text[max(0, m.start() - 320) : m.end() + 320]).upper()
                expect(
                    any(
                        cue in window
                        for cue in (
                            "MUST NOT",
                            "NOT DEFINED",
                            "FORBIDDEN",
                            "DEFERRED",
                            "ACCEPTANCEFOLLOWUPITEM",
                            "NEVER",
                            "NOT BE INTRODUCED",
                            "NOT BE REUSED",
                            "IS NOT THE VALUE",
                        )
                    ),
                    "check24",
                    f"{label} may declare {value} as a DeliveryReviewTask lifecycle value",
                )

    # --- 8. supersession preserved --------------------------------------------------------------
    expect("SUPERSEDED BY 66D-D05" in domain, "check25", "ARCH1 is not marked superseded")
    expect(
        "mirrors submission review state" in domain,
        "check26",
        "the original ARCH1 sentence was deleted instead of annotated",
    )
    expect(
        "not interchangeable" in flat(inbox).lower(),
        "check27",
        "the DESIGN non-interchangeability requirement was removed",
    )

    # --- 9. frozen CR1 positive scope -----------------------------------------------------------
    expect(
        f'CR1_STAGE_HEAD = "{CR1_STAGE_HEAD}"' in cr1_src
        and 'CR1_POSITIVE_RANGE = f"{CR1_BASELINE}...{CR1_STAGE_HEAD}"' in cr1_src,
        "check28",
        "the CR1 verifier does not freeze its positive scope to af40b3b...4fe5204",
    )
    expect(
        'f"{CR1_BASELINE}...HEAD"' not in cr1_src,
        "check29",
        "the CR1 verifier still uses current HEAD as a positive scope endpoint",
    )
    expect(
        "CR1_RUNTIME_GUARD_ANCHOR" in cr1_src and 'f"{CR1_RUNTIME_GUARD_ANCHOR}...HEAD"' in cr1_src,
        "check30",
        "the current-state rejection guard no longer scans HEAD",
    )
    changed = {
        line.strip().replace("\\", "/")
        for line in git("diff", "--name-only", f"{PRE_MERGE_MAIN}...{CR1_STAGE_HEAD}").splitlines()
        if line.strip()
    }
    expect(
        changed == CR1_EXPECTED_PATHS,
        "check31",
        f"frozen range != registry; missing={sorted(CR1_EXPECTED_PATHS - changed)} "
        f"unexpected={sorted(changed - CR1_EXPECTED_PATHS)}",
    )
    expect(len(changed) == 11, "check32", f"the frozen range resolves to {len(changed)} paths")
    historical = sorted(
        p
        for p in changed
        if re.search(r"(verify|test)_step66", p) and "be1_cr1_active_state_contract" not in p
    )
    expect(
        historical == [M1_TEST],
        "check33",
        f"historical exception is {historical}, expected exactly [{M1_TEST}]",
    )
    expect(
        not sorted(p for p in changed if p.startswith(FORBIDDEN_PREFIXES)),
        "check34",
        "implementation/runtime paths are inside the contract scope",
    )
    expect("source/progress.md" not in changed, "check35", "source/progress.md is inside the scope")

    # --- 10. historical DESIGN-M1 repair preserved ----------------------------------------------
    expect(
        f'RECORD_COMMIT = "{DESIGN_M1_RECORD_COMMIT}"' in m1_test
        and 'f"{MERGE_COMMIT}..{RECORD_COMMIT}"' in m1_test,
        "check36",
        "the DESIGN-M1 frozen record range was lost",
    )
    expect(
        'f"{MERGE_COMMIT}..HEAD"' not in m1_test,
        "check37",
        "the DESIGN-M1 drifting HEAD range came back",
    )
    expect(
        f'MERGE_COMMIT = "{DESIGN_M1_MERGE_COMMIT}"' in m1_test,
        "check38",
        "the DESIGN-M1 merge commit constant changed",
    )

    # --- 11. progress.md untouched by the merge-record commit -----------------------------------
    since_merge = {
        line.strip().replace("\\", "/")
        for line in git(
            "diff", "--name-only",
            f"{MERGE_COMMIT}..{successor_window_end(MERGE_COMMIT)}"
        ).splitlines()
        if line.strip()
    }
    expect(
        "source/progress.md" not in since_merge,
        "check39",
        "the merge-record commit modified source/progress.md (ADV-DRIFT-PROGRESS-01)",
    )
    expect(
        not sorted(p for p in since_merge if p.startswith(FORBIDDEN_PREFIXES)),
        "check40",
        "the merge-record commit touched implementation or runtime paths",
    )

    # --- 12. advisories tracked only -------------------------------------------------------------
    for advisory in ("ADV-DRIFT-PROGRESS-01", "ADV-UTF8-01", "ADV-SUITE-01"):
        expect(advisory in record, "check41", f"{advisory} is not recorded in the merge record")
    expect(
        "NOT REMEDIATED" in record,
        "check42",
        "the merge record does not state the advisories were not remediated",
    )

    # --- 13. no BE1 implementation ---------------------------------------------------------------
    expect(
        not list((ROOT / "migrations").glob("*delivery_review_task*")),
        "check43",
        "a delivery review task migration exists",
    )
    expect(
        not list((ROOT / "migrations").glob("*delivery_submission*")),
        "check44",
        "a delivery submission migration exists",
    )
    expect(
        not (ROOT / "shared/sdk/delivery_acceptance").exists(),
        "check45",
        "a delivery acceptance package exists",
    )
    expect(
        "production_executed_true_count: 0" in record,
        "check46",
        "the merge record does not state production_executed_true_count: 0",
    )
    expect(
        data.get("production_executed_true_count") == 0,
        "check47",
        "manifest production_executed_true_count != 0",
    )

    print(f"  checks_run={checks_run}")
    if failures:
        print(f"{MARKER}: FAIL")
        return 1
    print("  [OK] PR #27 merged as a non-squash two-parent merge; both contract commits preserved;")
    print("       66D-D05 BINDING with active := closed_at IS NULL and closed := closed_at IS NOT")
    print("       NULL; lifecycle enum deferred; submission mirroring forbidden; at-most-one per")
    print("       delivery_submission_id; required existence and transitions deferred; ARCH1")
    print("       superseded in place and DESIGN distinction preserved; CR1 positive scope frozen")
    print("       to af40b3b...4fe5204 with an exact 11-path registry and one literal historical")
    print("       exception; rejection guard still current-state; DESIGN-M1 repair intact;")
    print("       source/progress.md untouched; no BE1 implementation; prod_exec=0")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
