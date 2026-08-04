"""Tests for Step 66C.4-BE3-RA-2M1 identity and secret canonicalization.

Offline by design: no container, no database, no Vault, no OIDC provider, no Kubernetes API, no
network, no secret access. Several tests re-derive their claims from Git objects or from the
repository source rather than asserting that a document agrees with itself.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "verify_step66c4_be3_ra2m_canonicalization.py"

SECURITY = REPO / "docs" / "security"
CONTRACTS = REPO / "docs" / "contracts" / "66c4-reminder-expiry-controlled-resume"
HANDOFFS = REPO / "docs" / "handoffs" / "66c4-reminder-expiry-controlled-resume"
MASTER = REPO / "docs" / "alignment" / "66-project-completion" / "master"
TEST_DOCS = REPO / "docs" / "test"

INVENTORY = SECURITY / "be3-ra2-current-state-identity-secret-inventory.md"
THREAT_MODEL = SECURITY / "be3-ra2-identity-secret-threat-and-trust-analysis.md"
DECISION_PACKAGE = CONTRACTS / "be3-ra2-identity-secret-provisioning-decision-package.md"
STAGE_PROPOSAL = HANDOFFS / "be3-ra2-implementation-stage-decomposition.md"
PLANNING_EVIDENCE = TEST_DOCS / "step66c4-be3-ra2-identity-secret-decision-evidence.md"

BINDING = CONTRACTS / "step66c4-be3-ra2-binding-decisions.md"
ADDENDUM = MASTER / "step66c4-be3-ra2-current-state-20260804.md"
PRECEDENCE = MASTER / "canonical-source-of-truth-precedence.md"
MANIFEST = HANDOFFS / "step66c4-be3-ra2m-canonicalization-manifest.md"
EVIDENCE = TEST_DOCS / "step66c4-be3-ra2m-canonicalization-evidence.md"

CANONICAL_MAIN = "44ab32ceab60d417ef1e0800be6cd00fc730b12e"
PLANNING_HEAD = "efa396dee6512d6f15b3fd079df87d2c70ee0c77"
PLANNING_BASE = "c1db4ccbfd88fa775e4761c932835896b9b980ed"

IMPORTED_UNCHANGED = (
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


def _git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=REPO,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert result.returncode == 0, f"git {' '.join(args)} failed: {result.stderr}"
    return result.stdout.strip()


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _section(decision: str) -> str:
    match = re.search(rf"^## {decision} —.*?(?=^## |\Z)", _read(BINDING), re.MULTILINE | re.DOTALL)
    assert match is not None, decision
    return match.group(0)


def _flat(text: str) -> str:
    return re.sub(r"\s+", " ", text)


# --- verifier -------------------------------------------------------------------------------


def test_verifier_script_exists() -> None:
    assert SCRIPT.is_file()


def test_verifier_passes() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=REPO,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "STEP66C4_BE3_RA2M_CANONICALIZATION_PREP_VERIFY: PASS" in result.stdout


# --- baseline and planning source, re-derived from Git ----------------------------------------


def test_canonical_main_is_ancestor_of_head() -> None:
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", CANONICAL_MAIN, "HEAD"], cwd=REPO, check=False
    )
    assert result.returncode == 0


def test_planning_head_resolves() -> None:
    assert _git("rev-parse", f"{PLANNING_HEAD}^{{commit}}") == PLANNING_HEAD


def test_planning_branch_head_unchanged() -> None:
    head = _git("rev-parse", "origin/planning/66c4-be3-ra2-identity-secret-decision")
    assert head == PLANNING_HEAD


def test_planning_branch_was_cut_from_the_previous_main() -> None:
    """The planning branch predates the current main, which is why it is not merged."""
    assert _git("merge-base", PLANNING_HEAD, CANONICAL_MAIN) == PLANNING_BASE


def test_planning_branch_is_not_merged_into_this_branch() -> None:
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", PLANNING_HEAD, "HEAD"], cwd=REPO, check=False
    )
    assert result.returncode != 0, "the planning branch must not be merged"


# --- import integrity ---------------------------------------------------------------------


def test_every_import_is_byte_identical_to_the_planning_commit() -> None:
    for rel in IMPORTED_UNCHANGED:
        source = _git("rev-parse", f"{PLANNING_HEAD}:{rel}")
        current = _git("rev-parse", f":{rel}")
        assert source == current, rel


def test_eight_files_were_imported_unchanged() -> None:
    assert len(IMPORTED_UNCHANGED) == 8


def test_all_planning_categories_present() -> None:
    for path in (INVENTORY, THREAT_MODEL, DECISION_PACKAGE, STAGE_PROPOSAL, PLANNING_EVIDENCE):
        assert path.is_file(), path.name


def test_next_executable_sequence_was_untouched_on_main() -> None:
    """Byte-identical import was safe only because main never modified this file."""
    rel = "docs/alignment/66-project-completion/master/next-executable-stage-sequence.md"
    assert _git("diff", "--name-only", PLANNING_BASE, CANONICAL_MAIN, "--", rel) == ""


def test_imported_ra2_verifier_still_passes_unchanged() -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(REPO / "scripts" / "verify_step66c4_be3_ra2_identity_secret_decision.py"),
        ],
        cwd=REPO,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "STEP66C4_BE3_RA2_IDENTITY_SECRET_DECISION_VERIFY: PASS" in result.stdout


def test_manifest_covers_every_import_and_new_record() -> None:
    manifest = _read(MANIFEST)
    for rel in IMPORTED_UNCHANGED:
        assert rel in manifest, rel
    assert "source/progress.md" in manifest
    for rel in (
        "step66c4-be3-ra2-binding-decisions.md",
        "step66c4-be3-ra2-current-state-20260804.md",
        "step66c4-be3-ra2m-canonicalization-manifest.md",
        "step66c4-be3-ra2m-canonicalization-evidence.md",
    ):
        assert rel in manifest, rel


def test_manifest_records_every_commit() -> None:
    manifest = _read(MANIFEST)
    for commit in ("efa396d", "44ab32c", "c1db4cc"):
        assert commit in manifest


def test_manifest_marks_eight_imports_unchanged() -> None:
    rows = [line for line in _read(MANIFEST).splitlines() if line.startswith("| `")]
    assert len([line for line in rows if "| YES |" in line]) == 8


# --- historical evidence preservation ----------------------------------------------------------


def test_decision_package_still_records_pending() -> None:
    package = _read(DECISION_PACKAGE)
    assert "PENDING" in package
    assert "RESOLVED / BINDING" not in package


def test_no_planning_document_was_rewritten_with_the_new_status() -> None:
    for path in (INVENTORY, THREAT_MODEL, STAGE_PROPOSAL, PLANNING_EVIDENCE, DECISION_PACKAGE):
        assert "RESOLVED / BINDING" not in _read(path), path.name


def test_binding_record_explains_the_status_transition() -> None:
    binding = _read(BINDING)
    assert "imported unchanged" in binding
    assert "after** that" in binding or "after that" in binding


def test_known_index_defect_is_recorded_not_silently_fixed() -> None:
    index = _read(MASTER / "next-executable-stage-sequence.md")
    assert "79 tests passed" in index, "the historical index must not be edited in place"
    addendum = _read(ADDENDUM)
    assert "100 passed / 0 skipped / 0 failed" in addendum
    assert "79 tests passed" in addendum


def test_authoritative_test_count_is_one_hundred() -> None:
    """Re-derived by running the imported RA-2 test file, not read from any document."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "tests/test_step66c4_be3_ra2_identity_secret_decision.py",
        ],
        cwd=REPO,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert result.returncode == 0, result.stdout
    assert "100 passed" in result.stdout


