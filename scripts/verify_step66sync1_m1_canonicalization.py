"""Deterministic verifier for Step 66SYNC.1-M1 canonicalization preparation.

Offline and read-only. Starts no container, opens no database connection, reads no secret,
and performs no network operation other than reading local Git objects.
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


MARKER = "STEP66SYNC1_M1_CANONICALIZATION_PREP_VERIFY: PASS"

ROOT = Path(__file__).resolve().parents[1]

CANONICAL_MAIN = "c1db4ccbfd88fa775e4761c932835896b9b980ed"

# Step 66D-ALIGN1-RM1 fixed stage boundary. This stage's scope is the frozen commit
# range below -- never "baseline -> current HEAD". Later authorized stages advance
# main; they cannot widen, narrow or drift what THIS stage is proven to have changed.
# The expected path set is the immutable manifest of that range. Both values are
# cross-checked against the RM1 stage-boundary manifest.
STAGE_BASELINE = "c1db4ccbfd88fa775e4761c932835896b9b980ed"
STAGE_HEAD = "1278b8944e3a8f824a9b35f82382fa8587e7989d"
EXPECTED_STAGE_PATHS = (
    "docs/alignment/66-project-completion/master/canonical-source-of-truth-precedence.md",
    "docs/alignment/66-project-completion/master/partner-context-snapshot-20260803.md",
    "docs/alignment/66-project-completion/master/partner-synchronized-program-state-20260803.md",
    "docs/alignment/66-project-completion/master/partner-synchronized-program-state-20260804.md",
    "docs/design/ai-agent-team-functional-poc-control-center-spec.md",
    "docs/handoffs/program-sync/step66sync1-canonicalization-manifest.md",
    "docs/handoffs/program-sync/step66sync1-claude-code-acknowledgement.md",
    "docs/handoffs/program-sync/step66sync1-claude-design-acknowledgement.md",
    "docs/handoffs/program-sync/step66sync1-claude-design-ux-gap-register.md",
    "docs/handoffs/program-sync/step66sync1-codex-acknowledgement.md",
    "docs/handoffs/program-sync/step66sync1-codex-frontend-gap-register.md",
    "docs/handoffs/program-sync/step66sync1-context-discrepancy-register.md",
    "docs/handoffs/program-sync/step66sync1-final-context-discrepancy-register.md",
    "docs/handoffs/program-sync/step66sync1-final-partner-acknowledgement.md",
    "docs/handoffs/program-sync/step66sync1-poc-backend-readiness-matrix.md",
    "docs/handoffs/program-sync/step66sync1-poc-scope-binding-decisions.md",
    "docs/handoffs/program-sync/step66sync1-poc-scope-decision-package.md",
    "docs/handoffs/program-sync/step66sync1-poc0-consolidated-gap-register.md",
    "docs/test/step66sync1-claude-code-reconciliation-evidence.md",
    "docs/test/step66sync1-claude-design-reconciliation-evidence.md",
    "docs/test/step66sync1-codex-frontend-reconciliation-evidence.md",
    "docs/test/step66sync1-final-partner-reconciliation-evidence.md",
    "docs/test/step66sync1-m1-canonicalization-evidence.md",
    "scripts/verify_step66sync1_claude_code_reconciliation.py",
    "scripts/verify_step66sync1_claude_design_reconciliation.py",
    "scripts/verify_step66sync1_codex_frontend_reconciliation.py",
    "scripts/verify_step66sync1_final_partner_reconciliation.py",
    "scripts/verify_step66sync1_m1_canonicalization.py",
    "source/progress.md",
    "tests/test_step66sync1_claude_code_reconciliation.py",
    "tests/test_step66sync1_claude_design_reconciliation.py",
    "tests/test_step66sync1_codex_frontend_reconciliation.py",
    "tests/test_step66sync1_final_partner_reconciliation.py",
    "tests/test_step66sync1_m1_canonicalization.py",
)

CLAUDE_CODE_HEAD = "828ea90"
CODEX_HEAD = "78aa4ee"
CLAUDE_DESIGN_HEAD = "65c93a1"
FINAL_HEAD = "2396c6c"
RA2_HEAD = "efa396d"

SYNC = ROOT / "docs" / "handoffs" / "program-sync"
MASTER = ROOT / "docs" / "alignment" / "66-project-completion" / "master"
TEST_DOCS = ROOT / "docs" / "test"

BINDING = SYNC / "step66sync1-poc-scope-binding-decisions.md"
ADDENDUM = MASTER / "partner-synchronized-program-state-20260804.md"
PRECEDENCE = MASTER / "canonical-source-of-truth-precedence.md"
MANIFEST = SYNC / "step66sync1-canonicalization-manifest.md"
EVIDENCE = TEST_DOCS / "step66sync1-m1-canonicalization-evidence.md"

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

IMPORTED = {
    CLAUDE_CODE_HEAD: (
        "docs/alignment/66-project-completion/master/partner-context-snapshot-20260803.md",
        "docs/handoffs/program-sync/step66sync1-claude-code-acknowledgement.md",
        "docs/handoffs/program-sync/step66sync1-context-discrepancy-register.md",
        "docs/handoffs/program-sync/step66sync1-poc-backend-readiness-matrix.md",
        "docs/test/step66sync1-claude-code-reconciliation-evidence.md",
    ),
    CODEX_HEAD: (
        "docs/handoffs/program-sync/step66sync1-codex-acknowledgement.md",
        "docs/handoffs/program-sync/step66sync1-codex-frontend-gap-register.md",
        "docs/test/step66sync1-codex-frontend-reconciliation-evidence.md",
        "scripts/verify_step66sync1_codex_frontend_reconciliation.py",
        "tests/test_step66sync1_codex_frontend_reconciliation.py",
    ),
    CLAUDE_DESIGN_HEAD: (
        "docs/handoffs/program-sync/step66sync1-claude-design-acknowledgement.md",
        "docs/test/step66sync1-claude-design-reconciliation-evidence.md",
        "scripts/verify_step66sync1_claude_design_reconciliation.py",
        "tests/test_step66sync1_claude_design_reconciliation.py",
    ),
    FINAL_HEAD: (
        "docs/alignment/66-project-completion/master/"
        "partner-synchronized-program-state-20260803.md",
        "docs/handoffs/program-sync/step66sync1-final-partner-acknowledgement.md",
        "docs/handoffs/program-sync/step66sync1-final-context-discrepancy-register.md",
        "docs/handoffs/program-sync/step66sync1-poc-scope-decision-package.md",
        "docs/test/step66sync1-final-partner-reconciliation-evidence.md",
    ),
}

# Step 66D-ALIGN1 annotated these three with an append-only supersession note. Their original
# content must still be a byte-exact PREFIX of the current file -- nothing above the marker may
# change -- and everything after the marker is the note. This is stricter than "not rewritten"
# for the original portion, and is verified as such rather than by whole-blob identity.
ANNOTATED = {
    CLAUDE_DESIGN_HEAD: (
        "docs/design/ai-agent-team-functional-poc-control-center-spec.md",
        "docs/handoffs/program-sync/step66sync1-claude-design-ux-gap-register.md",
    ),
    FINAL_HEAD: ("docs/handoffs/program-sync/step66sync1-poc0-consolidated-gap-register.md",),
}

ANNOTATION_MARKER = "<!-- SUPERSESSION-NOTE-BEGIN: Step 66D-ALIGN1 -->"

# Four partner scope-check files carry a recorded transformation. Step 66SYNC.1-M1 widened their
# branch-scoped ALLOWED_PREFIXES tuple; Step 66D-ALIGN1-RM1 removed that tuple entirely and
# replaced it with a frozen commit range plus an exact registered path set. No runtime prefix was
# admitted at any point.
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

# Step 66D-ALIGN1-RM1 superseded the earlier prefix-widening transformation. These four partner
# scope files no longer carry a branch-scoped prefix allowlist at all: their scope is now a frozen
# commit range plus an exact registered path set. The gate below verifies that stricter shape and
# refuses the generic prefixes outright, so the widening cannot be reintroduced.
TRANSFORM_REQUIRED_MARKERS = (
    "STAGE_BASELINE = ",
    "STAGE_HEAD = ",
    "EXPECTED_STAGE_PATHS = (",
)
TRANSFORM_FORBIDDEN_PREFIXES = (
    '"docs/",',
    '"scripts/verify_step66",',
    '"tests/test_step66",',
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


def check01_baseline_main() -> None:
    # c1db4cc is the canonical *pre-merge* baseline. Before Step 66SYNC.1-M2 it was origin/main
    # itself; after the merge it is the merge commit's first parent. Ancestry holds in both cases,
    # equality only in the first, so ancestry is the assertion that stays true and still fails if
    # this branch is ever cut from an unrelated baseline.
    baseline_reachable = subprocess.run(
        ["git", "merge-base", "--is-ancestor", CANONICAL_MAIN, "origin/main"],
        cwd=ROOT,
        check=False,
    )
    if baseline_reachable.returncode != 0:
        bad("check01: canonical baseline c1db4cc is not contained in origin/main")
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", CANONICAL_MAIN, "HEAD"],
        cwd=ROOT,
        check=False,
    )
    if ancestor.returncode != 0:
        bad("check01: canonical main c1db4cc is not an ancestor of HEAD")


def _head_check(number: str, short: str, label: str) -> None:
    resolved = git("rev-parse", f"{short}^{{commit}}")
    if not resolved.startswith(short):
        bad(f"{number}: {label} head {short} does not resolve to a commit")


def check02_to_06_partner_heads() -> None:
    _head_check("check02", CLAUDE_CODE_HEAD, "Claude Code")
    _head_check("check03", CODEX_HEAD, "Codex")
    _head_check("check04", CLAUDE_DESIGN_HEAD, "Claude Design")
    _head_check("check05", FINAL_HEAD, "final reconciliation")
    _head_check("check06", RA2_HEAD, "RA-2 planning")
    if git("rev-parse", "origin/planning/66c4-be3-ra2-identity-secret-decision")[:7] != RA2_HEAD:
        bad("check06: RA-2 planning branch head is no longer efa396d")


def check07_acknowledgements_present() -> None:
    for name in (
        "step66sync1-claude-code-acknowledgement.md",
        "step66sync1-codex-acknowledgement.md",
        "step66sync1-claude-design-acknowledgement.md",
    ):
        if not (SYNC / name).is_file():
            bad(f"check07: missing partner acknowledgement {name}")


def check08_final_artifacts_present() -> None:
    for path in (
        MASTER / "partner-synchronized-program-state-20260803.md",
        SYNC / "step66sync1-final-partner-acknowledgement.md",
        SYNC / "step66sync1-final-context-discrepancy-register.md",
        SYNC / "step66sync1-poc-scope-decision-package.md",
        SYNC / "step66sync1-poc0-consolidated-gap-register.md",
        TEST_DOCS / "step66sync1-final-partner-reconciliation-evidence.md",
    ):
        if not path.is_file():
            bad(f"check08: missing final reconciliation artifact {path.name}")


def _stage_scope_block(body: str) -> str | None:
    """Return the text of the file's registered stage-scope tuple, or None if absent."""
    match = re.search(r"(?m)^EXPECTED_STAGE_PATHS\s*=\s*\((.*?)^\)", body, re.DOTALL)
    return match.group(1) if match else None


