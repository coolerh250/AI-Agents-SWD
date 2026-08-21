"""Deterministic verifier for Step 66C.4-BE3-RA-2M1 identity and secret canonicalization.

Offline and read-only. Starts no container, opens no database connection, contacts no Vault, no
OIDC provider and no Kubernetes API, reads no secret, and performs no network operation other than
reading local Git objects.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
import pathlib

# AT-M2 remediation: this stage's rejection window ends where an authorized successor
# milestone takes over. Without one this is HEAD, exactly as before.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
try:
    from successor_lifecycle import frozen_artifact_is_authorized  # noqa: E402
    from successor_lifecycle import live_guard_changed_paths  # noqa: E402
except ModuleNotFoundError:  # isolated probe copies may not carry scripts/

    def live_guard_changed_paths(baseline: str) -> list[str]:
        """Strictest fallback: with no lifecycle module nothing is exempt."""
        current = "HEAD"
        return [
            line.strip().replace("\\", "/")
            for line in git("diff", "--name-only", baseline, current).splitlines()
            if line.strip()
        ]

    def frozen_artifact_is_authorized(
        _relpath: str, historical: str, current: str
    ) -> tuple[bool, str]:
        """Strictest fallback: with no lifecycle module nothing may diverge at all."""
        return historical == current, "no freeze-amendment authority is available"


MARKER = "STEP66C4_BE3_RA2M_CANONICALIZATION_PREP_VERIFY: PASS"

ROOT = Path(__file__).resolve().parents[1]

CANONICAL_MAIN = "44ab32ceab60d417ef1e0800be6cd00fc730b12e"

# Step 66D-ALIGN1-RM1 fixed stage boundary. This stage's scope is the frozen commit
# range below -- never "baseline -> current HEAD". Later authorized stages advance
# main; they cannot widen, narrow or drift what THIS stage is proven to have changed.
# The expected path set is the immutable manifest of that range. Both values are
# cross-checked against the RM1 stage-boundary manifest.
STAGE_BASELINE = "44ab32ceab60d417ef1e0800be6cd00fc730b12e"
STAGE_HEAD = "edafc0ca9111bc6dd76bc3ab59b5ea110f2f05d6"
EXPECTED_STAGE_PATHS = (
    "docs/alignment/66-project-completion/master/canonical-source-of-truth-precedence.md",
    "docs/alignment/66-project-completion/master/next-executable-stage-sequence.md",
    "docs/alignment/66-project-completion/master/step66c4-be3-ra2-current-state-20260804.md",
    "docs/contracts/66c4-reminder-expiry-controlled-resume/be3-ra2-identity-secret-provisioning-decision-package.md",
    "docs/contracts/66c4-reminder-expiry-controlled-resume/step66c4-be3-ra2-binding-decisions.md",
    "docs/handoffs/66c4-reminder-expiry-controlled-resume/be3-ra2-implementation-stage-decomposition.md",
    "docs/handoffs/66c4-reminder-expiry-controlled-resume/step66c4-be3-ra2m-canonicalization-manifest.md",
    "docs/security/be3-ra2-current-state-identity-secret-inventory.md",
    "docs/security/be3-ra2-identity-secret-threat-and-trust-analysis.md",
    "docs/test/step66c4-be3-ra2-identity-secret-decision-evidence.md",
    "docs/test/step66c4-be3-ra2m-canonicalization-evidence.md",
    "scripts/verify_step66c4_be3_ra2_identity_secret_decision.py",
    "scripts/verify_step66c4_be3_ra2m_canonicalization.py",
    "source/progress.md",
    "tests/test_step66c4_be3_ra2_identity_secret_decision.py",
    "tests/test_step66c4_be3_ra2m_canonicalization.py",
)

PLANNING_HEAD = "efa396dee6512d6f15b3fd079df87d2c70ee0c77"
PLANNING_BASE = "c1db4ccbfd88fa775e4761c932835896b9b980ed"

SECURITY = ROOT / "docs" / "security"
CONTRACTS = ROOT / "docs" / "contracts" / "66c4-reminder-expiry-controlled-resume"
HANDOFFS = ROOT / "docs" / "handoffs" / "66c4-reminder-expiry-controlled-resume"
MASTER = ROOT / "docs" / "alignment" / "66-project-completion" / "master"
TEST_DOCS = ROOT / "docs" / "test"

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

RESUME_MODEL = ROOT / "shared" / "sdk" / "tasks" / "resume_request_model.py"
REPLAY_MODEL = ROOT / "shared" / "sdk" / "tasks" / "replay_request_model.py"

FORBIDDEN_SOURCE_PREFIXES = (
    "apps/",
    "agents/",
    "shared/",
    "services/",
    "migrations/",
    "infra/",
)

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

UNAUTHORIZED_STAGES = (
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

FAILURES: list[str] = []


def bad(message: str) -> None:
    FAILURES.append(message)


def git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def read(path: Path) -> str:
    if not path.is_file():
        bad(f"missing required file: {path.relative_to(ROOT).as_posix()}")
        return ""
    return path.read_text(encoding="utf-8")


def git_blob_text(commit: str, rel: str) -> str:
    """A committed blob as UTF-8 text, independent of the console code page."""
    result = subprocess.run(
        ["git", "show", f"{commit}:{rel}"],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return result.stdout.decode("utf-8") if result.returncode == 0 else ""


def check01_baseline_main() -> None:
    reachable = subprocess.run(
        ["git", "merge-base", "--is-ancestor", CANONICAL_MAIN, "HEAD"],
        cwd=ROOT,
        check=False,
    )
    if reachable.returncode != 0:
        bad("check01: canonical baseline 44ab32c is not an ancestor of HEAD")
    if git("cat-file", "-t", CANONICAL_MAIN) != "commit":
        bad("check01: canonical baseline 44ab32c is not a reachable commit")


def check02_planning_source() -> None:
    if git("rev-parse", f"{PLANNING_HEAD}^{{commit}}") != PLANNING_HEAD:
        bad("check02: RA-2 planning source efa396d does not resolve to a commit")
    branch_head = git("rev-parse", "origin/planning/66c4-be3-ra2-identity-secret-decision")
    if branch_head and branch_head != PLANNING_HEAD:
        bad("check02: the RA-2 planning branch head is no longer efa396d")


def check03_planning_artifacts_present() -> None:
    for path in (INVENTORY, THREAT_MODEL, DECISION_PACKAGE, STAGE_PROPOSAL, PLANNING_EVIDENCE):
        if not path.is_file():
            bad(f"check03: missing RA-2 planning artifact {path.name}")


def check04_historical_evidence_not_rewritten() -> None:
    for rel in IMPORTED_UNCHANGED:
        source = git("rev-parse", f"{PLANNING_HEAD}:{rel}")
        if not source:
            bad(f"check04: {rel} not found in planning commit efa396d")
            continue
        if git("rev-parse", f":{rel}") == source:
            continue
        # Divergence is a rewrite unless AT-D12 names this exact path as amendable and the
        # divergence matches the shape it declared. Fail-closed with no such authority.
        allowed, why = frozen_artifact_is_authorized(
            rel, git_blob_text(PLANNING_HEAD, rel), (ROOT / rel).read_text(encoding="utf-8")
        )
        if not allowed:
            bad(f"check04: {rel} was rewritten -- blob differs from efa396d ({why})")

    package = read(DECISION_PACKAGE)
    if "PENDING" not in package:
        bad("check04: the decision package no longer records PENDING selections")
    if "RESOLVED / BINDING" in package:
        bad("check04: the decision package was rewritten with the new binding status")
    for path in (INVENTORY, THREAT_MODEL, STAGE_PROPOSAL, PLANNING_EVIDENCE):
        if "RESOLVED / BINDING" in read(path):
            bad(f"check04: historical evidence {path.name} was rewritten with the new status")


def check05_all_decisions_present() -> None:
    binding = read(BINDING)
    for decision in DECISIONS:
        if decision not in binding:
            bad(f"check05: {decision} is missing from the binding decision record")


def check06_all_decisions_binding() -> None:
    binding = read(BINDING)
    for decision in DECISIONS:
        block = re.search(rf"^## {decision} —.*?(?=^## |\Z)", binding, re.MULTILINE | re.DOTALL)
        if block is None:
            bad(f"check06: {decision} has no section in the binding decision record")
            continue
        if not re.search(r"STATUS:\s+RESOLVED / BINDING", block.group(0)):
            bad(f"check06: {decision} is not recorded RESOLVED / BINDING")
    if "DECISION_AUTHORITY:\nProduct Owner" not in binding:
        bad("check06: decision authority is not recorded as Product Owner")
    if "RA2_D01_D12:\nRESOLVED / BINDING" not in binding:
        bad("check06: the D01-D12 summary status is not RESOLVED / BINDING")


def check07_conditions_present_and_binding() -> None:
    binding = read(BINDING)
    for condition in CONDITIONS:
        if condition not in binding:
            bad(f"check07: {condition} is missing from the binding decision record")
    if "RA2_C01_C06:\nRESOLVED / BINDING" not in binding:
        bad("check07: the C01-C06 summary status is not RESOLVED / BINDING")


def _selection(binding: str, decision: str) -> str:
    block = re.search(rf"^## {decision} —.*?(?=^## |\Z)", binding, re.MULTILINE | re.DOTALL)
    return block.group(0) if block else ""


def check08_to_19_selections() -> None:
    binding = read(BINDING)
    expectations = (
        ("check08", "RA2-D01", ("Enterprise OIDC", "existing enterprise Identity Provider")),
        (
            "check09",
            "RA2-D02",
            ("Authorization Code Flow with PKCE", "server-side session"),
        ),
        ("check10", "RA2-D03", ("Platform-owned RBAC is the authorization source of truth",)),
        ("check11", "RA2-D04", ("projected ServiceAccount OIDC",)),
        ("check12", "RA2-D05", ("same projected workload OIDC model",)),
        ("check13", "RA2-D06", ("HashiCorp Vault, non-dev", "Kubernetes workload identity")),
        (
            "check14",
            "RA2-D07",
            ("Vault Agent versus CSI is NOT selected", "RA-2I4P"),
        ),
        (
            "check15",
            "RA2-D08",
            (
                "GitOps-controlled provisioning",
                "Platform Security",
                "Enterprise IAM",
                "two-person approval",
            ),
        ),
        ("check16", "RA2-D09", ("Credential-specific lifecycle controls",)),
        ("check17", "RA2-D10", ("Dedicated human break-glass identity", "hardware MFA")),
        ("check18", "RA2-D11", ("isolated non-production Kubernetes",)),
        (
            "check19",
            "RA2-D12",
            ("Activation is not allowed until the complete chain is validated",),
        ),
    )
    for number, decision, needles in expectations:
        block = _selection(binding, decision)
        if not block:
            bad(f"{number}: {decision} section not found")
            continue
        flat = re.sub(r"\s+", " ", block)
        for needle in needles:
            if re.sub(r"\s+", " ", needle) not in flat:
                bad(f"{number}: {decision} does not record {needle!r}")


def check20_hmac_local_test_only() -> None:
    block = _selection(read(BINDING), "RA2-D05")
    if "LOCAL / TEST ONLY" not in block or "DISABLED IN SHARED RUNTIME" not in block:
        bad("check20: the HMAC mechanism is not restricted to local/test and disabled in shared")
    if "must never be the primary identity mechanism in shared" not in block:
        bad("check20: long-lived HMAC bearer secrets are not forbidden as primary identity")


def check21_request_actor_not_trusted() -> None:
    binding = read(BINDING)
    if "RA2-C02" not in binding:
        bad("check21: RA2-C02 is missing")
        return
    condition = re.search(r"RA2-C02\s+(.*?)(?=RA2-C03)", binding, re.DOTALL)
    flat = re.sub(r"\s+", " ", condition.group(1)) if condition else ""
    if "never an authorization identity" not in flat:
        bad("check21: RA2-C02 does not forbid request-provided actor/role as identity")
    if "never an authoritative audit identity" not in flat:
        bad("check21: RA2-C02 does not forbid request-provided actor/role as audit identity")


def check22_no_static_service_identity_secret() -> None:
    binding = read(BINDING)
    condition = re.search(r"RA2-C03\s+(.*?)(?=RA2-C04)", binding, re.DOTALL)
    if condition is None or "static shared Service Identity secret" not in condition.group(1):
        bad("check22: RA2-C03 does not forbid a static shared Service Identity secret")
    if "No static shared service credential may act as a shared runtime identity" not in binding:
        bad("check22: RA2-D04 does not forbid static shared service credentials")


def check23_no_vault_dev_or_root_token() -> None:
    binding = read(BINDING)
    condition = re.search(r"RA2-C04\s+(.*?)(?=RA2-C05)", binding, re.DOTALL)
    if condition is None:
        bad("check23: RA2-C04 is missing")
        return
    text = condition.group(1)
    for needle in ("Vault dev mode", "root token", "static Vault token"):
        if needle not in text:
            bad(f"check23: RA2-C04 does not forbid {needle}")


def check24_no_resume_replay_before_ra2r() -> None:
    binding = read(BINDING)
    condition = re.search(r"RA2-C05\s+(.*?)(?=RA2-C06)", binding, re.DOTALL)
    if condition is None or "RA-2R" not in condition.group(1):
        bad("check24: RA2-C05 does not gate resume/replay on RA-2R")
    if "BE3_RESUME_REPLAY:              DISABLED" not in binding:
        bad("check24: BE3 resume/replay is not recorded DISABLED")


def check25_sequence_recorded_without_authorization() -> None:
    binding = read(BINDING)
    if "APPROVED EXECUTION SEQUENCE" not in binding:
        bad("check25: the implementation sequence is not recorded")
    if "NOT IMPLEMENTATION AUTHORIZATION" not in binding:
        bad("check25: the sequence is not explicitly marked as non-authorizing")
    order = [
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
    chain = re.search(r"RA-2M\n(?:\s*->\s*RA-[\w]+\n)+", binding)
    if chain is None:
        bad("check25: the authorized execution chain block was not found")
    else:
        listed = re.findall(r"RA-[\w]+", chain.group(0))
        if listed != order:
            bad(f"check25: the recorded sequence is not in the authorized order: {listed}")
    if "RA2_IMPLEMENTATION:\nNOT STARTED / NOT AUTHORIZED" not in binding:
        bad("check25: RA-2 implementation is not recorded NOT STARTED / NOT AUTHORIZED")


def check26_every_stage_unauthorized() -> None:
    binding = read(BINDING)
    for stage in UNAUTHORIZED_STAGES:
        if not re.search(rf"^{stage}:\s+NOT AUTHORIZED$", binding, re.MULTILINE):
            bad(f"check26: {stage} is not recorded NOT AUTHORIZED")
    addendum = read(ADDENDUM)
    if "Implementation stages authorized: 0 of 11" not in addendum:
        bad("check26: the addendum does not record 0 of 11 stages authorized")


def check27_be3_gates_default_false() -> None:
    for var, gate_file in (
        ("BE3_RESUME_API_ENABLED", RESUME_MODEL),
        ("BE3_RESUME_COMMAND_ENABLED", RESUME_MODEL),
        ("BE3_REPLAY_API_ENABLED", REPLAY_MODEL),
        ("BE3_REPLAY_EXECUTION_ENABLED", REPLAY_MODEL),
    ):
        if not gate_file.is_file():
            bad(f"check27: gate file missing: {gate_file.name}")
            continue
        if f'os.environ.get("{var}", "false")' not in gate_file.read_text(encoding="utf-8"):
            bad(f"check27: {var} default is not 'false' in {gate_file.name}")


def check28_no_implementation_change() -> None:
    changed = [
        line
        for line in git("diff", "--name-only", STAGE_BASELINE, STAGE_HEAD).splitlines()
        if line.strip()
    ]
    offenders = [path for path in changed if path.startswith(FORBIDDEN_SOURCE_PREFIXES)]
    if offenders:
        bad(f"check28: runtime/source paths changed: {', '.join(sorted(offenders))}")

    frontend = [
        path
        for path in changed
        if path.endswith((".tsx", ".ts", ".jsx", ".js", ".vue", ".css", ".scss"))
    ]
    if frontend:
        bad(f"check28: frontend source changed: {', '.join(frontend)}")

    infra = [
        path
        for path in changed
        if "docker-compose" in path
        or path.startswith(("helm/", "k8s/", "charts/"))
        or path.endswith((".yaml", ".yml"))
    ]
    if infra:
        bad(f"check28: infra/manifest paths changed: {', '.join(infra)}")

    # Step 66D-ALIGN1-RM1: exact-set comparison over the FIXED range. Nothing passes on
    # the strength of a directory or filename prefix; an unregistered path fails here.
    _actual = tuple(sorted(changed))
    _unexpected = sorted(set(_actual) - set(EXPECTED_STAGE_PATHS))
    _missing = sorted(set(EXPECTED_STAGE_PATHS) - set(_actual))
    if _unexpected:
        bad(f"check28: unregistered path in this stage's fixed range: {', '.join(_unexpected)}")
    if _missing:
        bad(
            f"check28: registered path missing from this stage's fixed range: {', '.join(_missing)}"
        )

    numstat = git("diff", "--numstat", CANONICAL_MAIN, "--", "source/progress.md")
    if numstat:
        parts = numstat.split("\t")
        if len(parts) >= 2 and parts[1] != "0":
            bad(f"check28: source/progress.md is not append-only ({parts[1]} lines deleted)")


def check29_production_count_zero() -> None:
    for path in (BINDING, ADDENDUM, MANIFEST, EVIDENCE):
        text = read(path)
        if not text:
            continue
        for value in re.findall(r"production_executed_true_count[`:\s]*([0-9]+)", text, re.I):
            if value != "0":
                bad(f"check29: {path.name} records production_executed_true_count {value}")
        for value in re.findall(r"PRODUCTION_EXECUTED_TRUE_COUNT:\s*\n?\s*([0-9]+)", text):
            if value != "0":
                bad(f"check29: {path.name} records PRODUCTION_EXECUTED_TRUE_COUNT {value}")


def check30_manifest_covers_everything() -> None:
    manifest = read(MANIFEST)
    for rel in IMPORTED_UNCHANGED:
        if rel not in manifest:
            bad(f"check30: manifest does not cover imported artifact {rel}")
    if "source/progress.md" not in manifest:
        bad("check30: manifest does not record the transformed source/progress.md import")
    for rel in (
        "docs/contracts/66c4-reminder-expiry-controlled-resume/"
        "step66c4-be3-ra2-binding-decisions.md",
        "docs/alignment/66-project-completion/master/step66c4-be3-ra2-current-state-20260804.md",
        "docs/handoffs/66c4-reminder-expiry-controlled-resume/"
        "step66c4-be3-ra2m-canonicalization-manifest.md",
        "docs/test/step66c4-be3-ra2m-canonicalization-evidence.md",
    ):
        if rel not in manifest:
            bad(f"check30: manifest does not record new canonical record {rel}")
    for commit in (PLANNING_HEAD[:7], CANONICAL_MAIN[:7], PLANNING_BASE[:7]):
        if commit not in manifest:
            bad(f"check30: manifest does not record commit {commit}")


def check_precedence_recorded() -> None:
    precedence = read(PRECEDENCE)
    for line in (
        "1. Product Owner binding decisions",
        "2. Current RA-2 canonical state addendum",
        "3. RA-2 binding decision record's implementation sequence",
        "4. Historical RA-2 planning evidence",
        "5. Partner recommendations",
        "6. Conversation summaries",
    ):
        if line not in precedence:
            bad(f"precedence: missing RA-2 tier line {line!r}")
    if "never an implementation authorization" not in precedence:
        bad("precedence: does not state that a planning recommendation is not an authorization")


def check_no_false_claims() -> None:
    for path in (BINDING, ADDENDUM, MANIFEST, EVIDENCE, PRECEDENCE):
        text = read(path).lower()
        if not text:
            continue
        for phrase in (
            "oidc is implemented",
            "vault is deployed",
            "service identity is active",
            "shared environment is ready",
            "resume/replay is enabled",
        ):
            for match in re.finditer(re.escape(phrase), text):
                window = text[match.end() : match.end() + 100]
                if "false" not in window and "not " not in window:
                    bad(f"no-false-claims: {path.name} appears to claim {phrase!r}")


# Step 66D-ALIGN1-RM1: the stage SCOPE above is frozen, which is what stops it drifting.
# The runtime denylist must not be frozen with it -- a runtime path added by any later
# commit still has to be caught. This anchor is deliberately HEAD-relative, and it feeds
# the denylist only; it never widens or satisfies the stage scope.
RUNTIME_GUARD_ANCHOR = "44ab32ceab60d417ef1e0800be6cd00fc730b12e"


def check_runtime_guard_current_state() -> None:
    """Reject runtime/frontend/infra paths introduced at any point after this stage's baseline."""
    changed = live_guard_changed_paths(RUNTIME_GUARD_ANCHOR)
    offenders = [
        path
        for path in changed
        if path.startswith(("apps/", "agents/", "services/", "shared/", "migrations/", "infra/"))
        or path.endswith((".tsx", ".jsx", ".vue", ".yaml", ".yml", ".sql"))
        or "docker-compose" in path
        or path.startswith(("helm/", "k8s/", "charts/"))
    ]
    if offenders:
        bad(
            f"runtime-guard: protected path present after this stage: {', '.join(sorted(offenders))}"
        )


def main() -> int:
    check01_baseline_main()
    check02_planning_source()
    check03_planning_artifacts_present()
    check04_historical_evidence_not_rewritten()
    check05_all_decisions_present()
    check06_all_decisions_binding()
    check07_conditions_present_and_binding()
    check08_to_19_selections()
    check20_hmac_local_test_only()
    check21_request_actor_not_trusted()
    check22_no_static_service_identity_secret()
    check23_no_vault_dev_or_root_token()
    check24_no_resume_replay_before_ra2r()
    check25_sequence_recorded_without_authorization()
    check26_every_stage_unauthorized()
    check27_be3_gates_default_false()
    check28_no_implementation_change()
    check29_production_count_zero()
    check30_manifest_covers_everything()
    check_precedence_recorded()
    check_no_false_claims()

    check_runtime_guard_current_state()

    if FAILURES:
        for failure in dict.fromkeys(FAILURES):
            print(f"VERIFY FAILED: {failure}", file=sys.stderr)
        return 1
    print(MARKER)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