# --- binding decisions -------------------------------------------------------------------------


def test_decision_authority_and_date() -> None:
    binding = _read(BINDING)
    assert "DECISION_AUTHORITY:\nProduct Owner" in binding
    assert "DECISION_DATE:\n2026-08-04" in binding


def test_canonical_context_and_planning_source_recorded() -> None:
    binding = _read(BINDING)
    assert "main 44ab32c" in binding
    assert PLANNING_HEAD in binding


def test_all_twelve_decisions_present() -> None:
    binding = _read(BINDING)
    for decision in DECISIONS:
        assert decision in binding, decision


def test_all_twelve_decisions_are_resolved_binding() -> None:
    for decision in DECISIONS:
        assert re.search(r"STATUS:\s+RESOLVED / BINDING", _section(decision)), decision


def test_all_six_conditions_present_and_binding() -> None:
    binding = _read(BINDING)
    for condition in CONDITIONS:
        assert condition in binding, condition
    assert "RA2_C01_C06:\nRESOLVED / BINDING" in binding


def test_d01_selects_enterprise_oidc() -> None:
    flat = _flat(_section("RA2-D01"))
    assert "Enterprise OIDC" in flat
    assert "existing enterprise Identity Provider" in flat
    assert "No specific vendor, tenant, or production issuer is selected" in flat


