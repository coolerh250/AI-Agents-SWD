"""Step 66D-BE1-CR1-M1 -- tests for the canonical merge of the 66D-D05 active-state contract.

Deterministic and read-only. Mirrors scripts/verify_step66d_be1_cr1_m1_canonical_merge.py and
re-derives its facts from git, the manifest and source rather than citing the merge record.

Must run with 0 failed and 0 skipped. Starts no runtime, container or external provider.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
import pathlib

# AT-M2 remediation: the rejection window ends where an authorized successor milestone
# takes over; without one this is HEAD, exactly as before.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
try:
    from successor_lifecycle import successor_window_end  # noqa: E402
except ModuleNotFoundError:  # isolated probe copies may not carry scripts/

    def successor_window_end(_baseline: str = "") -> str:
        """Strictest fallback: with no lifecycle module the window stays HEAD-relative."""
        return "HEAD"

ROOT = Path(__file__).resolve().parents[1]

PRE_MERGE_MAIN = "af40b3bf9792fe8182e9620fb9d134af67cf4a12"
CR1_COMMIT = "c820dfbfefbc5d33a442ed011e6ed9b5ef6c5593"
CR1_STAGE_HEAD = "4fe5204e74774d2087c69bea7358f4739122880e"
MERGE_COMMIT = "0fa1a4191a2b28340e7155dafaebea631a29c9ee"

DESIGN_M1_MERGE_COMMIT = "e4efb88bad01f72ccc73bdd0d13ff9b8e29fbda2"
DESIGN_M1_RECORD_COMMIT = "af40b3bf9792fe8182e9620fb9d134af67cf4a12"

CONTRACTS = ROOT / "docs/contracts/66d-delivery-acceptance"
ARCH = ROOT / "docs/architecture/66d-delivery-acceptance"
DESIGN = ROOT / "docs/design/66d-delivery-acceptance"
HANDOFF = ROOT / "docs/handoffs/66d-delivery-acceptance"

VERIFIER = ROOT / "scripts/verify_step66d_be1_cr1_m1_canonical_merge.py"
CR1_VERIFIER = ROOT / "scripts/verify_step66d_be1_cr1_active_state_contract.py"
D05 = CONTRACTS / "step66d-d05-review-task-active-state-amendment.md"
BINDING = CONTRACTS / "step66d-delivery-decision-model-binding-decisions.md"
DOMAIN = ARCH / "step66d-arch1-domain-and-state-model.md"
INBOX = DESIGN / "step66d-design-delivery-inbox-spec.md"
MANIFEST = DESIGN / "step66d-design-contract-manifest.json"
RECORD = HANDOFF / "step66d-be1-cr1-m1-canonical-merge-record.md"
M1_TEST = ROOT / "tests/test_step66d_design_m1_canonical_merge.py"

EXPECTED_PATHS = {
    "docs/contracts/66d-delivery-acceptance/step66d-d05-review-task-active-state-amendment.md",
    "docs/contracts/66d-delivery-acceptance/step66d-delivery-decision-model-binding-decisions.md",
    "docs/contracts/66d-delivery-acceptance/step66d-canonical-terminology-registry.md",
    "docs/architecture/66d-delivery-acceptance/step66d-arch1-domain-and-state-model.md",
    "docs/design/66d-delivery-acceptance/step66d-design-delivery-inbox-spec.md",
    "docs/design/66d-delivery-acceptance/step66d-design-contract-manifest.json",
    "docs/handoffs/66d-delivery-acceptance/step66d-canonical-conflict-supersession-matrix.md",
    "docs/handoffs/66d-delivery-acceptance/step66d-be1-cr1-active-state-contract-evidence.md",
    "scripts/verify_step66d_be1_cr1_active_state_contract.py",
    "tests/test_step66d_be1_cr1_active_state_contract.py",
    "tests/test_step66d_design_m1_canonical_merge.py",
}


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


def manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def block() -> dict:
    return manifest()["review_task_active_state"]


def successor_range(baseline: str) -> str:
    """``baseline``..window end -- HEAD unless an authorized successor took over."""
    return f"{baseline}..{successor_window_end(baseline)}"


def changed_in(rev_range: str) -> set[str]:
    return {
        line.strip().replace("\\", "/")
        for line in git("diff", "--name-only", rev_range).splitlines()
        if line.strip()
    }


# ------------------------------------------------------------------ merge shape
def test_verifier_passes():
    result = subprocess.run(
        [sys.executable, str(VERIFIER)], cwd=ROOT, capture_output=True, text=True, check=False
    )
    assert "STEP66D_BE1_CR1_M1_CANONICAL_MERGE_VERIFY: PASS" in result.stdout, result.stdout


def test_merge_is_two_parent_non_squash():
    parents = git("show", "--no-patch", "--format=%P", MERGE_COMMIT).split()
    assert len(parents) == 2, f"not a two-parent merge: {parents}"
    assert parents == [PRE_MERGE_MAIN, CR1_STAGE_HEAD]


def test_both_contract_commits_preserved():
    for commit in (CR1_COMMIT, CR1_STAGE_HEAD):
        assert is_ancestor(commit), f"{commit[:7]} was dropped (squash or rebase would do this)"


def test_pr_contained_exactly_two_commits():
    assert git("rev-list", "--count", f"{PRE_MERGE_MAIN}..{CR1_STAGE_HEAD}") == "2"


def test_merge_commit_is_ancestor_of_head():
    assert is_ancestor(MERGE_COMMIT)


# ------------------------------------------------------------------ D05 semantics
def test_d05_is_binding_with_ten_requirements():
    d05 = D05.read_text(encoding="utf-8")
    binding = BINDING.read_text(encoding="utf-8")
    assert "66D-D05" in d05 and "BINDING" in d05
    for n in range(1, 11):
        assert f"D05-R{n}" in binding, f"missing D05-R{n}"


def test_predicates_are_structural_everywhere():
    for path in (D05, BINDING, DOMAIN):
        text = path.read_text(encoding="utf-8")
        assert "closed_at IS NULL" in text, path.name
        assert "closed_at IS NOT NULL" in text, path.name


def test_manifest_block_is_exact():
    b = block()
    assert b["decision_id"] == "66D-D05"
    assert b["review_task_active_predicate"] == "closed_at_is_null"
    assert b["review_task_closed_predicate"] == "closed_at_is_not_null"
    assert b["review_task_lifecycle_enum"] == "deferred"
    assert b["submission_status_mirroring"] == "forbidden"
    assert b["delivery_review_task_status"] == "planned_not_implemented"
    assert b["persistence_invariant"] == "at_most_one_active_per_delivery_submission_id"
    assert b["partial_unique_boundary"] == "delivery_submission_id"
    assert b["required_existence_semantics"] == "deferred"
    assert b["transition_semantics"] == "deferred"
    assert b["closed_at_implies_decision"] is False


def test_at_most_one_never_exactly_one():
    flat = re.sub(r"\s+", " ", D05.read_text(encoding="utf-8"))
    assert re.search(r"(?i)at most one", flat)
    assert not re.search(r"(?i)exactly one .{0,40}always exists", flat)


def test_no_review_task_lifecycle_enum_declared():
    text = D05.read_text(encoding="utf-8")
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
            window = re.sub(r"\s+", " ", text[max(0, m.start() - 320) : m.end() + 320]).upper()
            assert any(
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
            ), f"{value} may be declared as a DeliveryReviewTask lifecycle value"


def test_arch1_superseded_and_design_preserved():
    domain = DOMAIN.read_text(encoding="utf-8")
    assert "SUPERSEDED BY 66D-D05" in domain
    assert "mirrors submission review state" in domain, "the original sentence was deleted"
    assert "not interchangeable" in INBOX.read_text(encoding="utf-8").lower()


# ------------------------------------------------------------------ scope freeze
def test_cr1_positive_scope_is_frozen():
    source = CR1_VERIFIER.read_text(encoding="utf-8")
    assert f'CR1_STAGE_HEAD = "{CR1_STAGE_HEAD}"' in source
    assert 'CR1_POSITIVE_RANGE = f"{CR1_BASELINE}...{CR1_STAGE_HEAD}"' in source
    assert 'f"{CR1_BASELINE}...HEAD"' not in source


def test_cr1_rejection_guard_still_scans_current_state():
    source = CR1_VERIFIER.read_text(encoding="utf-8")
    assert "CR1_RUNTIME_GUARD_ANCHOR" in source
    assert 'f"{CR1_RUNTIME_GUARD_ANCHOR}...HEAD"' in source
    assert "scanned = current_state or changed" in source


def test_frozen_range_is_exactly_eleven_registered_paths():
    changed = changed_in(f"{PRE_MERGE_MAIN}...{CR1_STAGE_HEAD}")
    assert changed == EXPECTED_PATHS
    assert len(changed) == 11


def test_exactly_one_historical_exception():
    changed = changed_in(f"{PRE_MERGE_MAIN}...{CR1_STAGE_HEAD}")
    historical = sorted(
        p
        for p in changed
        if re.search(r"(verify|test)_step66", p) and "be1_cr1_active_state_contract" not in p
    )
    assert historical == ["tests/test_step66d_design_m1_canonical_merge.py"]


def test_no_implementation_path_in_contract_scope():
    changed = changed_in(f"{PRE_MERGE_MAIN}...{CR1_STAGE_HEAD}")
    forbidden = (
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
    assert not [p for p in changed if p.startswith(forbidden)]


# ------------------------------------------------------------------ historical repair carried in
def test_design_m1_frozen_range_survived_the_merge():
    text = M1_TEST.read_text(encoding="utf-8")
    assert f'MERGE_COMMIT = "{DESIGN_M1_MERGE_COMMIT}"' in text
    assert f'RECORD_COMMIT = "{DESIGN_M1_RECORD_COMMIT}"' in text
    assert 'f"{MERGE_COMMIT}..{RECORD_COMMIT}"' in text
    assert 'f"{MERGE_COMMIT}..HEAD"' not in text


# ------------------------------------------------------------------ progress.md and advisories
def test_progress_file_untouched_by_this_stage():
    """ADV-DRIFT-PROGRESS-01: three historical suites still diff progress.md against HEAD."""
    assert "source/progress.md" not in changed_in(f"{PRE_MERGE_MAIN}...{CR1_STAGE_HEAD}")
    assert "source/progress.md" not in changed_in(successor_range(MERGE_COMMIT))


def test_merge_record_tracks_advisories_without_remediating():
    text = RECORD.read_text(encoding="utf-8")
    for advisory in ("ADV-DRIFT-PROGRESS-01", "ADV-UTF8-01", "ADV-SUITE-01"):
        assert advisory in text
    assert "NOT REMEDIATED" in text


def test_merge_record_states_the_real_shas():
    text = RECORD.read_text(encoding="utf-8")
    for sha in (PRE_MERGE_MAIN, CR1_COMMIT, CR1_STAGE_HEAD, MERGE_COMMIT):
        assert sha in text, f"merge record does not record {sha[:7]}"


# ------------------------------------------------------------------ no implementation
def test_no_be1_implementation_exists():
    assert not list((ROOT / "migrations").glob("*delivery_review_task*"))
    assert not list((ROOT / "migrations").glob("*delivery_submission*"))
    assert not (ROOT / "shared/sdk/delivery_acceptance").exists()


def test_merge_record_commit_touched_no_implementation():
    changed = changed_in(successor_range(MERGE_COMMIT))
    forbidden = (
        "apps/",
        "agents/",
        "services/",
        "shared/",
        "migrations/",
        "infra/",
        "runtime/",
    )
    assert not [p for p in changed if p.startswith(forbidden)]


def test_production_execution_count_is_zero():
    assert manifest()["production_executed_true_count"] == 0
    assert "production_executed_true_count: 0" in RECORD.read_text(encoding="utf-8")
