"""Step 66C.4-BE3-RA-2 -- identity and secret decision-package verification tests.

Offline, deterministic checks over the RA-2 deliverables and the negative-proof safety boundary.
These tests start NO runtime container (no PostgreSQL, Redis, Vault, or IdP), read NO real secret,
and perform NO identity, deployment, or activation action -- starting a runtime here would itself
be a scope violation of this stage.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

CONTRACT = ROOT / "docs" / "contracts" / "66c4-reminder-expiry-controlled-resume"
HANDOFF = ROOT / "docs" / "handoffs" / "66c4-reminder-expiry-controlled-resume"
SECURITY = ROOT / "docs" / "security"

PACKAGE = CONTRACT / "be3-ra2-identity-secret-provisioning-decision-package.md"
INVENTORY = SECURITY / "be3-ra2-current-state-identity-secret-inventory.md"
THREAT = SECURITY / "be3-ra2-identity-secret-threat-and-trust-analysis.md"
DECOMP = HANDOFF / "be3-ra2-implementation-stage-decomposition.md"
EVIDENCE = ROOT / "docs" / "test" / "step66c4-be3-ra2-identity-secret-decision-evidence.md"

RESUME_MODEL = ROOT / "shared" / "sdk" / "tasks" / "resume_request_model.py"
REPLAY_MODEL = ROOT / "shared" / "sdk" / "tasks" / "replay_request_model.py"
AUTH_POLICY = ROOT / "shared" / "sdk" / "tasks" / "authorization_policy.py"
VERIFY_SCRIPT = ROOT / "scripts" / "verify_step66c4_be3_ra2_identity_secret_decision.py"

BASELINE_MAIN = "c1db4cc"
DECISION_IDS = tuple(f"RA2-D{n:02d}" for n in range(1, 13))


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def package() -> str:
    return _read(PACKAGE)


@pytest.fixture(scope="module")
def inventory() -> str:
    return _read(INVENTORY)


@pytest.fixture(scope="module")
def threat() -> str:
    return _read(THREAT)


@pytest.fixture(scope="module")
def decomp() -> str:
    return _read(DECOMP)


@pytest.mark.parametrize("path", [PACKAGE, INVENTORY, THREAT, DECOMP, EVIDENCE])
def test_required_deliverable_exists(path: Path) -> None:
    assert path.is_file(), f"missing required deliverable: {path}"


def test_baseline_main_recorded(package: str) -> None:
    assert BASELINE_MAIN in package


# --- Decision package structure -------------------------------------------------


@pytest.mark.parametrize("decision_id", DECISION_IDS)
def test_decision_present(package: str, decision_id: str) -> None:
    assert f"Decision ID:          {decision_id}" in package


def test_at_least_twelve_decisions(package: str) -> None:
    found = [d for d in DECISION_IDS if f"Decision ID:          {d}" in package]
    assert len(found) >= 12, f"only {len(found)} decisions present"


@pytest.mark.parametrize("decision_id", DECISION_IDS)
def test_decision_has_multiple_options_and_pending_selection(
    package: str, decision_id: str
) -> None:
    block = package.split(f"Decision ID:          {decision_id}", 1)[-1].split("Decision ID:", 1)[0]
    assert "Option A:" in block
    assert "Option B:" in block
    assert "Product Owner selection:   PENDING" in block
    assert "Product Owner conditions:  PENDING" in block
    assert "Status: PRODUCT_OWNER_DECISION_REQUIRED" in block


def test_every_decision_marked_po_required(package: str) -> None:
    assert package.count("Status: PRODUCT_OWNER_DECISION_REQUIRED") >= 12


def test_nothing_marked_selected_or_approved(package: str) -> None:
    forbidden = re.compile(
        r"(Status:\s*(SELECTED|APPROVED|BINDING|CANONICAL))"
        r"|(Product Owner selection:\s*Option)"
        r"|(canonical backend)|(official IdP)|(final decision)",
        re.IGNORECASE,
    )
    hit = forbidden.search(package)
    assert hit is None, f"decision package marks an option chosen: {hit.group(0) if hit else ''}"


def test_recommendations_are_labelled_non_binding(package: str) -> None:
    assert "NON-BINDING" in package
    assert "RECOMMENDED FOR PO CONSIDERATION" in package
    assert "Decided by Claude Code: 0" in package


def test_unacceptable_patterns_recorded(package: str) -> None:
    lowered = package.lower()
    assert "request-provided role" in lowered
    assert "static shared secret" in lowered
    # Environment-file delivery must be confined to local/dev.
    assert "local/dev only" in lowered


# --- RA-P carry-forward ---------------------------------------------------------


@pytest.mark.parametrize("item", list(range(1, 12)))
def test_ra_p_open_item_carried_forward(package: str, item: int) -> None:
    assert f"RA-P {item}." in package


def test_ra_p_carry_forward_integrity(package: str) -> None:
    assert "RA-P open items: 11" in package
    assert "carried forward: 11" in package
    assert "dropped: 0" in package
    assert "silently defaulted: 0" in package


@pytest.mark.parametrize(
    "classification",
    [
        "RESOLVED_BY_RA2_PO_DECISION",
        "REQUIRES_RA2_PO_DECISION",
        "DEFERRED_TO_RA6",
        "DEFERRED_TO_RA7",
        "DEFERRED_TO_RA9_RA11",
    ],
)
def test_ra_p_classification_used(package: str, classification: str) -> None:
    assert classification in package


# --- Current-state inventory ----------------------------------------------------


def test_inventory_records_zero_production_service_identity_call_sites(inventory: str) -> None:
    assert re.search(r"apps/\s+0 call sites", inventory)
    assert re.search(r"shared/\s+0 call sites", inventory)
    assert re.search(r"tests/\s+16 call sites", inventory)
    assert "NO REAL SERVICE IDENTITY AUTHENTICATOR EXISTS" in inventory


def test_inventory_service_identity_claim_matches_reality() -> None:
    """Re-derive the inventory's central claim rather than trusting the document."""
    for folder in ("apps", "shared"):
        result = subprocess.run(
            ["git", "grep", "-n", "is_service_identity=True", "--", folder],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        assert (
            result.stdout.strip() == ""
        ), f"unexpected production Service Identity construction in {folder}/"


def test_inventory_records_header_based_operator_identity(inventory: str) -> None:
    assert "X-Task-Actor" in inventory
    assert "X-Task-Role" in inventory
    assert "TASK_API_TEST_AUTH_ENABLED" in inventory


@pytest.mark.parametrize(
    "question",
    [
        "正式 operator authenticator",
        "request payload/header",
        "Admin Console session",
        "可驗證的人類 operator identity",
    ],
)
def test_inventory_answers_mandatory_question(inventory: str, question: str) -> None:
    assert question in inventory


@pytest.mark.parametrize(
    "classification",
    [
        "IMPLEMENTED_AND_ACTIVE",
        "IMPLEMENTED_NOT_ACTIVE",
        "TEMPLATE_ONLY",
        "DEV_ONLY",
        "REFERENCED_NOT_IMPLEMENTED",
        "ABSENT",
    ],
)
def test_secret_backend_classification_vocabulary(inventory: str, classification: str) -> None:
    assert classification in inventory


def test_vault_dev_mode_distinguished(inventory: str) -> None:
    assert "server -dev" in inventory
    assert "IS NOT" in inventory


def test_policy_authority_inventoried(inventory: str) -> None:
    assert "compare_digest" in inventory
    assert "BE3_RESUME_POLICY_AUTHORITY" in inventory
    assert "dual-key rotation" in inventory.lower()


# --- Threat model ---------------------------------------------------------------


@pytest.mark.parametrize(
    "probe", ["impersonation", "replay", "revocation", "leakage", "confused deputy", "break-glass"]
)
def test_threat_model_covers(threat: str, probe: str) -> None:
    assert probe in threat.lower()


def test_threat_model_disclaims_zero_trust(threat: str) -> None:
    assert "Zero Trust" in threat
    assert "NOT achieved" in threat


def test_threat_model_has_trust_boundary_chain(threat: str) -> None:
    for boundary in ("Human Operator", "Policy", "Service Identity", "Audit Evidence"):
        assert boundary in threat


# --- Implementation decomposition -----------------------------------------------


@pytest.mark.parametrize(
    "stage", ["RA-2I1", "RA-2I2", "RA-2I3", "RA-2I4", "RA-2I5", "RA-2I6", "RA-2R"]
)
def test_stage_present(decomp: str, stage: str) -> None:
    assert stage in decomp


def test_stages_carry_dependencies_and_review_classification(decomp: str) -> None:
    assert "Required PO decisions:" in decomp
    assert "Independent review:" in decomp
    assert "Verification level:" in decomp
    assert "Earliest executable" in decomp


def test_no_stage_authorized(decomp: str) -> None:
    assert "Authorized stages: 0" in decomp
    assert "NOT AUTHORIZED" in decomp


# --- Safety / negative proof ----------------------------------------------------


@pytest.mark.parametrize(
    "var,path",
    [
        ("BE3_RESUME_API_ENABLED", RESUME_MODEL),
        ("BE3_RESUME_COMMAND_ENABLED", RESUME_MODEL),
        ("BE3_REPLAY_API_ENABLED", REPLAY_MODEL),
        ("BE3_REPLAY_EXECUTION_ENABLED", REPLAY_MODEL),
    ],
)
def test_feature_gate_defaults_false(var: str, path: Path) -> None:
    assert f'os.environ.get("{var}", "false")' in _read(path)


def test_stage_changed_no_runtime_or_infra_file() -> None:
    changed = subprocess.run(
        ["git", "diff", "--name-only", BASELINE_MAIN, "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    ).stdout
    offenders = [
        f.strip()
        for f in changed.splitlines()
        if f.strip().startswith(("apps/", "shared/", "infra/", "migrations/"))
    ]
    assert offenders == [], f"RA-2 must not change runtime/infra/migration files: {offenders}"


def test_authorization_policy_untouched_by_this_stage() -> None:
    """The Actor model and policy evaluation must be byte-identical to the baseline."""
    changed = subprocess.run(
        [
            "git",
            "diff",
            "--name-only",
            BASELINE_MAIN,
            "HEAD",
            "--",
            str(AUTH_POLICY.relative_to(ROOT)),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert changed == "", "authorization_policy.py must not be modified by a decision-only stage"


@pytest.mark.parametrize("doc", [PACKAGE, INVENTORY, THREAT, DECOMP])
def test_no_secret_shaped_content(doc: Path) -> None:
    secret_shaped = re.compile(
        r"(BEGIN [A-Z ]*PRIVATE KEY)"
        r"|(password\s*[:=]\s*['\"][^'\"]{3,})"
        r"|(postgres(?:ql)?://[^\s`]*:[^\s`@]+@)",
        re.IGNORECASE,
    )
    hit = secret_shaped.search(_read(doc))
    assert (
        hit is None
    ), f"{doc.name} contains secret-shaped content: {hit.group(0)[:40] if hit else ''}"


@pytest.mark.parametrize("doc", [PACKAGE, INVENTORY, THREAT, DECOMP])
def test_no_internal_identifiers(doc: Path) -> None:
    forbidden = re.compile(r"10\.0\.1\.(31|32)|aiagent-swd|itadmin|stpadmin", re.IGNORECASE)
    hit = forbidden.search(_read(doc))
    assert hit is None, f"{doc.name} leaks an internal identifier: {hit.group(0) if hit else ''}"


def test_production_executed_true_count_zero(package: str) -> None:
    assert "production_executed_true_count: 0" in package
    progress = _read(ROOT / "source" / "progress.md")
    assert "production_executed_true_count: 0" in progress


def test_verifier_script_passes() -> None:
    result = subprocess.run(
        [sys.executable, str(VERIFY_SCRIPT)], cwd=ROOT, capture_output=True, text=True
    )
    assert "STEP66C4_BE3_RA2_IDENTITY_SECRET_DECISION_VERIFY: PASS" in result.stdout, (
        result.stdout + result.stderr
    )
    assert result.returncode == 0