def test_d02_selects_auth_code_pkce_server_session() -> None:
    flat = _flat(_section("RA2-D02"))
    assert "Authorization Code Flow with PKCE" in flat
    assert "server-side session" in flat
    for forbidden in ("browser-stored bearer token", "request-header identity"):
        assert forbidden in flat


def test_d03_selects_platform_owned_rbac() -> None:
    flat = _flat(_section("RA2-D03"))
    assert "Platform-owned RBAC is the authorization source of truth" in flat
    assert "never, by itself, a platform authorization" in flat


def test_d04_selects_projected_serviceaccount_oidc() -> None:
    flat = _flat(_section("RA2-D04"))
    assert "projected ServiceAccount OIDC" in flat
    assert "SPIFFE / SPIRE: DEFERRED" in flat
    assert "No static shared service credential" in flat


def test_d05_selects_policy_authority_workload_oidc() -> None:
    flat = _flat(_section("RA2-D05"))
    assert "same projected workload OIDC model" in flat
    assert "LOCAL / TEST ONLY" in flat
    assert "DISABLED IN SHARED RUNTIME" in flat


def test_d06_selects_non_dev_vault() -> None:
    flat = _flat(_section("RA2-D06"))
    assert "HashiCorp Vault, non-dev" in flat
    assert "Kubernetes workload identity" in flat
    assert "GCP Secret Manager: DEFERRED" in flat


def test_d07_defers_vault_agent_versus_csi_to_ra2i4p() -> None:
    flat = _flat(_section("RA2-D07"))
    assert "Vault Agent versus CSI is NOT selected" in flat
    assert "RA-2I4P" in flat
    assert "must not be made in RA-2M" in flat
    assert "Environment-variable secret delivery is prohibited in shared runtime" in flat


def test_d08_records_full_provisioning_governance() -> None:
    flat = _flat(_section("RA2-D08"))
    for needle in (
        "GitOps-controlled provisioning",
        "Platform Security",
        "Enterprise IAM",
        "two-person approval",
    ):
        assert needle in flat, needle


def test_d09_is_credential_specific() -> None:
    flat = _flat(_section("RA2-D09"))
    assert "Credential-specific lifecycle controls" in flat
    for control in (
        "short TTL",
        "renewal",
        "bounded overlap",
        "session invalidation",
        "workload disablement",
        "Vault lease revocation",
    ):
        assert control in flat, control


def test_d10_break_glass_is_dedicated_with_hardware_mfa() -> None:
    flat = _flat(_section("RA2-D10"))
    assert "Dedicated human break-glass identity" in flat
    assert "hardware MFA" in flat
    for forbidden in (
        "production approval bypass",
        "anonymous emergency identity",
        "shared break-glass account",
    ):
        assert forbidden in flat, forbidden


def test_d11_first_environment_is_isolated_non_production() -> None:
    flat = _flat(_section("RA2-D11"))
    assert "isolated non-production Kubernetes" in flat
    assert "Production must not serve as the first validation environment" in flat


def test_d12_requires_the_complete_identity_chain() -> None:
    flat = _flat(_section("RA2-D12"))
    assert "Activation is not allowed until the complete chain is validated" in flat
    for link in (
        "Operator Identity",
        "Platform RBAC",
        "Policy Authority",
        "Service Identity",
        "Audit",
    ):
        assert link in flat, link
    assert "is not activation" in flat


# --- binding conditions --------------------------------------------------------------------------


def _condition(name: str, following: str) -> str:
    match = re.search(rf"{name}\s+(.*?)(?={following})", _read(BINDING), re.DOTALL)
    assert match is not None, name
    return _flat(match.group(1))


def test_c01_single_authoritative_secret_backend() -> None:
    assert "exactly one authoritative secret backend" in _condition("RA2-C01", "RA2-C02")


def test_c02_request_actor_is_never_identity() -> None:
    text = _condition("RA2-C02", "RA2-C03")
    assert "never an authorization identity" in text
    assert "never an authoritative audit identity" in text


def test_c03_no_static_service_identity_secret() -> None:
    assert "static shared Service Identity secret" in _condition("RA2-C03", "RA2-C04")


def test_c04_no_vault_dev_or_root_token() -> None:
    text = _condition("RA2-C04", "RA2-C05")
    for needle in ("Vault dev mode", "root token", "static Vault token"):
        assert needle in text, needle


def test_c05_no_resume_replay_before_ra2r() -> None:
    text = _condition("RA2-C05", "RA2-C06")
    assert "RA-2R" in text
    assert "must not run until" in text


