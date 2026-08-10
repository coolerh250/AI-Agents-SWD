"""Step 66D-DESIGN-M1 -- tests for the canonical merge of the Unified Control Center design.

Deterministic and read-only. Mirrors scripts/verify_step66d_design_m1_canonical_merge.py and
re-derives its facts from git and from source rather than citing the merge record.

Must run with 0 failed and 0 skipped. Starts no runtime, container or external provider.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PRE_MERGE_MAIN = "9c5210d190b82b76575ba8d456b5d2005c2867d2"
ORIGINAL_DESIGN_COMMIT = "47dcbe9feda6633e3d0835d16dcaa0866a26c2cf"
RM1_COMMIT = "c9ee13b7389f0b4977cab835337c828675a4a67d"
DESIGN_STAGE_HEAD = "bb8eab70ee7fb252329fe05c4b7039c2ed0f694b"
MERGE_COMMIT = "e4efb88bad01f72ccc73bdd0d13ff9b8e29fbda2"
# Step 66D-BE1-CR1-RM1: the DESIGN-M1 merge-record commit. What that stage changed is the
# frozen range MERGE_COMMIT..RECORD_COMMIT. Using ..HEAD here made these assertions attribute
# every later stage's commits to Step 66D-DESIGN-M1, so they failed for any subsequent commit.
RECORD_COMMIT = "af40b3bf9792fe8182e9620fb9d134af67cf4a12"

DESIGN_DIR = ROOT / "docs/design/66d-delivery-acceptance"
HANDOFF_DIR = ROOT / "docs/handoffs/66d-delivery-acceptance"

VERIFIER = ROOT / "scripts/verify_step66d_design_m1_canonical_merge.py"
DESIGN_VERIFIER = ROOT / "scripts/verify_step66d_design_unified_control_center.py"
DESIGN_TESTS = ROOT / "tests/test_step66d_design_unified_control_center.py"
MANIFEST = DESIGN_DIR / "step66d-design-contract-manifest.json"
YAML_MANIFEST = DESIGN_DIR / "step66d-design-contract-manifest.yaml"
MATRIX = DESIGN_DIR / "step66d-design-state-error-permission-matrix.md"
RECORD = HANDOFF_DIR / "step66d-design-m1-canonical-merge-record.md"
GAPS = HANDOFF_DIR / "step66d-design-gap-and-dependency-register.md"
APP_TSX = ROOT / "apps/admin-console/src/App.tsx"

EXPECTED_PATHS = {
    "docs/design/66d-delivery-acceptance/step66d-design-unified-control-center-ia.md",
    "docs/design/66d-delivery-acceptance/step66d-design-route-and-drilldown-map.md",
    "docs/design/66d-delivery-acceptance/step66d-design-delivery-inbox-spec.md",
    "docs/design/66d-delivery-acceptance/step66d-design-delivery-review-interactions.md",
    "docs/design/66d-delivery-acceptance/step66d-design-state-error-permission-matrix.md",
    "docs/design/66d-delivery-acceptance/step66d-design-wireframes.md",
    "docs/design/66d-delivery-acceptance/step66d-design-accessibility-responsive-spec.md",
    "docs/design/66d-delivery-acceptance/step66d-design-frontend-handoff.md",
    "docs/design/66d-delivery-acceptance/step66d-design-contract-manifest.json",
    "docs/handoffs/66d-delivery-acceptance/step66d-design-existing-ui-route-inventory.md",
    "docs/handoffs/66d-delivery-acceptance/step66d-design-gap-and-dependency-register.md",
    "docs/handoffs/66d-delivery-acceptance/step66d-design-evidence.md",
    "scripts/verify_step66d_design_unified_control_center.py",
    "tests/test_step66d_design_unified_control_center.py",
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


def record() -> str:
    return RECORD.read_text(encoding="utf-8")


# ------------------------------------------------------------------ merge shape
def test_verifier_passes():
    result = subprocess.run(
        [sys.executable, str(VERIFIER)], cwd=ROOT, capture_output=True, text=True, check=False
    )
    assert "STEP66D_DESIGN_M1_CANONICAL_MERGE_VERIFY: PASS" in result.stdout, result.stdout


def test_merge_is_a_two_parent_non_squash_merge():
    parents = git("show", "--no-patch", "--format=%P", MERGE_COMMIT).split()
    assert len(parents) == 2, f"not a two-parent merge: {parents}"
    assert parents == [PRE_MERGE_MAIN, DESIGN_STAGE_HEAD]


def test_all_three_design_commits_are_preserved_in_main():
    for commit in (ORIGINAL_DESIGN_COMMIT, RM1_COMMIT, DESIGN_STAGE_HEAD):
        assert is_ancestor(commit), f"{commit[:7]} was not preserved (squash/rebase would drop it)"


def test_pr_contained_exactly_three_commits():
    assert git("rev-list", "--count", f"{PRE_MERGE_MAIN}..{DESIGN_STAGE_HEAD}") == "3"


def test_merge_commit_is_an_ancestor_of_head():
    assert is_ancestor(MERGE_COMMIT)


# ------------------------------------------------------------------ scope freeze
def test_positive_scope_is_frozen_to_the_stage_range():
    source = DESIGN_VERIFIER.read_text(encoding="utf-8")
    assert f'DESIGN_STAGE_HEAD = "{DESIGN_STAGE_HEAD}"' in source
    assert 'DESIGN_POSITIVE_RANGE = f"{DESIGN_BASELINE}...{DESIGN_STAGE_HEAD}"' in source
    assert f'DESIGN_STAGE_HEAD = "{DESIGN_STAGE_HEAD}"' in DESIGN_TESTS.read_text(encoding="utf-8")


def test_no_positive_scope_endpoint_depends_on_current_head():
    source = DESIGN_VERIFIER.read_text(encoding="utf-8")
    assert (
        'f"{DESIGN_BASELINE}...HEAD"' not in source
    ), "the design verifier would drift as main advances"


def test_rejection_guard_still_scans_current_state():
    source = DESIGN_VERIFIER.read_text(encoding="utf-8")
    assert 'f"{RUNTIME_GUARD_ANCHOR}...HEAD"' in source
    assert "def current_state_paths(" in source
    scope_fn = source.split("def check_scope(")[1].split("\ndef ")[0]
    assert "current_state_paths()" in scope_fn
    assert "actual == DESIGN_EXPECTED_PATHS" in scope_fn


def test_frozen_range_resolves_to_exactly_the_registered_paths():
    changed = {
        line.strip().replace("\\", "/")
        for line in git(
            "diff", "--name-only", f"{PRE_MERGE_MAIN}...{DESIGN_STAGE_HEAD}"
        ).splitlines()
        if line.strip()
    }
    assert changed == EXPECTED_PATHS
    assert len(changed) == 14


def test_no_implementation_or_historical_path_in_the_design_scope():
    changed = {
        line.strip().replace("\\", "/")
        for line in git(
            "diff", "--name-only", f"{PRE_MERGE_MAIN}...{DESIGN_STAGE_HEAD}"
        ).splitlines()
        if line.strip()
    }
    forbidden = (
        "apps/",
        "agents/",
        "services/",
        "shared/",
        "migrations/",
        "infra/",
        "helm/",
        "k8s/",
        ".github/workflows/",
    )
    assert not [p for p in changed if p.startswith(forbidden)]
    assert not [
        p
        for p in changed
        if re.search(r"(verify|test)_step66", p) and "design_unified_control_center" not in p
    ]


# ------------------------------------------------------------------ manifest and contracts
def test_json_manifest_present_and_yaml_absent():
    assert MANIFEST.is_file()
    assert not YAML_MANIFEST.exists()
    assert isinstance(manifest(), dict)


def test_canonical_ia_and_principle_are_binding():
    data = manifest()
    assert data["canonical_ia"] == "UNIFIED_CONTROL_CENTER"
    assert data["implementation_principle"] == "UNIFIED_OVERVIEW_WITH_EXISTING_ROUTE_DRILL_DOWN"


def test_exact_enum_sets_survived_the_merge():
    data = manifest()
    assert data["review_gate_actions"] == [
        "ACCEPT",
        "REJECT",
        "REQUEST_CHANGES",
        "RERUN_QA",
        "ESCALATE",
        "ARCHIVE",
    ]
    assert data["product_owner_decisions"] == [
        "ACCEPTED",
        "ACCEPTED_WITH_FOLLOW_UP",
        "REJECTED",
    ]
    assert len(data["canonical_statuses"]) == 9


def test_counts_are_rederived_not_cited():
    data = manifest()
    assert len(data["open_gaps"]) == 16
    assert len(re.findall(r"^### (DG-\d+)", GAPS.read_text(encoding="utf-8"), re.M)) == 16
    assert len(data["frontend_inventory"]["mutation_surfaces"]) == 5
    assert len(data["required_data_states"]) == 7
    assert len(data["permission_states"]) == 6


def test_route_truthfulness_holds_against_source():
    source = {}
    for block in re.split(r"(?=<Route\s)", APP_TSX.read_text(encoding="utf-8")):
        m = re.match(r'<Route\s+path="([^"]+)"', block)
        if m:
            seg = block.split("/>")[0] if "/>" in block else block[:400]
            source[m.group(1)] = "PLACEHOLDER" if "PlaceholderPage" in seg else "REAL_PAGE"
    data = manifest()
    inventory = {r["path"]: r["classification"] for r in data["route_inventory"]["routes"]}
    for path, cls in source.items():
        assert inventory.get(path) == cls, f"{path}: manifest {inventory.get(path)} vs source {cls}"
    for path in (
        "/projects/:projectId/control-center",
        "/delivery-submissions/:deliverySubmissionId/review",
    ):
        assert path not in source, f"{path} must not exist in App.tsx"
    for path in ("/delivery-inbox", "/delivery-detail", "/dlq-retry", "/approvals"):
        assert source[path] == "PLACEHOLDER"


def test_activity_timeline_defines_all_seven_data_states():
    row = next(
        line
        for line in MATRIX.read_text(encoding="utf-8").splitlines()
        if line.lower().strip().startswith("| activity timeline")
    )
    cells = [c.strip() for c in row.strip().strip("|").split("|")]
    assert len(cells) == 8
    assert all(cells)


def test_operator_console_is_not_a_po_decision_entry_point():
    overlap = manifest()["operator_console_overlap"]
    assert overlap["existing_route"] == "/operator"
    assert "Delivery Review" in overlap["canonical_po_decision_entry_point"]
    assert overlap["fe2_coexistence_gate"]


# ------------------------------------------------------------------ record and advisories
def test_merge_record_exists_and_states_the_real_shas():
    text = record()
    for sha in (
        PRE_MERGE_MAIN,
        ORIGINAL_DESIGN_COMMIT,
        RM1_COMMIT,
        DESIGN_STAGE_HEAD,
        MERGE_COMMIT,
    ):
        assert sha in text, f"merge record does not record {sha[:7]}"


def test_r2_findings_recorded_closed():
    text = record()
    for finding in ("R2-F01", "R2-F02", "R2-F03"):
        assert finding in text
    assert "CLOSED" in text


def test_advisories_are_tracked_and_not_remediated():
    text = record()
    assert "ADV-UTF8-01" in text and "ADV-SUITE-01" in text
    adv = text.split("ADV-UTF8-01", 1)[1].split("ADV-SUITE-01")[0]
    assert "NOT REMEDIATED" in adv
    # the accurate mechanism, not the inaccurate read_text framing
    assert "subprocess.run" in adv and "encoding=" in adv
    stray = [
        s
        for s in re.split(r"(?<=\.)\s+", adv)
        if "read_text" in s and not re.search(r"\bNOT\b|\bnever\b", s)
    ]
    assert not stray, f"ADV-UTF8-01 asserts the inaccurate read_text mechanism: {stray}"


def test_no_historical_verifier_or_test_was_modified_by_this_stage():
    changed = {
        line.strip().replace("\\", "/")
        for line in git("diff", "--name-only", f"{MERGE_COMMIT}..{RECORD_COMMIT}").splitlines()
        if line.strip()
    }
    historical = [
        p
        for p in changed
        if re.search(r"(verify|test)_step66", p)
        and "design_unified_control_center" not in p
        and "design_m1_canonical_merge" not in p
    ]
    assert not historical, f"historical stage verifiers/tests modified: {historical}"


def test_production_execution_count_is_zero():
    assert manifest()["production_executed_true_count"] == 0
    assert "production_executed_true_count: 0" in record()


def test_no_implementation_slice_is_authorized():
    for key, value in manifest()["implementation_authorizations"].items():
        if isinstance(value, bool):
            assert value is False, f"{key} is True"
        elif isinstance(value, str):
            assert "NOT" in value.upper() or value.upper() in {"FALSE", "NONE"}, f"{key}={value}"


def test_merge_record_commit_touched_no_product_design_content():
    changed = {
        line.strip().replace("\\", "/")
        for line in git("diff", "--name-only", f"{MERGE_COMMIT}..{RECORD_COMMIT}").splitlines()
        if line.strip()
    }
    # An empty diff (running exactly at the merge commit) trivially satisfies this; never skip.
    design_docs = {p for p in changed if p.startswith("docs/design/66d-delivery-acceptance/")}
    assert not design_docs, f"the merge-record commit modified design content: {design_docs}"


def test_merge_record_exclusion_is_exactly_one_literal_path():
    """The M1 merge record shares the step66d-design-* prefix, so the design package's
    unregistered-document guard had to exclude it. That exclusion must be a single literal path,
    never a prefix or pattern, or Probe A / F03 would be silently weakened."""
    source = DESIGN_VERIFIER.read_text(encoding="utf-8")
    assert "MERGE_GOVERNANCE_ARTIFACTS" in source
    block = source.split("MERGE_GOVERNANCE_ARTIFACTS = frozenset(")[1].split(")")[0]
    literals = re.findall(r'"([^"]+)"', block)
    assert len(literals) == 1, f"expected exactly one excluded path, got {literals}"
    assert literals[0].endswith("/step66d-design-m1-canonical-merge-record.md"), literals[0]
    assert "{HANDOFF_DIR}" in literals[0], "the exclusion is not anchored to the handoff directory"
    for wildcard in ("*", "startswith", "glob", "fnmatch"):
        assert wildcard not in block, f"the exclusion uses a pattern ({wildcard}), not a literal"


def test_another_unregistered_design_document_is_still_rejected(tmp_path):
    """Guard the guard: a DIFFERENT step66d-design-* document must still be rejected."""
    intruder = (
        ROOT / "docs/handoffs/66d-delivery-acceptance" / "step66d-design-not-a-real-artifact.md"
    )
    assert not intruder.exists(), "test precondition: the intruder file must not already exist"
    intruder.write_text("# intruder\n", encoding="utf-8")
    try:
        result = subprocess.run(
            [sys.executable, str(DESIGN_VERIFIER)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert "STEP66D_DESIGN_UNIFIED_CONTROL_CENTER_VERIFY: FAIL" in result.stdout, (
            "an unregistered step66d-design-* document was accepted:\n" + result.stdout
        )
        assert "no_unregistered_design_document" in result.stdout
    finally:
        intruder.unlink()
    # and the tree is clean again
    assert not intruder.exists()
