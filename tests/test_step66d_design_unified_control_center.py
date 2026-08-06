"""Step 66D-DESIGN (+ RM1) -- tests for the Unified Control Center UX/IA design package.

Deterministic, read-only positive checks plus RM1 negative mutation probes. Each probe copies the
repository state into a temporary directory, tampers with exactly one thing, and asserts the
verifier REJECTS it. No probe is ever committed and no probe touches the working tree.

Must run with 0 failed and 0 skipped. Starts no runtime, container or external provider.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DESIGN_BASELINE = "9c5210d190b82b76575ba8d456b5d2005c2867d2"

DESIGN_DIR = ROOT / "docs/design/66d-delivery-acceptance"
HANDOFF_DIR = ROOT / "docs/handoffs/66d-delivery-acceptance"
VERIFIER = ROOT / "scripts/verify_step66d_design_unified_control_center.py"
TEST_FILE = ROOT / "tests/test_step66d_design_unified_control_center.py"

IA = DESIGN_DIR / "step66d-design-unified-control-center-ia.md"
ROUTES_DOC = DESIGN_DIR / "step66d-design-route-and-drilldown-map.md"
INBOX = DESIGN_DIR / "step66d-design-delivery-inbox-spec.md"
REVIEW = DESIGN_DIR / "step66d-design-delivery-review-interactions.md"
MATRIX = DESIGN_DIR / "step66d-design-state-error-permission-matrix.md"
WIRE = DESIGN_DIR / "step66d-design-wireframes.md"
A11Y = DESIGN_DIR / "step66d-design-accessibility-responsive-spec.md"
HANDOFF = DESIGN_DIR / "step66d-design-frontend-handoff.md"
MANIFEST = DESIGN_DIR / "step66d-design-contract-manifest.json"
INVENTORY = HANDOFF_DIR / "step66d-design-existing-ui-route-inventory.md"
GAPS = HANDOFF_DIR / "step66d-design-gap-and-dependency-register.md"
EVIDENCE = HANDOFF_DIR / "step66d-design-evidence.md"

ALL_DOCS = [IA, ROUTES_DOC, INBOX, REVIEW, MATRIX, WIRE, A11Y, HANDOFF, INVENTORY, GAPS, EVIDENCE]

REVIEW_ACTIONS = ["ACCEPT", "REJECT", "REQUEST_CHANGES", "RERUN_QA", "ESCALATE", "ARCHIVE"]
PO_DECISIONS = ["ACCEPTED", "ACCEPTED_WITH_FOLLOW_UP", "REJECTED"]
STATUSES = [
    "DRAFT",
    "SUBMITTED",
    "UNDER_REVIEW",
    "CHANGES_REQUESTED",
    "QA_RERUN_REQUESTED",
    "ACCEPTED",
    "REJECTED",
    "ARCHIVED",
    "EXPIRED",
]


def manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


# --------------------------------------------------------------------- positive
def test_manifest_is_valid_json_and_yaml_manifest_is_gone():
    assert MANIFEST.is_file()
    data = manifest()
    assert isinstance(data, dict)
    assert not (DESIGN_DIR / "step66d-design-contract-manifest.yaml").exists()
    raw = MANIFEST.read_text(encoding="utf-8")
    assert "//" not in raw.split('"', 1)[0]
    assert not re.search(r",\s*[}\]]", raw), "trailing comma in JSON"


def test_all_registered_artifacts_exist():
    for path in [*ALL_DOCS, MANIFEST, VERIFIER]:
        assert path.is_file(), f"missing {path.relative_to(ROOT)}"


def test_ia_enums_are_exact():
    data = manifest()
    assert data["canonical_ia"] == "UNIFIED_CONTROL_CENTER"
    assert data["implementation_principle"] == "UNIFIED_OVERVIEW_WITH_EXISTING_ROUTE_DRILL_DOWN"
    assert data["ia_decision"]["non_selected_alternative"] == "COORDINATED_EXISTING_ROUTES"


def test_exact_enum_sets():
    data = manifest()
    assert data["review_gate_actions"] == REVIEW_ACTIONS
    assert data["product_owner_decisions"] == PO_DECISIONS
    assert sorted(data["canonical_statuses"]) == sorted(STATUSES)
    assert "ACCEPTED_WITH_FOLLOW_UP" not in data["review_gate_actions"]
    for forbidden in ("REQUEST_CHANGES", "RERUN_QA", "ESCALATE", "ARCHIVE"):
        assert forbidden not in data["product_owner_decisions"]


def test_data_states_and_permission_states_are_separate():
    data = manifest()
    assert set(data["required_data_states"]) == {
        "loading",
        "empty",
        "partial",
        "stale",
        "inaccessible",
        "error",
        "unknown",
    }
    assert set(data["permission_states"]) == {
        "authorized",
        "not_authorized",
        "identity_not_verified",
        "capability_unavailable",
        "read_only_observer",
        "future_shared_runtime_required",
    }
    assert data["state_matrix"]["activity_timeline_has_unknown_state"] is True
    assert data["state_matrix"]["unknown_is_distinct_from_error"] is True


def test_activity_timeline_row_has_seven_populated_state_cells():
    row = next(
        line
        for line in MATRIX.read_text(encoding="utf-8").splitlines()
        if line.lower().startswith("| activity timeline")
    )
    cells = [c.strip() for c in row.strip().strip("|").split("|")]
    assert len(cells) == 8, f"expected section + 7 states, got {len(cells)}"
    assert all(cells), "empty state cell in the Activity Timeline row"
    assert "unknown" in cells[7].lower()


def test_mutation_surface_inventory_is_five_and_semantic():
    data = manifest()
    surfaces = {m["source_path"] for m in data["frontend_inventory"]["mutation_surfaces"]}
    assert surfaces == {
        "apps/admin-console/src/pages/TaskNew.tsx",
        "apps/admin-console/src/pages/TaskDetail.tsx",
        "apps/admin-console/src/pages/TaskWorkroom.tsx",
        "apps/admin-console/src/pages/MultiProjectDelivery.tsx",
        "apps/admin-console/src/pages/OperatorConsole.tsx",
    }
    assert data["frontend_inventory"]["mutation_surface_count"] == 5
    for excluded in (
        "BackupDr.tsx",
        "IdentityPosture.tsx",
        "RuntimeBaseline.tsx",
        "SecurityPosture.tsx",
    ):
        assert not any(excluded in s for s in surfaces)


def test_operator_console_duplication_analysis_present():
    data = manifest()
    overlap = data["operator_console_overlap"]
    assert overlap["existing_route"] == "/operator"
    assert "OperatorReviewPanel" in overlap["existing_analogue_component"]
    assert "Delivery Review" in overlap["canonical_po_decision_entry_point"]
    assert overlap["fe2_coexistence_gate"]
    assert "OperatorReviewPanel" in ROUTES_DOC.read_text(encoding="utf-8")


def test_inbox_filter_terminology_disambiguated():
    data = manifest()
    names = {f["name"] for f in data["inbox_filters"]}
    assert {"delivery_review_task_status", "delivery_submission_status"} <= names
    text = INBOX.read_text(encoding="utf-8")
    assert "delivery_review_task_status" in text
    assert "delivery_submission_status" in text
    for entry in data["inbox_filters"]:
        for field in (
            "source_field",
            "enum_source",
            "display_label",
            "missing_data_behavior",
            "backend_dependency",
        ):
            assert entry.get(field), f"{entry['name']} missing {field}"


def test_planned_routes_absent_and_placeholders_not_functional():
    data = manifest()
    by_path = {r["path"]: r for r in data["route_inventory"]["routes"]}
    for path in (
        "/projects/:projectId/control-center",
        "/delivery-submissions/:deliverySubmissionId/review",
    ):
        assert path not in by_path
    for path in ("/delivery-inbox", "/delivery-detail"):
        assert by_path[path]["classification"] == "PLACEHOLDER"


def test_no_implementation_authorized():
    auth = manifest()["implementation_authorizations"]
    assert auth["codex_authorized"] is False
    assert "NOT GRANTED" in auth["merge_authorization"].upper()
    assert auth["task_roles_modified"] is False
    assert auth["adr_66d_09_modified"] is False
    assert manifest()["production_executed_true_count"] == 0


def test_verifier_passes_on_current_state():
    result = subprocess.run(
        [sys.executable, str(VERIFIER)], cwd=ROOT, capture_output=True, text=True, check=False
    )
    assert "STEP66D_DESIGN_UNIFIED_CONTROL_CENTER_VERIFY: PASS" in result.stdout, result.stdout
    assert result.returncode == 0


def test_verifier_reports_split_stable_metrics():
    result = subprocess.run(
        [sys.executable, str(VERIFIER)], cwd=ROOT, capture_output=True, text=True, check=False
    )
    assert re.search(r"CHECK_DEFINITIONS=\d+", result.stdout)
    assert re.search(r"ASSERTIONS_EXECUTED=\d+", result.stdout)
    definitions = int(re.search(r"CHECK_DEFINITIONS=(\d+)", result.stdout).group(1))
    executed = int(re.search(r"ASSERTIONS_EXECUTED=(\d+)", result.stdout).group(1))
    assert definitions > 0 and executed >= definitions


def test_verifier_emits_rm1_closure_sections():
    result = subprocess.run(
        [sys.executable, str(VERIFIER)], cwd=ROOT, capture_output=True, text=True, check=False
    )
    for marker in (
        "DESIGN_RM1_SCOPE_EXACT",
        "DESIGN_RM1_SOURCE_COUNTS",
        "DESIGN_RM1_ENUM_INTEGRITY",
        "DESIGN_RM1_ROUTE_TRUTHFULNESS",
        "DESIGN_RM1_REGRESSION_CLOSURE",
    ):
        assert f"{marker}: PASS" in result.stdout, result.stdout


# --------------------------------------------------------------------- probes
def _probe_copy(tmp: Path) -> Path:
    """Copy the design package + verifier into a disposable tree with a git history.

    The probe tree is a real git repo whose baseline commit contains the frontend source, so the
    verifier's exact-scope diff behaves the same way it does in the real repository.
    """
    work = tmp / "repo"
    (work / "scripts").mkdir(parents=True)
    (work / "docs/design/66d-delivery-acceptance").mkdir(parents=True)
    (work / "docs/handoffs/66d-delivery-acceptance").mkdir(parents=True)
    shutil.copytree(ROOT / "apps/admin-console/src", work / "apps/admin-console/src")
    subprocess.run(["git", "init", "-q"], cwd=work, check=True)
    subprocess.run(["git", "config", "user.email", "probe@example.invalid"], cwd=work, check=True)
    subprocess.run(["git", "config", "user.name", "probe"], cwd=work, check=True)
    subprocess.run(["git", "add", "-A"], cwd=work, check=True)
    subprocess.run(["git", "commit", "-qm", "baseline"], cwd=work, check=True)
    base = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=work, capture_output=True, text=True, check=True
    ).stdout.strip()
    (work / "tests").mkdir(parents=True, exist_ok=True)
    for path in [*ALL_DOCS, MANIFEST, TEST_FILE]:
        shutil.copy2(path, work / path.relative_to(ROOT))
    verifier = work / "scripts/verify_step66d_design_unified_control_center.py"
    shutil.copy2(VERIFIER, verifier)
    # Re-point ONLY the scope diff base at the probe's synthetic baseline commit. DESIGN_BASELINE
    # itself is left untouched so the baseline.recorded string checks still exercise the real value.
    verifier.write_text(
        verifier.read_text(encoding="utf-8").replace(
            '["git", "diff", "--name-only", f"{DESIGN_BASELINE}...HEAD"]',
            f'["git", "diff", "--name-only", "{base}...HEAD"]',
        ),
        encoding="utf-8",
    )
    return work


def _run_probe(work: Path) -> subprocess.CompletedProcess:
    subprocess.run(["git", "add", "-A"], cwd=work, check=True)
    subprocess.run(["git", "commit", "-qm", "probe"], cwd=work, check=True)
    return subprocess.run(
        [sys.executable, "scripts/verify_step66d_design_unified_control_center.py"],
        cwd=work,
        capture_output=True,
        text=True,
        check=False,
    )


def _assert_rejected(result: subprocess.CompletedProcess, label: str) -> None:
    assert result.returncode != 0, f"{label}: verifier did NOT reject\n{result.stdout}"
    assert "STEP66D_DESIGN_UNIFIED_CONTROL_CENTER_VERIFY: FAIL" in result.stdout, result.stdout


def test_probe_baseline_copy_passes(tmp_path):
    """The untampered probe copy must PASS, so every rejection below is attributable."""
    work = _probe_copy(tmp_path)
    result = _run_probe(work)
    assert "STEP66D_DESIGN_UNIFIED_CONTROL_CENTER_VERIFY: PASS" in result.stdout, result.stdout


@pytest.mark.parametrize(
    "label,relpath,content",
    [
        (
            "unregistered design document",
            "docs/design/66d-delivery-acceptance/unregistered-probe.md",
            "# probe\n",
        ),
        (
            "frontend implementation",
            "apps/admin-console/src/pages/UnifiedControlCenterProbe.tsx",
            "export function UnifiedControlCenterProbe() { return null; }\n",
        ),
    ],
)
def test_probe_unregistered_or_frontend_path_is_rejected(tmp_path, label, relpath, content):
    work = _probe_copy(tmp_path)
    target = work / relpath
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    _assert_rejected(_run_probe(work), label)


@pytest.mark.parametrize(
    "label,key,value",
    [
        (
            "extra review action",
            "review_gate_actions",
            ["ACCEPT", "REJECT", "REQUEST_CHANGES", "RERUN_QA", "ESCALATE", "ARCHIVE", "DEFER"],
        ),
        (
            "extra PO decision",
            "product_owner_decisions",
            ["ACCEPTED", "ACCEPTED_WITH_FOLLOW_UP", "REJECTED", "APPROVED"],
        ),
        ("extra canonical status", "canonical_statuses", STATUSES + ["DONE"]),
        ("IA set to the non-selected alternative", "canonical_ia", "COORDINATED_EXISTING_ROUTES"),
        ("IA set to unresolved", "canonical_ia", "UNRESOLVED"),
    ],
)
def test_probe_manifest_enum_tampering_is_rejected(tmp_path, label, key, value):
    work = _probe_copy(tmp_path)
    path = work / MANIFEST.relative_to(ROOT)
    data = json.loads(path.read_text(encoding="utf-8"))
    data[key] = value
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    _assert_rejected(_run_probe(work), label)


def test_probe_semantic_open_decision_wording_is_rejected(tmp_path):
    work = _probe_copy(tmp_path)
    path = work / IA.relative_to(ROOT)
    path.write_text(
        path.read_text(encoding="utf-8") + "\n\nThe IA decision remains open.\n", encoding="utf-8"
    )
    _assert_rejected(_run_probe(work), "semantic open-decision wording")


@pytest.mark.parametrize(
    "label,mutate",
    [
        (
            "route count tampering",
            lambda d: d["route_inventory"].__setitem__(
                "total_routes", d["route_inventory"]["total_routes"] + 1
            ),
        ),
        (
            "nav count tampering",
            lambda d: d["navigation_inventory"].__setitem__(
                "nav_items", d["navigation_inventory"]["nav_items"] + 1
            ),
        ),
        (
            "badge count tampering",
            lambda d: d["navigation_inventory"]["badges"].__setitem__("soon", 99),
        ),
        (
            "mutation count tampering",
            lambda d: d["frontend_inventory"].__setitem__("mutation_surface_count", 7),
        ),
        (
            "gap count tampering",
            lambda d: d["open_gaps"].append({"id": "DG-99", "title": "phantom", "severity": "LOW"}),
        ),
    ],
)
def test_probe_count_tampering_is_rejected(tmp_path, label, mutate):
    work = _probe_copy(tmp_path)
    path = work / MANIFEST.relative_to(ROOT)
    data = json.loads(path.read_text(encoding="utf-8"))
    mutate(data)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    _assert_rejected(_run_probe(work), label)


def test_probe_fake_implemented_route_is_rejected(tmp_path):
    work = _probe_copy(tmp_path)
    path = work / MANIFEST.relative_to(ROOT)
    data = json.loads(path.read_text(encoding="utf-8"))
    for entry in data["route_inventory"]["planned_absent_routes"]:
        if entry["path"] == "/projects/:projectId/control-center":
            entry["classification"] = "IMPLEMENTED"
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    _assert_rejected(_run_probe(work), "fake implemented control-center route")


def test_probe_placeholder_marked_functional_is_rejected(tmp_path):
    work = _probe_copy(tmp_path)
    path = work / MANIFEST.relative_to(ROOT)
    data = json.loads(path.read_text(encoding="utf-8"))
    for entry in data["route_inventory"]["routes"]:
        if entry["path"] == "/delivery-inbox":
            entry["classification"] = "REAL_PAGE"
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    _assert_rejected(_run_probe(work), "placeholder marked functional")


def test_probe_missing_activity_timeline_unknown_state_is_rejected(tmp_path):
    work = _probe_copy(tmp_path)
    path = work / MATRIX.relative_to(ROOT)
    text = path.read_text(encoding="utf-8")
    row = next(line for line in text.splitlines() if line.lower().startswith("| activity timeline"))
    cells = row.strip().strip("|").split("|")
    stripped = "|" + "|".join(cells[:-1]) + "|"
    path.write_text(text.replace(row, stripped), encoding="utf-8")
    _assert_rejected(_run_probe(work), "missing Activity Timeline unknown cell")


def test_probe_yaml_manifest_reintroduction_is_rejected(tmp_path):
    work = _probe_copy(tmp_path)
    (work / "docs/design/66d-delivery-acceptance/step66d-design-contract-manifest.yaml").write_text(
        "stage: probe\n", encoding="utf-8"
    )
    _assert_rejected(_run_probe(work), "reintroduced YAML manifest")


# ------------------------------------------------- RM2 route-truthfulness probes (K1-K5)
# R2-F01: a placeholder route must not be describable as implemented in ANY of the three
# representations (manifest semantic_routes, manifest route_inventory, route-map document), and the
# three must agree with each other and with the parsed frontend source.


def _edit_manifest(work: Path, mutate) -> None:
    path = work / MANIFEST.relative_to(ROOT)
    data = json.loads(path.read_text(encoding="utf-8"))
    mutate(data)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


@pytest.mark.parametrize(
    "label,state",
    [
        ("K1a semantic_routes IMPLEMENTED", "IMPLEMENTED"),
        ("K1b semantic_routes FUNCTIONAL", "FUNCTIONAL"),
        ("K1c semantic_routes AVAILABLE", "AVAILABLE"),
        ("K1d semantic_routes PRODUCTION_READY", "PRODUCTION_READY"),
    ],
)
def test_probe_k1_semantic_route_claimed_implemented_is_rejected(tmp_path, label, state):
    """K1 -- the placeholder /delivery-inbox declared implemented in semantic_routes."""
    work = _probe_copy(tmp_path)

    def mutate(data):
        for entry in data["semantic_routes"]:
            if entry.get("route") == "/delivery-inbox":
                entry["current_state"] = state

    _edit_manifest(work, mutate)
    _assert_rejected(_run_probe(work), label)


def test_probe_k2_route_inventory_entry_claimed_implemented_is_rejected(tmp_path):
    """K2 -- the placeholder /delivery-inbox declared implemented in route_inventory.routes."""
    work = _probe_copy(tmp_path)

    def mutate(data):
        for entry in data["route_inventory"]["routes"]:
            if entry["path"] == "/delivery-inbox":
                entry["classification"] = "IMPLEMENTED"

    _edit_manifest(work, mutate)
    _assert_rejected(_run_probe(work), "K2 route_inventory IMPLEMENTED")


@pytest.mark.parametrize("state", ["IMPLEMENTED", "FUNCTIONAL", "WRITE_ENABLED"])
def test_probe_k3_route_map_document_claimed_implemented_is_rejected(tmp_path, state):
    """K3 -- the route-map document's responsibility matrix declares a placeholder implemented."""
    work = _probe_copy(tmp_path)
    path = work / ROUTES_DOC.relative_to(ROOT)
    text = path.read_text(encoding="utf-8")
    original = "| Delivery Inbox | `/delivery-inbox` | PLACEHOLDER |"
    assert original in text, "route-map row anchor missing; probe would be vacuous"
    path.write_text(
        text.replace(original, f"| Delivery Inbox | `/delivery-inbox` | {state} |"),
        encoding="utf-8",
    )
    _assert_rejected(_run_probe(work), f"K3 route-map document {state}")


