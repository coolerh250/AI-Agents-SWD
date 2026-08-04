"""Tests for Step 66SYNC.1-M1 canonicalization preparation.

Offline by design: no container, no database, no network, no secret access. Several tests
re-derive their claims from Git objects rather than asserting that a document agrees with itself.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "verify_step66sync1_m1_canonicalization.py"

SYNC = REPO / "docs" / "handoffs" / "program-sync"
MASTER = REPO / "docs" / "alignment" / "66-project-completion" / "master"
TEST_DOCS = REPO / "docs" / "test"

BINDING = SYNC / "step66sync1-poc-scope-binding-decisions.md"
ADDENDUM = MASTER / "partner-synchronized-program-state-20260804.md"
PRECEDENCE = MASTER / "canonical-source-of-truth-precedence.md"
MANIFEST = SYNC / "step66sync1-canonicalization-manifest.md"
EVIDENCE = TEST_DOCS / "step66sync1-m1-canonicalization-evidence.md"

CANONICAL_MAIN = "c1db4ccbfd88fa775e4761c932835896b9b980ed"
CLAUDE_CODE_HEAD = "828ea90"
CODEX_HEAD = "78aa4ee"
CLAUDE_DESIGN_HEAD = "65c93a1"
FINAL_HEAD = "2396c6c"
RA2_HEAD = "efa396d"

CLAUDE_CODE_FILES = (
    "docs/alignment/66-project-completion/master/partner-context-snapshot-20260803.md",
    "docs/handoffs/program-sync/step66sync1-claude-code-acknowledgement.md",
    "docs/handoffs/program-sync/step66sync1-context-discrepancy-register.md",
    "docs/handoffs/program-sync/step66sync1-poc-backend-readiness-matrix.md",
    "docs/test/step66sync1-claude-code-reconciliation-evidence.md",
)
CODEX_FILES = (
    "docs/handoffs/program-sync/step66sync1-codex-acknowledgement.md",
    "docs/handoffs/program-sync/step66sync1-codex-frontend-gap-register.md",
    "docs/test/step66sync1-codex-frontend-reconciliation-evidence.md",
    "scripts/verify_step66sync1_codex_frontend_reconciliation.py",
    "tests/test_step66sync1_codex_frontend_reconciliation.py",
)
CLAUDE_DESIGN_FILES = (
    "docs/design/ai-agent-team-functional-poc-control-center-spec.md",
    "docs/handoffs/program-sync/step66sync1-claude-design-acknowledgement.md",
    "docs/handoffs/program-sync/step66sync1-claude-design-ux-gap-register.md",
    "docs/test/step66sync1-claude-design-reconciliation-evidence.md",
    "scripts/verify_step66sync1_claude_design_reconciliation.py",
    "tests/test_step66sync1_claude_design_reconciliation.py",
)
FINAL_FILES = (
    "docs/alignment/66-project-completion/master/partner-synchronized-program-state-20260803.md",
    "docs/handoffs/program-sync/step66sync1-final-partner-acknowledgement.md",
    "docs/handoffs/program-sync/step66sync1-final-context-discrepancy-register.md",
    "docs/handoffs/program-sync/step66sync1-poc-scope-decision-package.md",
    "docs/handoffs/program-sync/step66sync1-poc0-consolidated-gap-register.md",
    "docs/test/step66sync1-final-partner-reconciliation-evidence.md",
)
IMPORTED = {
    CLAUDE_CODE_HEAD: CLAUDE_CODE_FILES,
    CODEX_HEAD: CODEX_FILES,
    CLAUDE_DESIGN_HEAD: CLAUDE_DESIGN_FILES,
    FINAL_HEAD: FINAL_FILES,
}

TRANSFORMED = {
    CLAUDE_CODE_HEAD: (
        "scripts/verify_step66sync1_claude_code_reconciliation.py",
        "tests/test_step66sync1_claude_code_reconciliation.py",
    ),
    FINAL_HEAD: (
        "scripts/verify_step66sync1_final_partner_reconciliation.py",
        "tests/test_step66sync1_final_partner_reconciliation.py",
    ),
}


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


# --- verifier -----------------------------------------------------------------------------


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
    assert "STEP66SYNC1_M1_CANONICALIZATION_PREP_VERIFY: PASS" in result.stdout


# --- baseline and partner heads (re-derived from Git, not from prose) ----------------------


def test_canonical_main_is_baseline() -> None:
    assert _git("rev-parse", "origin/main") == CANONICAL_MAIN


def test_canonical_main_is_ancestor_of_head() -> None:
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", CANONICAL_MAIN, "HEAD"],
        cwd=REPO,
        check=False,
    )
    assert result.returncode == 0


def test_claude_code_head_resolves() -> None:
    assert _git("rev-parse", f"{CLAUDE_CODE_HEAD}^{{commit}}").startswith(CLAUDE_CODE_HEAD)


def test_codex_head_resolves() -> None:
    assert _git("rev-parse", f"{CODEX_HEAD}^{{commit}}").startswith(CODEX_HEAD)


def test_claude_design_head_resolves() -> None:
    assert _git("rev-parse", f"{CLAUDE_DESIGN_HEAD}^{{commit}}").startswith(CLAUDE_DESIGN_HEAD)


def test_final_reconciliation_head_resolves() -> None:
    assert _git("rev-parse", f"{FINAL_HEAD}^{{commit}}").startswith(FINAL_HEAD)


def test_ra2_planning_branch_head_unchanged() -> None:
    head = _git("rev-parse", "origin/planning/66c4-be3-ra2-identity-secret-decision")
    assert head.startswith(RA2_HEAD)


def test_partner_branch_heads_unchanged() -> None:
    for branch, expected in (
        ("origin/planning/66sync1-claude-code-state-reconciliation", CLAUDE_CODE_HEAD),
        ("origin/planning/66sync1-codex-frontend-reconciliation", CODEX_HEAD),
        ("origin/planning/66sync1-claude-design-ux-reconciliation", CLAUDE_DESIGN_HEAD),
        ("origin/planning/66sync1-final-partner-reconciliation", FINAL_HEAD),
    ):
        assert _git("rev-parse", branch).startswith(expected), branch


# --- import integrity ---------------------------------------------------------------------


def test_every_imported_file_is_byte_identical_to_its_source_commit() -> None:
    for commit, paths in IMPORTED.items():
        for rel in paths:
            source = _git("rev-parse", f"{commit}:{rel}")
            current = _git("rev-parse", f":{rel}")
            assert source == current, f"{rel} differs from {commit}"


def test_twenty_six_files_were_imported() -> None:
    unchanged = sum(len(paths) for paths in IMPORTED.values())
    transformed = sum(len(paths) for paths in TRANSFORMED.values())
    assert unchanged == 22
    assert transformed == 4
    assert unchanged + transformed == 26


def test_transformed_scope_files_are_additive_only() -> None:
    """The four scope-check files may only gain allowlist entries, never lose a line."""
    for commit, paths in TRANSFORMED.items():
        for rel in paths:
            numstat = _git("diff", "--numstat", commit, "--", rel)
            assert numstat, rel
            added, deleted = numstat.split("\t")[:2]
            assert deleted == "0", f"{rel} deleted {deleted} lines"
            assert added == "6", f"{rel} added {added} lines, expected 6"


def test_transformed_scope_files_admit_no_runtime_prefix() -> None:
    for paths in TRANSFORMED.values():
        for rel in paths:
            body = _read(REPO / rel)
            match = re.search(r"(?im)^\s*allowed_prefixes\s*=\s*\((.*?)^\s*\)", body, re.DOTALL)
            assert match is not None, rel
            allowlist = match.group(1)
            for prefix in ("apps/", "agents/", "shared/", "services/", "migrations/", "infra/"):
                assert f'"{prefix}"' not in allowlist, f"{rel} admitted {prefix}"
            for added in (
                '"docs/design/"',
                '"scripts/verify_step66sync1_"',
                '"tests/test_step66sync1_"',
            ):
                assert added in allowlist, f"{rel} missing {added}"


def test_all_three_partner_acknowledgements_present() -> None:
    for name in (
        "step66sync1-claude-code-acknowledgement.md",
        "step66sync1-codex-acknowledgement.md",
        "step66sync1-claude-design-acknowledgement.md",
    ):
        assert (SYNC / name).is_file(), name


def test_all_final_reconciliation_artifacts_present() -> None:
    for rel in FINAL_FILES:
        assert (REPO / rel).is_file(), rel


def test_superseded_claude_code_revision_not_imported() -> None:
    """Step 66SYNC.1-A1 (828ea90) supersedes 66SYNC.1-A (1b86182); no A-era blob may survive."""
    superseded = _git("diff", "--name-only", "1b86182", CLAUDE_CODE_HEAD).splitlines()
    for rel in (path for path in superseded if path.strip()):
        old = _git("rev-parse", f"1b86182:{rel}")
        current = _git("rev-parse", f":{rel}")
        assert current != old, f"{rel} was imported at its superseded 1b86182 revision"


def test_codex_untracked_paths_absent_from_source_commit() -> None:
    tree = _git("ls-tree", "-r", "--name-only", CODEX_HEAD).splitlines()
    assert not [p for p in tree if p.startswith(".tools/")]
    assert "docs/product/platform-progress-admin-console-proposal.md" not in tree


def test_codex_untracked_paths_not_imported() -> None:
    assert not (REPO / ".tools").exists() or not any((REPO / ".tools").iterdir())
    tracked = _git("ls-files", "docs/product/platform-progress-admin-console-proposal.md")
    assert tracked == ""


def test_manifest_covers_every_imported_file() -> None:
    manifest = _read(MANIFEST)
    for source in (IMPORTED, TRANSFORMED):
        for paths in source.values():
            for rel in paths:
                assert rel in manifest, rel


def test_manifest_records_every_source_commit() -> None:
    manifest = _read(MANIFEST)
    for commit in (CLAUDE_CODE_HEAD, CODEX_HEAD, CLAUDE_DESIGN_HEAD, FINAL_HEAD):
        assert commit in manifest


def test_manifest_records_progress_transformation() -> None:
    manifest = _read(MANIFEST)
    assert "source/progress.md" in manifest
    assert "Imported unchanged:        NO" in manifest
    assert "pure append" in manifest


def test_manifest_marks_partner_evidence_unchanged() -> None:
    manifest = _read(MANIFEST)
    rows = [line for line in manifest.splitlines() if line.startswith("| `docs/")]
    rows += [line for line in manifest.splitlines() if line.startswith("| `scripts/")]
    rows += [line for line in manifest.splitlines() if line.startswith("| `tests/")]
    imported_rows = [line for line in rows if "| YES |" in line]
    assert len(imported_rows) == 22


def test_manifest_marks_new_records_not_imported() -> None:
    manifest = _read(MANIFEST)
    assert manifest.count("N/A — new canonical record") == 5


# --- historical evidence preservation ------------------------------------------------------


def test_historical_open_decision_count_preserved() -> None:
    for rel in (
        "docs/handoffs/program-sync/step66sync1-final-partner-acknowledgement.md",
        "docs/handoffs/program-sync/step66sync1-claude-code-acknowledgement.md",
    ):
        text = _read(REPO / rel)
        assert re.search(r"OPEN_PRODUCT_OWNER_DECISIONS:\s*\n?\s*3", text), rel


def test_historical_documents_do_not_claim_resolution() -> None:
    for paths in IMPORTED.values():
        for rel in paths:
            if not rel.endswith(".md"):
                continue
            text = _read(REPO / rel)
            assert "RESOLVED / BINDING" not in text, f"{rel} was rewritten with the new status"


def test_new_record_explains_the_status_transition() -> None:
    binding = _read(BINDING)
    assert "were subsequently resolved by Product Owner authorization" in binding
    assert "preserved unchanged" in binding


# --- binding decisions ---------------------------------------------------------------------


def test_decision_authority_is_product_owner() -> None:
    assert "DECISION_AUTHORITY:\nProduct Owner" in _read(BINDING)


def test_decision_date_recorded() -> None:
    assert "DECISION_DATE:\n2026-08-04" in _read(BINDING)


def test_context_id_recorded() -> None:
    assert "AIAT-SYNC-20260803-01" in _read(BINDING)


def test_canonical_baseline_recorded() -> None:
    binding = _read(BINDING)
    assert "main c1db4cc" in binding
    assert "2396c6c" in binding


def test_d1_resolved_binding() -> None:
    assert re.search(r"^D-1:\n\s*RESOLVED / BINDING$", _read(BINDING), re.MULTILINE)


def test_d2_resolved_binding() -> None:
    assert re.search(r"^D-2:\n\s*RESOLVED / BINDING$", _read(BINDING), re.MULTILINE)


def test_d3_resolved_binding() -> None:
    assert re.search(r"^D-3:\n\s*RESOLVED / BINDING$", _read(BINDING), re.MULTILINE)


def test_d1_selected_option_is_dedicated_poc_goal() -> None:
    assert "Selected:     Dedicated POC Development Goal" in _read(BINDING)


def test_d2_selected_option_is_hybrid() -> None:
    assert "Selected:     Hybrid execution model" in _read(BINDING)


def test_d3_selected_option_is_plan_only() -> None:
    assert "Selected:     Runtime LLM remains plan-only" in _read(BINDING)


def test_d1_binding_requirements_complete() -> None:
    binding = _read(BINDING)
    for req in ("D1-R1", "D1-R2", "D1-R3", "D1-R4", "D1-R5", "D1-R6", "D1-R7"):
        assert req in binding


def test_d2_binding_requirements_complete() -> None:
    binding = _read(BINDING)
    for req in ("D2-R1", "D2-R2", "D2-R3", "D2-R4", "D2-R5"):
        assert req in binding


def test_d3_binding_requirements_complete() -> None:
    binding = _read(BINDING)
    for req in ("D3-R1", "D3-R2", "D3-R3", "D3-R4", "D3-R5", "D3-R6"):
        assert req in binding


def test_d1_entry_chain_recorded() -> None:
    binding = _read(BINDING)
    for step in (
        "Product Owner Development Goal",
        "Durable POC Project",
        "Primary Work Item",
        "Workflow / Run",
        "Existing Intake Pipeline",
    ):
        assert step in binding


def test_d2_partner_roles_recorded() -> None:
    binding = _read(BINDING)
    assert "Claude Code    -> Backend / Architecture implementation partner" in binding
    assert "Codex          -> Frontend implementation partner" in binding
    assert "Claude Design  -> UX / IA / Design partner" in binding


def test_d2_activity_fields_recorded() -> None:
    binding = _read(BINDING)
    for field in (
        "assigned task",
        "actor type",
        "execution status",
        "artifact",
        "commit",
        "branch",
        "draft PR",
        "test evidence",
        "review evidence",
        "handoff evidence",
        "timestamps",
    ):
        assert field in binding


def test_all_twelve_binding_conditions_recorded() -> None:
    binding = _read(BINDING)
    for index in range(1, 13):
        assert f"B-{index:02d}" in binding


def test_open_decisions_from_step66sync1_are_zero() -> None:
    assert "OPEN_PRODUCT_OWNER_DECISIONS_FROM_STEP66SYNC1:\n0" in _read(BINDING)


def test_decision_set_complete_but_implementation_not_authorized() -> None:
    binding = _read(BINDING)
    assert "POC_SCOPE_DECISION_SET:\nCOMPLETE" in binding
    assert "POC_IMPLEMENTATION_AUTHORIZED:\nNO" in binding


# --- safety semantics ----------------------------------------------------------------------


def test_partners_are_external_not_runtime_agents() -> None:
    binding = _read(BINDING)
    assert "external AI partners" in binding
    assert "must not be presented or modelled as a runtime Agent service" in binding


def test_agent_directories_still_classified_not_implemented() -> None:
    binding = _read(BINDING)
    assert "remain classified NOT IMPLEMENTED" in binding


def test_agent_directories_actually_have_no_python() -> None:
    """Re-derive the claim rather than trusting the document."""
    for name in ("backend-agent", "frontend-agent"):
        directory = REPO / "agents" / name
        assert directory.is_dir(), name
        assert not list(directory.rglob("*.py")), name


def test_task_surface_remains_non_dispatching() -> None:
    binding = _read(BINDING)
    assert "The existing Task API and Task UI remain non-dispatching." in binding
    assert "must not be used as the Agent execution source of truth" in binding


def test_task_api_still_reports_dispatch_disabled() -> None:
    """Re-derive from source: the decision must match what the code actually does."""
    source = _read(REPO / "apps" / "orchestrator" / "src" / "task_api.py")
    assert "dispatch_enabled" in source
    assert "stream.tasks" not in source


def test_autonomous_generation_still_prohibited() -> None:
    binding = _read(BINDING)
    for phrase in (
        "runtime LLM direct patch generation",
        "runtime LLM direct test generation",
        "automatic patch application",
        "autonomous merge",
        "direct push to main",
    ):
        assert phrase in binding


def test_autonomous_generation_deferred_with_security_review() -> None:
    binding = _read(BINDING)
    assert "deferred to a separate high-risk stage" in binding
    assert "requires an independent security review" in binding
    assert "must not be folded into ordinary POC.0" in binding


def test_plan_only_control_still_present_in_code() -> None:
    """The binding decision preserves an existing control; confirm the control still exists."""
    matches = _git("grep", "-l", "generate_patch_proposal", "--", "shared", "apps")
    assert matches.strip(), "generate_patch_proposal not found in the codebase"


def test_be3_gates_default_false() -> None:
    resume = _read(REPO / "shared" / "sdk" / "tasks" / "resume_request_model.py")
    replay = _read(REPO / "shared" / "sdk" / "tasks" / "replay_request_model.py")
    assert 'os.environ.get("BE3_RESUME_API_ENABLED", "false")' in resume
    assert 'os.environ.get("BE3_RESUME_COMMAND_ENABLED", "false")' in resume
    assert 'os.environ.get("BE3_REPLAY_API_ENABLED", "false")' in replay
    assert 'os.environ.get("BE3_REPLAY_EXECUTION_ENABLED", "false")' in replay


# --- addendum ------------------------------------------------------------------------------


def test_addendum_references_previous_snapshot() -> None:
    addendum = _read(ADDENDUM)
    assert "partner-synchronized-program-state-20260803.md" in addendum
    assert "2396c6c" in addendum
    assert "step66sync1-poc-scope-binding-decisions.md" in addendum


def test_addendum_records_three_resolved_decisions() -> None:
    addendum = _read(ADDENDUM)
    for decision in ("D-1", "D-2", "D-3"):
        assert re.search(rf"^{decision}:\s+RESOLVED / BINDING", addendum, re.MULTILINE)


def test_addendum_records_zero_canonical_mismatches() -> None:
    addendum = _read(ADDENDUM)
    assert re.search(r"UNRESOLVED_CANONICAL_MISMATCHES:\s*0", addendum)
    assert re.search(r"Canonical mismatches:\s*0", addendum)


def test_addendum_records_required_status_normalization() -> None:
    addendum = _read(ADDENDUM)
    for line in (
        "STEP66SYNC1:                     PASS / CLOSED",
        "PARTNER_CONTEXT_SYNCHRONIZED:    YES",
        "POC_SCOPE_DECISIONS_COMPLETE:    YES",
        "POC_SCOPE_IMPLEMENTATION_PLAN:   NOT YET FINALIZED",
        "POC_IMPLEMENTATION:              NOT STARTED / NOT AUTHORIZED",
        "STEP66D_ARCH:                    NOT STARTED / NOT AUTHORIZED",
        "STEP67POC0:                      NOT STARTED / NOT AUTHORIZED",
        "RA2M:                            NOT STARTED / NOT AUTHORIZED",
        "BE3_RESUME_REPLAY:               DISABLED",
        "PRODUCTION_EXECUTED_TRUE_COUNT:  0",
    ):
        assert line in addendum, line


def test_addendum_does_not_upgrade_any_capability() -> None:
    addendum = _read(ADDENDUM)
    assert "No capability was upgraded" in addendum
    assert "READY:                   1" in addendum
    assert "Total:                  23" in addendum


def test_addendum_keeps_all_gaps_unauthorized() -> None:
    addendum = _read(ADDENDUM)
    assert "Authorized: 0 of 23." in addendum
    assert "Total 23 gaps" in addendum


def test_addendum_gap_partition_sums_to_twenty_three() -> None:
    addendum = _read(ADDENDUM)
    counts = []
    for pattern in (
        r"Decision input now resolved \((\d+)\)",
        r"NOT D-1/D-2/D-3 \((\d+)\)",
        r"Never had a decision dependency \((\d+)\)",
    ):
        match = re.search(pattern, addendum)
        assert match is not None, pattern
        counts.append(int(match.group(1)))
    assert sum(counts) == 23


def test_addendum_distinguishes_decisions_from_scope_finalization() -> None:
    addendum = _read(ADDENDUM)
    assert "does **not** mean the POC implementation scope is technically" in addendum


# --- precedence ----------------------------------------------------------------------------


def test_precedence_order_recorded() -> None:
    precedence = _read(PRECEDENCE)
    for line in (
        "1. Product Owner accepted binding decisions",
        "2. Current canonical program-state addendum",
        "3. Final reconciliation package",
        "4. Partner acknowledgements and evidence",
        "5. Historical snapshots",
        "6. Planning proposals",
    ):
        assert line in precedence, line


def test_precedence_excludes_non_authoritative_sources() -> None:
    precedence = _read(PRECEDENCE)
    for phrase in (
        "conversation summary",
        "design option",
        "partner recommendation",
        "planning proposal",
    ):
        assert phrase in precedence, phrase


def test_precedence_resolves_the_open_decision_conflict() -> None:
    precedence = _read(PRECEDENCE)
    assert "OPEN_PRODUCT_OWNER_DECISIONS: 3" in precedence
    assert "Tier 1 supersedes" in precedence


def test_precedence_keeps_ia_options_non_binding() -> None:
    precedence = _read(PRECEDENCE)
    assert "non-binding until a Product Owner selects it" in precedence


# --- scope boundary -------------------------------------------------------------------------


def _changed_paths() -> list[str]:
    return [
        line for line in _git("diff", "--name-only", CANONICAL_MAIN, "HEAD").splitlines() if line
    ]


def test_no_runtime_or_backend_source_changed() -> None:
    forbidden = ("apps/", "agents/", "shared/", "services/", "migrations/", "infra/")
    offenders = [p for p in _changed_paths() if p.startswith(forbidden)]
    assert offenders == []


def test_no_frontend_source_changed() -> None:
    offenders = [
        p
        for p in _changed_paths()
        if p.endswith((".tsx", ".ts", ".jsx", ".js", ".vue", ".css", ".scss"))
    ]
    assert offenders == []


def test_no_compose_or_kubernetes_manifest_changed() -> None:
    offenders = [
        p
        for p in _changed_paths()
        if "docker-compose" in p or p.startswith(("helm/", "k8s/", "charts/"))
    ]
    assert offenders == []


def test_changed_paths_are_within_the_canonicalization_scope() -> None:
    allowed_exact = {
        "source/progress.md",
        "scripts/verify_step66sync1_m1_canonicalization.py",
        "tests/test_step66sync1_m1_canonicalization.py",
    }
    allowed_prefixes = ("docs/", "scripts/verify_step66sync1_", "tests/test_step66sync1_")
    stray = [
        p for p in _changed_paths() if p not in allowed_exact and not p.startswith(allowed_prefixes)
    ]
    assert stray == []


def test_progress_record_is_append_only() -> None:
    numstat = _git("diff", "--numstat", CANONICAL_MAIN, "HEAD", "--", "source/progress.md")
    if not numstat:
        return
    added, deleted, _ = numstat.split("\t", 2)
    assert deleted == "0", f"{deleted} lines deleted from progress.md"
    assert int(added) > 0


def test_progress_record_contains_all_three_sync_sections() -> None:
    progress = _read(REPO / "source" / "progress.md")
    for heading in (
        "## Step 66SYNC.1-A — Claude Code Technical State Reconciliation",
        "## Step 66SYNC.1-A1 — Synchronization Taxonomy Correction",
        "## Step 66SYNC.1-D — Final Partner Reconciliation and Synchronization Gate",
        "## Step 66SYNC.1-M1 — Canonicalization and POC Binding Decisions",
    ):
        assert heading in progress, heading


# --- no-merge and production-count claims ---------------------------------------------------


def test_no_document_claims_the_pr_is_merged() -> None:
    for path in (BINDING, ADDENDUM, MANIFEST, PRECEDENCE, EVIDENCE):
        text = _read(path).lower()
        for phrase in ("canonical main updated", "poc.0 authorized", "merged to main"):
            assert phrase not in text, f"{path.name} claims {phrase!r}"


def test_no_document_claims_implementation_authorization() -> None:
    binding = _read(BINDING)
    for phrase in (
        "POC.0 is authorized                              -- FALSE",
        "Step 66D-ARCH is authorized                      -- FALSE",
        "Step 67POC.0 is authorized                       -- FALSE",
        "RA-2M or RA-2 implementation is authorized       -- FALSE",
    ):
        assert phrase in binding, phrase


def test_production_executed_true_count_is_zero_everywhere() -> None:
    for path in (BINDING, ADDENDUM, MANIFEST, PRECEDENCE, EVIDENCE):
        text = _read(path)
        for value in re.findall(r"production_executed_true_count[`:\s]*([0-9]+)", text, re.I):
            assert value == "0", path.name


def test_evidence_document_present_and_records_marker() -> None:
    evidence = _read(EVIDENCE)
    assert "STEP66SYNC1_M1_CANONICALIZATION_PREP_VERIFY: PASS" in evidence
