"""Step 66D-DESIGN -- tests for the Unified Control Center UX/IA design package.

Deterministic, read-only. Mirrors scripts/verify_step66d_design_unified_control_center.py.
Must run with 0 failed and 0 skipped. Starts no runtime, container or external provider.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINE = "9c5210d190b82b76575ba8d456b5d2005c2867d2"
BASELINE_SHORT = "9c5210d"

D = ROOT / "docs" / "design" / "66d-delivery-acceptance"
H = ROOT / "docs" / "handoffs" / "66d-delivery-acceptance"

IA = D / "step66d-design-unified-control-center-ia.md"
ROUTES = D / "step66d-design-route-and-drilldown-map.md"
INBOX = D / "step66d-design-delivery-inbox-spec.md"
REVIEW = D / "step66d-design-delivery-review-interactions.md"
MATRIX = D / "step66d-design-state-error-permission-matrix.md"
WIRE = D / "step66d-design-wireframes.md"
A11Y = D / "step66d-design-accessibility-responsive-spec.md"
HANDOFF = D / "step66d-design-frontend-handoff.md"
MANIFEST = D / "step66d-design-contract-manifest.yaml"
INVENTORY = H / "step66d-design-existing-ui-route-inventory.md"
GAPS = H / "step66d-design-gap-and-dependency-register.md"
EVIDENCE = H / "step66d-design-evidence.md"

REQUIRED = [IA, ROUTES, INBOX, REVIEW, MATRIX, WIRE, A11Y, HANDOFF, MANIFEST, INVENTORY, GAPS, EVIDENCE]

REVIEW_ACTIONS = ["ACCEPT", "REJECT", "REQUEST_CHANGES", "RERUN_QA", "ESCALATE", "ARCHIVE"]
PO_DECISIONS = ["ACCEPTED", "ACCEPTED_WITH_FOLLOW_UP", "REJECTED"]
STATUSES = ["DRAFT", "SUBMITTED", "UNDER_REVIEW", "CHANGES_REQUESTED", "QA_RERUN_REQUESTED",
            "ACCEPTED", "REJECTED", "ARCHIVED", "EXPIRED"]


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8") if p.is_file() else ""


def _all() -> str:
    return "\n".join(_read(p) for p in REQUIRED)


def test_all_required_artifacts_exist():
    for p in REQUIRED:
        assert p.is_file(), f"missing {p.relative_to(ROOT)}"


def test_canonical_baseline_recorded():
    for p in (IA, ROUTES, MANIFEST, EVIDENCE):
        t = _read(p)
        assert BASELINE in t or BASELINE_SHORT in t, f"{p.name} missing baseline"


def test_unified_control_center_is_single_canonical_ia():
    m = _read(MANIFEST)
    assert 'canonical_ia: "Unified Control Center"' in m
    assert 'option_comparison: "CLOSED / NOT REOPENED"' in m
    assert "unified overview + existing route drill-down" in _all().lower()


def test_ia_not_remarked_unresolved():
    low = _all().lower()
    for bad in ("ia is unresolved", "ia remains open", "ia still open", "ia undecided"):
        assert bad not in low


def test_three_surface_separation():
    low = _read(IA).lower()
    for term in ("delivery inbox", "unified control center", "delivery review"):
        assert term in low
    assert "duplication-prevention rule" in low


def test_six_review_actions_and_three_decisions_separated():
    r = _read(REVIEW)
    for a in REVIEW_ACTIONS:
        assert a in r
    for d in PO_DECISIONS:
        assert d in r
    low = r.lower()
    assert "exactly six" in low
    assert "exactly three" in low
    assert "visually and semantically separated" in low


def test_nine_canonical_statuses():
    t = _read(MATRIX)
    for s in STATUSES:
        assert s in t, f"status missing: {s}"


def test_qa_rerun_limit_one_backend_authoritative():
    m = _read(MANIFEST)
    assert "limit_per_submission_version: 1" in m
    assert "client_counter_allowed: false" in m
    assert "1 of 1" in _read(REVIEW)
    assert "qa_rerun_limit_reached" in _all().lower()


def test_expired_blocks_accept_and_reject():
    m = _read(MANIFEST)
    assert "disabled_when_expired" in m
    seg = m.split("disabled_when_expired:")[1].split("available_when_expired:")[0]
    assert "ACCEPT" in seg and "REJECT" in seg


def test_blocking_follow_up_rule():
    m = _read(MANIFEST)
    low = _all().lower()
    assert "blocking_item_allowed: false" in m
    assert "blocking_follow_up_requires_changes" in low
    assert ("no auto-conversion" in low) or ("not auto-convert" in low)


def test_all_required_states_present():
    low = _read(MATRIX).lower()
    for st in ("loading", "empty", "partial", "stale", "inaccessible", "error", "unknown"):
        assert st in low
    for es in ("COMPLETE", "PARTIAL", "MISSING", "STALE", "INACCESSIBLE", "UNKNOWN"):
        assert es in _read(MATRIX) or es in _read(IA)
    assert "never green" in (_read(MATRIX) + _read(IA)).lower()


def test_identity_gate_blocks_final_decision():
    assert "identity not verified" in _read(MATRIX).lower()
    assert "final_decision_requires_verified_identity: true" in _read(MANIFEST)


def test_read_model_freshness_present():
    t = _all()
    assert "as_of" in t and "is_stale" in t
    assert "eventually consistent" in t.lower()
    assert "authority_rule" in _read(MANIFEST)


def test_existing_routes_not_faked_as_implemented():
    assert ("planned / not implemented" in _read(ROUTES).lower()
            or "planned_not_implemented" in _read(MANIFEST).lower())
    assert "placeholder" in _read(INVENTORY).lower()
    assert "44" in _read(INVENTORY)


def test_deep_link_contract_present():
    r = _read(ROUTES)
    for prm in ("project_id", "delivery_submission_id", "delivery_review_task_id", "return_to"):
        assert prm in r
    assert "return behavior" in r.lower()


def test_responsive_and_accessibility_specified():
    a = _read(A11Y)
    for bp in ("1440", "1280", "1024", "768"):
        assert bp in a
    low = a.lower()
    for req in ("keyboard", "focus", "screen-reader", "reduced motion", "focus trap"):
        assert req in low


def test_no_implementation_claims():
    low = _all().lower()
    m = _read(MANIFEST)
    assert "no frontend implementation" in low
    assert "not authorized" in low
    assert "codex_authorized: false" in m
    assert 'merge_authorization: "NOT GRANTED"' in m


def test_legacy_delivery_package_boundary_preserved():
    m = _read(MANIFEST)
    t = _all()
    assert "legacy_delivery_package_repurposed: false" in m
    assert "legacy_delivery_package_refs" in t
    assert "deliverysubmission" in t.lower()


def test_dual_anchor_and_task_boundary():
    low = _all().lower()
    assert "dual" in low
    assert "delivery_review_task_id" in _all()
    assert ("task is not the agent execution source of truth" in low) or ("non-dispatching" in low)


def test_production_count_zero_and_contracts_unmodified():
    t = _all()
    m = _read(MANIFEST)
    assert ("production_executed_true_count: 0" in t) or ("production_executed_true_count = 0" in t)
    assert "production_executed_true_count: 0" in m
    assert "adr_66d_09_modified: false" in m
    assert "task_roles_modified: false" in m


def test_ten_wireframes():
    assert len(re.findall(r"^## WF-\d+", _read(WIRE), flags=re.M)) == 10


def test_no_secrets_or_local_paths():
    secret = re.compile(r"(-----BEGIN [A-Z ]*PRIVATE KEY|ghp_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|sk-ant-[A-Za-z0-9_-]{20,})")
    localp = re.compile(r"(C:\\Users|C:/Users|/home/[A-Za-z0-9._-]+/)")
    for p in REQUIRED:
        t = _read(p)
        assert not secret.search(t), f"secret shape in {p.name}"
        assert not localp.search(t), f"local path in {p.name}"


def test_scope_no_runtime_or_backend_paths_changed():
    r = subprocess.run(["git", "diff", "--name-only", f"{BASELINE}...HEAD"],
                       cwd=ROOT, capture_output=True, text=True, check=False)
    if r.returncode != 0:
        return
    forbidden = ("apps/", "agents/", "services/", "shared/", "migrations/", "infra/",
                 "helm/", "k8s/", ".github/workflows/")
    for line in r.stdout.splitlines():
        path = line.strip().replace("\\", "/")
        if not path:
            continue
        assert not any(path.startswith(p) for p in forbidden), f"forbidden path changed: {path}"