def test_probe_k4_cross_representation_disagreement_is_rejected(tmp_path):
    """K4 -- source and route_inventory both say PLACEHOLDER, semantic_routes says AVAILABLE.

    No single representation is internally implausible here; only cross-representation comparison
    catches it. This is the case R2-F01 reported as undetected.
    """
    work = _probe_copy(tmp_path)

    def mutate(data):
        for entry in data["semantic_routes"]:
            if entry.get("route") == "/delivery-inbox":
                entry["current_state"] = "AVAILABLE"

    _edit_manifest(work, mutate)
    result = _run_probe(work)
    _assert_rejected(result, "K4 cross-representation disagreement")
    assert "routes.cross_representation_equality" in result.stdout or "AVAILABLE" in result.stdout


@pytest.mark.parametrize(
    "label,state",
    [
        ("K5a absent route -> PLACEHOLDER", "PLACEHOLDER"),
        ("K5b absent route -> IMPLEMENTED", "IMPLEMENTED"),
    ],
)
def test_probe_k5_absent_route_reclassified_is_rejected(tmp_path, label, state):
    """K5 -- a route that does not exist in the source declared present in any form."""
    work = _probe_copy(tmp_path)

    def mutate(data):
        for entry in data["semantic_routes"]:
            if entry.get("route") == "/delivery-submissions/:deliverySubmissionId/review":
                entry["current_state"] = state

    _edit_manifest(work, mutate)
    _assert_rejected(_run_probe(work), label)