def test_c06_every_stage_needs_separate_authorization() -> None:
    assert "separate Product Owner authorization" in _read(BINDING)


# --- sequence and authorization --------------------------------------------------------------------


def test_sequence_recorded_in_authorized_order() -> None:
    chain = re.search(r"RA-2M\n(?:\s*->\s*RA-[\w]+\n)+", _read(BINDING))
    assert chain is not None
    assert re.findall(r"RA-[\w]+", chain.group(0)) == [
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


def test_sequence_is_not_an_authorization() -> None:
    binding = _read(BINDING)
    assert "APPROVED EXECUTION SEQUENCE" in binding
    assert "NOT IMPLEMENTATION AUTHORIZATION" in binding


def test_ra2i4_split_is_recorded_as_superseding_the_proposal() -> None:
    binding = _read(BINDING)
    assert "supersedes the stage decomposition proposed" in binding
    assert "single `RA-2I4` stage is split" in binding


def test_ra2i2_follows_ra2i3() -> None:
    binding = _read(BINDING)
    assert binding.index("RA-2I3   Policy Authority") < binding.index("RA-2I2   Service Identity")
    assert "Must follow RA-2I3" in binding


def test_every_stage_is_unauthorized() -> None:
    binding = _read(BINDING)
    for stage in STAGES:
        assert re.search(rf"^{stage}:\s+NOT AUTHORIZED$", binding, re.MULTILINE), stage


def test_ra2_implementation_not_started_or_authorized() -> None:
    binding = _read(BINDING)
    assert "RA2_IMPLEMENTATION:\nNOT STARTED / NOT AUTHORIZED" in binding
    assert "RA2_CANONICALIZATION:   PREPARED FOR MERGE" in binding


# --- current state re-derived from source ---------------------------------------------------------


def test_task_api_still_trusts_request_headers() -> None:
    """The addendum's central claim, re-derived from the code rather than cited."""
    source = _read(REPO / "apps" / "orchestrator" / "src" / "task_api.py")
    assert "X-Task-Actor" in source
    assert "X-Task-Role" in source


def test_oidc_provider_is_still_interface_only() -> None:
    matches = _git("grep", "-l", "OidcDisabledError", "--", "shared", "apps")
    assert matches.strip(), "OidcDisabledError not found; the OIDC path may no longer be disabled"


def test_vault_directory_still_has_no_configuration() -> None:
    vault_dir = REPO / "infra" / "vault"
    if not vault_dir.is_dir():
        return
    real = [p for p in vault_dir.rglob("*") if p.is_file() and p.name != ".gitkeep"]
    assert real == [], f"unexpected Vault configuration: {real}"


def test_be3_gates_still_default_false() -> None:
    resume = _read(REPO / "shared" / "sdk" / "tasks" / "resume_request_model.py")
    replay = _read(REPO / "shared" / "sdk" / "tasks" / "replay_request_model.py")
    assert 'os.environ.get("BE3_RESUME_API_ENABLED", "false")' in resume
    assert 'os.environ.get("BE3_RESUME_COMMAND_ENABLED", "false")' in resume
    assert 'os.environ.get("BE3_REPLAY_API_ENABLED", "false")' in replay
    assert 'os.environ.get("BE3_REPLAY_EXECUTION_ENABLED", "false")' in replay


def test_addendum_records_nothing_implemented() -> None:
    addendum = _read(ADDENDUM)
    for line in (
        "Operator production authentication:\nNOT IMPLEMENTED",
        "Service Identity production authentication:\nNOT IMPLEMENTED",
        "Policy Authority workload OIDC:\nNOT IMPLEMENTED",
        "Authoritative non-dev Vault:\nNOT DEPLOYED",
        "Shared secret delivery:\nNOT IMPLEMENTED",
        "Dedicated non-production Kubernetes environment:\nNOT PROVISIONED",
        "Resume/replay execution:\nDISABLED",
        "RA-2R:\nNOT STARTED",
        "production_executed_true_count:\n0",
    ):
        assert line in addendum, line


def test_addendum_records_zero_threats_mitigated() -> None:
    addendum = _read(ADDENDUM)
    assert "Threats mitigated:       0" in addendum
    assert "Implementation stages authorized: 0 of 11" in addendum


# --- precedence -------------------------------------------------------------------------------------


def test_ra2_precedence_tiers_recorded() -> None:
    precedence = _read(PRECEDENCE)
    for line in (
        "1. Product Owner binding decisions",
        "2. Current RA-2 canonical state addendum",
        "3. RA-2 binding decision record's implementation sequence",
        "4. Historical RA-2 planning evidence",
        "5. Partner recommendations",
        "6. Conversation summaries",
    ):
        assert line in precedence, line


def test_precedence_says_recommendation_is_not_authorization() -> None:
    assert "never an implementation authorization" in _read(PRECEDENCE)


def test_precedence_resolves_the_known_conflicts() -> None:
    precedence = _read(PRECEDENCE)
    assert "Tier 1 supersedes" in precedence
    assert "Vault Agent versus CSI" in precedence
    assert "NOT selected at any tier" in precedence


# --- scope boundary ------------------------------------------------------------------------------------


def _changed() -> list[str]:
    return [line for line in _git("diff", "--name-only", CANONICAL_MAIN).splitlines() if line]


def test_no_runtime_backend_or_agent_source_changed() -> None:
    forbidden = ("apps/", "agents/", "shared/", "services/", "migrations/", "infra/")
    assert [p for p in _changed() if p.startswith(forbidden)] == []


def test_no_frontend_source_changed() -> None:
    suffixes = (".tsx", ".ts", ".jsx", ".js", ".vue", ".css", ".scss")
    assert [p for p in _changed() if p.endswith(suffixes)] == []


def test_no_manifest_compose_or_chart_changed() -> None:
    assert [
        p
        for p in _changed()
        if "docker-compose" in p
        or p.startswith(("helm/", "k8s/", "charts/"))
        or p.endswith((".yaml", ".yml"))
    ] == []


def test_changed_paths_are_within_scope() -> None:
    allowed_exact = {
        "source/progress.md",
        "scripts/verify_step66c4_be3_ra2m_canonicalization.py",
        "tests/test_step66c4_be3_ra2m_canonicalization.py",
        "scripts/verify_step66c4_be3_ra2_identity_secret_decision.py",
        "tests/test_step66c4_be3_ra2_identity_secret_decision.py",
        # BOUNDED POST-MERGE VERIFIER ADAPTATION (Step 66C.4-BE3-RA-2M2): the RA-2M2 artifacts
        # postdate this allowlist and could not have been in the merge. No runtime path admitted.
        "scripts/verify_step66c4_be3_ra2m2_canonical_merge.py",
        "tests/test_step66c4_be3_ra2m2_canonical_merge.py",
    }
    later_stage = ("docs/", "scripts/verify_step66", "tests/test_step66")
    assert [p for p in _changed() if p not in allowed_exact and not p.startswith(later_stage)] == []


def test_progress_record_is_append_only() -> None:
    numstat = _git("diff", "--numstat", CANONICAL_MAIN, "--", "source/progress.md")
    if not numstat:
        return
    added, deleted, _ = numstat.split("\t", 2)
    assert deleted == "0"
    assert int(added) > 0


def test_progress_record_contains_the_ra2_sections() -> None:
    progress = _read(REPO / "source" / "progress.md")
    assert "## Step 66C.4-BE3-RA-2 — Identity and Secret Provisioning Decision" in progress
    assert "## Step 66C.4-BE3-RA-2M1 — Canonicalize Identity and Secret Decisions" in progress


# --- no false claims ---------------------------------------------------------------------------------


def test_no_document_claims_implementation_or_deployment() -> None:
    for path in (BINDING, ADDENDUM, MANIFEST, EVIDENCE, PRECEDENCE):
        text = _read(path).lower()
        for phrase in (
            "oidc is implemented",
            "vault is deployed",
            "service identity is active",
            "shared environment is ready",
            "resume/replay is enabled",
        ):
            for match in re.finditer(re.escape(phrase), text):
                window = text[match.end() : match.end() + 100]
                assert "false" in window or "not " in window, f"{path.name}: {phrase}"


def test_binding_record_lists_prohibited_implications() -> None:
    binding = _read(BINDING)
    for phrase in (
        "RA-2 decisions are already on main",
        "OIDC is implemented",
        "Vault is deployed",
        "Service Identity is active",
        "Resume/replay is enabled",
    ):
        assert phrase in binding, phrase


def test_production_executed_true_count_is_zero_everywhere() -> None:
    for path in (BINDING, ADDENDUM, MANIFEST, EVIDENCE):
        text = _read(path)
        for value in re.findall(r"production_executed_true_count[`:\s]*([0-9]+)", text, re.I):
            assert value == "0", path.name


def test_evidence_document_records_the_marker() -> None:
    assert "STEP66C4_BE3_RA2M_CANONICALIZATION_PREP_VERIFY: PASS" in _read(EVIDENCE)