def _norm(text: str) -> str:
    """Compare content independently of checkout line endings."""
    return text.replace("\r\n", "\n").strip()


def git_blob_text(commit: str, rel: str) -> str:
    """Read a committed blob as UTF-8, independent of the console code page."""
    result = subprocess.run(
        ["git", "show", f"{commit}:{rel}"],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        return ""
    return result.stdout.decode("utf-8")


def check09_historical_artifacts_unchanged() -> None:
    for commit, paths in IMPORTED.items():
        for rel in paths:
            source = git("rev-parse", f"{commit}:{rel}")
            if not source:
                bad(f"check09: {rel} not found in source commit {commit}")
                continue
            if git("rev-parse", f":{rel}") == source:
                continue
            # Divergence is a rewrite unless AT-D12 names this exact path as amendable and the
            # divergence matches the shape it declared. Fail-closed with no such authority.
            allowed, why = frozen_artifact_is_authorized(
                rel, git_blob_text(commit, rel), (ROOT / rel).read_text(encoding="utf-8")
            )
            if not allowed:
                bad(
                    f"check09: {rel} was rewritten -- blob differs from source commit "
                    f"{commit} ({why})"
                )

    for commit, paths in TRANSFORMED.items():
        for rel in paths:
            numstat = git("diff", "--numstat", commit, "--", rel)
            if not numstat:
                bad(f"check09: expected a recorded transformation in {rel}, found none")
                continue
            body = (ROOT / rel).read_text(encoding="utf-8")
            for marker in TRANSFORM_REQUIRED_MARKERS:
                if marker not in body:
                    bad(f"check09: {rel} has no fixed stage boundary; missing {marker!r}")
            for generic in TRANSFORM_FORBIDDEN_PREFIXES:
                if generic in body:
                    bad(f"check09: {rel} reintroduced the generic prefix allowlist {generic}")
            scope_block = _stage_scope_block(body)
            if scope_block is None:
                bad(f"check09: {rel} has no recognisable EXPECTED_STAGE_PATHS tuple")
                continue
            for runtime_prefix in FORBIDDEN_SOURCE_PREFIXES:
                if f'"{runtime_prefix}' in scope_block:
                    bad(f"check09: {rel} registered scope admitted runtime prefix {runtime_prefix}")

    for commit, paths in ANNOTATED.items():
        for rel in paths:
            original = git_blob_text(commit, rel)
            current = (ROOT / rel).read_text(encoding="utf-8")
            if not original:
                bad(f"check09: {rel} not found in source commit {commit}")
                continue
            if ANNOTATION_MARKER not in current:
                bad(f"check09: {rel} is missing the Step 66D-ALIGN1 annotation marker")
                continue
            head, _, _ = current.partition(ANNOTATION_MARKER)
            if _norm(head) != _norm(original):
                bad(f"check09: {rel} content above the annotation marker was modified")
            numstat = git("diff", "--numstat", commit, "--", rel)
            if numstat:
                deleted = numstat.split("\t")[1]
                if deleted != "0":
                    bad(f"check09: {rel} annotation deleted {deleted} line(s); must be additive")

    ack = read(SYNC / "step66sync1-final-partner-acknowledgement.md")
    if "OPEN_PRODUCT_OWNER_DECISIONS:\n3" not in ack:
        bad("check09: historical open-decision count was edited in the final acknowledgement")


def check10_manifest_covers_all_imports() -> None:
    manifest = read(MANIFEST)
    for source in (IMPORTED, TRANSFORMED, ANNOTATED):
        for paths in source.values():
            for rel in paths:
                if rel not in manifest:
                    bad(f"check10: canonicalization manifest does not cover {rel}")
    if "source/progress.md" not in manifest:
        bad("check10: manifest does not record the transformed source/progress.md import")
    for commit in (CLAUDE_CODE_HEAD, CODEX_HEAD, CLAUDE_DESIGN_HEAD, FINAL_HEAD):
        if commit not in manifest:
            bad(f"check10: manifest does not record source commit {commit}")


def check11_to_13_decisions_binding() -> None:
    binding = read(BINDING)
    for number, decision in (("check11", "D-1"), ("check12", "D-2"), ("check13", "D-3")):
        if not re.search(rf"^{decision}:\n\s*RESOLVED / BINDING$", binding, re.MULTILINE):
            bad(f"{number}: {decision} is not recorded RESOLVED / BINDING")
    if "DECISION_AUTHORITY:\nProduct Owner" not in binding:
        bad("check11: decision authority is not recorded as Product Owner")
    if "OPEN_PRODUCT_OWNER_DECISIONS_FROM_STEP66SYNC1:\n0" not in binding:
        bad("check11: open Step 66SYNC.1 decisions are not recorded as 0")


def check14_to_16_selected_options() -> None:
    binding = read(BINDING)
    for number, needle, label in (
        ("check14", "Selected:     Dedicated POC Development Goal", "D-1 dedicated POC goal"),
        ("check15", "Selected:     Hybrid execution model", "D-2 hybrid execution model"),
        (
            "check16",
            "Selected:     Runtime LLM remains plan-only",
            "D-3 runtime LLM plan-only",
        ),
    ):
        if needle not in binding:
            bad(f"{number}: {label} is not recorded as the selected option")


def check17_partners_not_runtime_agents() -> None:
    binding = read(BINDING)
    if "external AI partners" not in binding:
        bad("check17: binding record does not classify the partners as external AI partners")
    if "must not be presented or modelled as a runtime Agent service" not in binding:
        bad("check17: binding record does not forbid presenting a partner as a runtime agent")
    not_implemented = (
        "agents/backend-agent/ and agents/frontend-agent/ remain classified NOT IMPLEMENTED"
    )
    if not_implemented not in binding:
        bad("check17: backend-agent/frontend-agent are not recorded NOT IMPLEMENTED")


def check18_task_surface_not_dispatching() -> None:
    binding = read(BINDING)
    if "The existing Task API and Task UI remain non-dispatching." not in binding:
        bad("check18: binding record does not keep the Task surface non-dispatching")
    if "must not be used as the Agent execution source of truth" not in binding:
        bad("check18: binding record does not forbid the Task surface as execution source of truth")


def check19_autonomous_generation_forbidden() -> None:
    binding = read(BINDING)
    for needle in (
        "runtime LLM direct patch generation",
        "runtime LLM direct test generation",
        "automatic patch application",
        "autonomous merge",
        "direct push to main",
    ):
        if needle not in binding:
            bad(f"check19: prohibited operation not recorded: {needle}")
    if "requires an independent security review" not in binding:
        bad("check19: the deferred autonomous-generation stage lacks a security-review requirement")


def check20_to_22_stages_unauthorized() -> None:
    addendum = read(ADDENDUM)
    for number, label in (
        ("check20", "STEP66D_ARCH"),
        ("check21", "STEP67POC0"),
        ("check22", "RA2M"),
    ):
        if not re.search(rf"^{label}:\s+NOT STARTED / NOT AUTHORIZED$", addendum, re.MULTILINE):
            bad(f"{number}: {label} is not recorded NOT STARTED / NOT AUTHORIZED")
    if not re.search(r"^POC_IMPLEMENTATION:\s+NOT STARTED / NOT AUTHORIZED$", addendum, re.M):
        bad("check20: POC implementation is not recorded NOT STARTED / NOT AUTHORIZED")
    if not re.search(r"^BE3_RESUME_REPLAY:\s+DISABLED$", addendum, re.MULTILINE):
        bad("check20: BE3 resume/replay is not recorded DISABLED")


def check23_be3_gates_default_false() -> None:
    for var, gate_file in (
        ("BE3_RESUME_API_ENABLED", RESUME_MODEL),
        ("BE3_RESUME_COMMAND_ENABLED", RESUME_MODEL),
        ("BE3_REPLAY_API_ENABLED", REPLAY_MODEL),
        ("BE3_REPLAY_EXECUTION_ENABLED", REPLAY_MODEL),
    ):
        if not gate_file.is_file():
            bad(f"check23: gate file missing: {gate_file.name}")
            continue
        if f'os.environ.get("{var}", "false")' not in gate_file.read_text(encoding="utf-8"):
            bad(f"check23: {var} default is not 'false' in {gate_file.name}")


def check24_no_runtime_source_change() -> None:
    changed = [
        line
        for line in git("diff", "--name-only", STAGE_BASELINE, STAGE_HEAD).splitlines()
        if line.strip()
    ]
    offenders = [path for path in changed if path.startswith(FORBIDDEN_SOURCE_PREFIXES)]
    if offenders:
        bad(f"check24: runtime/source paths changed: {', '.join(sorted(offenders))}")

    # Step 66D-ALIGN1-RM1: exact-set comparison over the FIXED range. Nothing passes on
    # the strength of a directory or filename prefix; an unregistered path fails here.
    _actual = tuple(sorted(changed))
    _unexpected = sorted(set(_actual) - set(EXPECTED_STAGE_PATHS))
    _missing = sorted(set(EXPECTED_STAGE_PATHS) - set(_actual))
    if _unexpected:
        bad(f"check24: unregistered path in this stage's fixed range: {', '.join(_unexpected)}")
    if _missing:
        bad(
            f"check24: registered path missing from this stage's fixed range: {', '.join(_missing)}"
        )

    deletions = [
        line
        for line in git(
            "diff", "--numstat", CANONICAL_MAIN, "HEAD", "--", "source/progress.md"
        ).splitlines()
        if line.strip()
    ]
    for line in deletions:
        parts = line.split("\t")
        if len(parts) >= 2 and parts[1] != "0":
            bad(f"check24: source/progress.md is not append-only ({parts[1]} lines deleted)")


def check25_production_count_zero() -> None:
    for path in (BINDING, ADDENDUM, MANIFEST, PRECEDENCE, EVIDENCE):
        text = read(path)
        if not text:
            continue
        for match in re.findall(r"production_executed_true_count[`:\s]*([0-9]+)", text, re.I):
            if match != "0":
                bad(f"check25: {path.name} records production_executed_true_count {match}")
        for match in re.findall(r"PRODUCTION_EXECUTED_TRUE_COUNT:\s*\n?\s*([0-9]+)", text):
            if match != "0":
                bad(f"check25: {path.name} records PRODUCTION_EXECUTED_TRUE_COUNT {match}")


def check_precedence_record() -> None:
    precedence = read(PRECEDENCE)
    expected = (
        "1. Product Owner accepted binding decisions",
        "2. Current canonical program-state addendum",
        "3. Final reconciliation package",
        "4. Partner acknowledgements and evidence",
        "5. Historical snapshots",
        "6. Planning proposals",
    )
    for line in expected:
        if line not in precedence:
            bad(f"precedence: missing tier line {line!r}")
    for forbidden in ("conversation summary", "design option", "planning proposal"):
        if forbidden not in precedence:
            bad(f"precedence: does not exclude {forbidden!r} from source of truth")


def check_no_merge_claim() -> None:
    for path in (BINDING, ADDENDUM, MANIFEST, PRECEDENCE, EVIDENCE):
        text = read(path).lower()
        if not text:
            continue
        for phrase in (
            "canonical main updated",
            "poc.0 authorized",
            "merged to main",
        ):
            if phrase in text:
                bad(f"no-merge-claim: {path.name} claims {phrase!r} while the PR is unmerged")


# Step 66D-ALIGN1-RM1: the stage SCOPE above is frozen, which is what stops it drifting.
# The runtime denylist must not be frozen with it -- a runtime path added by any later
# commit still has to be caught. This anchor is deliberately HEAD-relative, and it feeds
# the denylist only; it never widens or satisfies the stage scope.
RUNTIME_GUARD_ANCHOR = "c1db4ccbfd88fa775e4761c932835896b9b980ed"


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
    check02_to_06_partner_heads()
    check07_acknowledgements_present()
    check08_final_artifacts_present()
    check09_historical_artifacts_unchanged()
    check10_manifest_covers_all_imports()
    check11_to_13_decisions_binding()
    check14_to_16_selected_options()
    check17_partners_not_runtime_agents()
    check18_task_surface_not_dispatching()
    check19_autonomous_generation_forbidden()
    check20_to_22_stages_unauthorized()
    check23_be3_gates_default_false()
    check24_no_runtime_source_change()
    check25_production_count_zero()
    check_precedence_record()
    check_no_merge_claim()

    check_runtime_guard_current_state()

    if FAILURES:
        for failure in dict.fromkeys(FAILURES):
            print(f"VERIFY FAILED: {failure}", file=sys.stderr)
        return 1
    print(MARKER)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