def test_probe_k_series_control_tree_is_restored_exactly(tmp_path):
    """Control for K1-K5: an untampered probe tree is byte-identical to the repository files."""
    work = _probe_copy(tmp_path)
    for path in [*ALL_DOCS, MANIFEST, VERIFIER]:
        copied = work / path.relative_to(ROOT)
        if path is VERIFIER:
            continue  # intentionally re-pointed at the probe's synthetic diff base
        assert copied.read_bytes() == path.read_bytes(), f"probe tree diverged at {path.name}"
    assert "STEP66D_DESIGN_UNIFIED_CONTROL_CENTER_VERIFY: PASS" in _run_probe(work).stdout


# --------------------------------------------------------------------- scope
def test_scope_no_runtime_or_backend_paths_changed():
    result = subprocess.run(
        ["git", "diff", "--name-only", f"{DESIGN_BASELINE}...HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        pytest.fail("could not compute the diff against the design baseline")
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
    for line in result.stdout.splitlines():
        path = line.strip().replace("\\", "/")
        if path:
            assert not path.startswith(forbidden), f"forbidden path changed: {path}"


def test_scope_changed_paths_are_exactly_fourteen():
    result = subprocess.run(
        ["git", "diff", "--name-only", f"{DESIGN_BASELINE}...HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        pytest.fail("could not compute the diff against the design baseline")
    changed = [
        line.strip().replace("\\", "/") for line in result.stdout.splitlines() if line.strip()
    ]
    assert len(changed) == 14, f"expected exactly 14 changed paths, got {len(changed)}: {changed}"
    assert not any(p.endswith((".yaml", ".yml")) for p in changed), "YAML file in the design diff"


def test_no_secrets_or_local_paths():
    secret = re.compile(
        r"(-----BEGIN [A-Z ]*PRIVATE KEY|ghp_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|"
        r"sk-ant-[A-Za-z0-9_-]{20,})"
    )
    local = re.compile(r"(C:\\Users|C:/Users|/home/[A-Za-z0-9._-]+/)")
    for path in [*ALL_DOCS, MANIFEST]:
        text = path.read_text(encoding="utf-8")
        assert not secret.search(text), f"secret shape in {path.name}"
        assert not local.search(text), f"local path in {path.name}"
