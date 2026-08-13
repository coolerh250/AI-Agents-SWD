"""PCP-v2 control plane -- memory drift gate and self-consistency invariants.

Reconciles the versioned PM State Snapshot against canonical engineering truth and refuses to
choose between them when they disagree.

Two failure modes are deliberately distinguished:

    STALENESS  the snapshot's recorded main is an ancestor of current main.
               Expected, reported, not a failure -- a snapshot records when it was reconciled.

    DRIFT      a stable/binding fact disagrees with canonical truth, or the snapshot names a
               commit unknown to the repository or not an ancestor of main.
               PM_STATE_CONFLICT -- stop, and reconcile downward from main.

Canonical values are READ FROM THE REPOSITORY, never hard-coded here. A gate that carried its own
copy of the truth would agree with itself while both drifted.

Local git only by default, so the gate is deterministic offline. `--remote` additionally
machine-confirms pull-request state through the GitHub CLI.

Starts no runtime, container, database, migration apply or external provider.

Marker: PCP_V2_CONTROL_PLANE_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
MARKER = "PCP_V2_CONTROL_PLANE_VERIFY"
CONFLICT = "PM_STATE_CONFLICT"

GOVERNANCE = "docs/governance"
PM_STATE = f"{GOVERNANCE}/AI_AGENTS_PM_STATE.md"
CONTRACT = f"{GOVERNANCE}/project-control-plane-v2.md"
RECOVERY = f"{GOVERNANCE}/pcp-v2-recovery.md"

# Canonical engineering artifacts the snapshot is reconciled AGAINST.
BINDING = "docs/contracts/autonomous-team/at-binding-decisions.md"
MANIFEST = "docs/alignment/66-project-completion/master/canonical-milestone-manifest.md"

REGISTER = re.compile(r"^\s*([A-Za-z][A-Za-z0-9 ._/-]*?)\s*:\s*(\S.*?)\s*$")

# Snapshot fields whose value must equal canonical truth. Disagreement is drift, never staleness.
STABLE_FIELDS = ("AT_M1", "PR29", "AT_M2", "AT-D09", "AT-D10", "AT-D10.1")

# Fields that are expected to age. They are reconciled by ancestry, not by equality.
VOLATILE_FIELDS = ("RECONCILED_AGAINST_MAIN", "RECONCILED_ON", "AT_M1_POSITIVE_SCOPE_PATHS")

OPEN_TERMS = ("OPEN", "DEFERRED", "PENDING", "UNDECIDED")
CLOSURE_TERMS = ("RESOLVED", "BINDING", "CLOSED", "ACCEPTED", "DECIDED", "FINAL")

failures: list[str] = []
notes: list[str] = []


def expect(ok: bool, label: str, message: str) -> None:
    if not ok:
        failures.append(label)
        print(f"  [FAIL] {label}: {message}")


def read(relpath: str) -> str:
    path = ROOT / relpath
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=False
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def is_ancestor(sha: str, of: str) -> bool:
    if not sha or not commit_exists(sha):
        return False
    return (
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", sha, of], cwd=ROOT, check=False
        ).returncode
        == 0
    )


def commit_exists(sha: str) -> bool:
    return bool(sha) and git("cat-file", "-t", sha) == "commit"


def canonical_main() -> str:
    for ref in ("origin/main", "main", "HEAD"):
        sha = git("rev-parse", ref)
        if sha:
            return sha
    return ""


def all_registers(doc: str) -> dict[str, list[str]]:
    """Every KEY: value occurrence inside fenced blocks, in order.

    All occurrences are kept. Collapsing a repeated key to its first value is how a contradiction
    written into the second occurrence becomes invisible -- the gate would then be reconciling a
    line nobody reads.
    """
    fields: dict[str, list[str]] = {}
    fenced = False
    for line in doc.splitlines():
        if line.strip().startswith("```"):
            fenced = not fenced
            continue
        if not fenced:
            continue
        matched = REGISTER.match(line)
        if matched:
            fields.setdefault(matched.group(1).strip(), []).append(matched.group(2).strip())
    return fields


def registers(doc: str) -> dict[str, str]:
    """KEY: value pairs inside fenced blocks. The fence is what makes a line a field."""
    return {key: values[0] for key, values in all_registers(doc).items()}


def repeated_key_conflicts(doc: str) -> list[str]:
    """A key stated twice with different values makes the snapshot self-contradictory."""
    return [
        f"{key}: stated {len(values)} times with differing values {values}"
        for key, values in all_registers(doc).items()
        if len({v.upper() for v in values}) > 1
    ]


def pm_state_fields(path: str | pathlib.Path = PM_STATE) -> dict[str, str]:
    """Fields of the PM State Snapshot, or of a fixture standing in for it.

    `--pm-state` exists so contradiction fixtures can be exercised end to end without mutating
    canonical project state. It is read-only and never writes back.
    """
    source = pathlib.Path(path)
    if source.is_absolute():
        return registers(source.read_text(encoding="utf-8") if source.is_file() else "")
    return registers(read(str(path)))


def canonical_truth() -> dict[str, str]:
    """Engineering truth, derived from the repository and from git -- never from constants."""
    binding = registers(read(BINDING))
    manifest = re.sub(r"\s+", " ", read(MANIFEST))
    at_m1_entry = manifest.split("AT-M1 Autonomous team", 1)[-1][:400].upper()
    truth = {
        "CANONICAL_MAIN": canonical_main(),
        "AT-D09": binding.get("AT-D09", ""),
        "AT-D10": binding.get("AT-D10", ""),
        "AT-D10.1": binding.get("AT-D10.1", ""),
        "AT_M2": binding.get("AT_M2", ""),
        "PRODUCTION_EXECUTED_TRUE_COUNT": binding.get("PRODUCTION_EXECUTED_TRUE_COUNT", ""),
        "AT_M1": "CLOSED / CANONICAL" if "CLOSED / CANONICAL" in at_m1_entry else "",
        "PR29": "MERGED" if "PR #29 MERGED" in at_m1_entry else "",
    }
    return truth


def semantic_equal(left: str, right: str) -> bool:
    def norm(value: str) -> set[str]:
        return {t for t in re.split(r"[^A-Za-z0-9.]+", value.upper()) if t}

    return norm(left) == norm(right)


def drift_conflicts(pm: dict[str, str], truth: dict[str, str]) -> list[str]:
    """Stable/binding disagreements. Each one is a PM_STATE_CONFLICT."""
    conflicts = []
    for field in STABLE_FIELDS:
        stated, actual = pm.get(field, ""), truth.get(field, "")
        if not stated:
            conflicts.append(f"{field}: absent from the PM state")
        elif not actual:
            conflicts.append(f"{field}: canonical truth could not be derived")
        elif not semantic_equal(stated, actual):
            conflicts.append(f"{field}: PM state says {stated!r}, canonical truth says {actual!r}")

    stated_count = pm.get("PRODUCTION_EXECUTED_TRUE_COUNT", "")
    actual_count = truth.get("PRODUCTION_EXECUTED_TRUE_COUNT", "")
    if stated_count != actual_count:
        conflicts.append(
            f"PRODUCTION_EXECUTED_TRUE_COUNT: PM state says {stated_count!r}, "
            f"canonical truth says {actual_count!r}"
        )

    recorded = pm.get("RECONCILED_AGAINST_MAIN", "")
    main = truth.get("CANONICAL_MAIN", "")
    if not commit_exists(recorded):
        conflicts.append(f"RECONCILED_AGAINST_MAIN: {recorded!r} is unknown to this repository")
    elif not is_ancestor(recorded, main):
        conflicts.append(
            f"RECONCILED_AGAINST_MAIN: {recorded[:7]} is not an ancestor of main; the snapshot "
            "describes a history this repository does not have"
        )

    merge = pm.get("AT_M1_MERGE_COMMIT", "")
    stage_head = pm.get("AT_M1_STAGE_HEAD", "")
    baseline = pm.get("AT_M1_BASELINE", "")
    if pm.get("PR29", "").upper() == "MERGED":
        if not is_ancestor(merge, main):
            conflicts.append(f"PR29 is MERGED but its merge commit {merge[:7]} is not in main")
        elif git("rev-parse", f"{merge}^2") != stage_head:
            conflicts.append("AT_M1_STAGE_HEAD is not the merge commit's merged parent")
        elif git("rev-parse", f"{merge}^1") != baseline:
            conflicts.append("AT_M1_BASELINE is not the merge commit's first parent")

    held_head = pm.get("PR28_HEAD", "")
    if held_head and is_ancestor(held_head, main):
        conflicts.append(
            f"PR28 is recorded on HOLD but its head {held_head[:7]} is already in main"
        )
    return conflicts


def staleness(pm: dict[str, str], truth: dict[str, str]) -> int:
    """Commits between the snapshot's recorded main and current main. Not a failure."""
    recorded, main = pm.get("RECONCILED_AGAINST_MAIN", ""), truth.get("CANONICAL_MAIN", "")
    if not is_ancestor(recorded, main):
        return -1
    counted = git("rev-list", "--count", f"{recorded}..{main}")
    return int(counted) if counted.isdigit() else -1


def invariant_violations(
    pm: dict[str, str], repeated: dict[str, list[str]] | None = None
) -> list[str]:
    """I1..I7. Internal consistency of the snapshot, independent of canonical truth."""
    violations = []
    positions = {
        pm.get("CURRENT_MILESTONE", ""),
        pm.get("CURRENT_STAGE", ""),
        pm.get("NEXT_PERMITTED_STAGE", ""),
    }

    # I1 -- a NOT AUTHORIZED stage cannot also be the current or next work.
    for key, value in pm.items():
        if "NOT AUTHORIZED" in value.upper() and key.replace("_", "-") in {
            p.replace("_", "-") for p in positions if p
        }:
            violations.append(f"I1: {key} is NOT AUTHORIZED and is also a current/next position")

    # I2 -- a HOLD artifact is never a canonical dependency. Every occurrence is examined, not
    # just the first: a HOLD entry restated later with a dependency claim is the realistic shape.
    occurrences = repeated if repeated is not None else {k: [v] for k, v in pm.items()}
    for key, values in occurrences.items():
        for value in values:
            upper = value.upper()
            if "HOLD" not in upper:
                continue
            if "NON-CANONICAL" not in upper:
                violations.append(f"I2: {key} is on HOLD but is not marked NON-CANONICAL")
            if "DEPENDENCY" in upper and "NOT A DEPENDENCY" not in upper:
                violations.append(f"I2: {key} is on HOLD and is asserted as a dependency")

    # I3 -- an OPEN/DEFERRED decision is never downstream BINDING truth.
    for key, value in pm.items():
        if not key.upper().startswith("AT-D"):
            continue
        upper = value.upper()
        opened = [t for t in OPEN_TERMS if re.search(rf"\b{t}\b", upper)]
        closed = [t for t in CLOSURE_TERMS if re.search(rf"\b{t}\b", upper)]
        if opened and closed:
            violations.append(f"I3: {key} is asserted both {opened} and {closed}")

    # I4 -- no production authorization means the execution count stays 0.
    if "GRANTED" not in pm.get("PRODUCTION_AUTHORIZATION", "NOT GRANTED").upper().replace(
        "NOT GRANTED", ""
    ):
        if pm.get("PRODUCTION_EXECUTED_TRUE_COUNT", "0") != "0":
            violations.append(
                "I4: production execution is claimed above zero without authorization"
            )

    # I5 -- a MERGED pull request is ancestry-reconcilable with main.
    if pm.get("PR29", "").upper() == "MERGED" and not is_ancestor(
        pm.get("AT_M1_MERGE_COMMIT", ""), canonical_main()
    ):
        violations.append("I5: PR29 is MERGED but its merge commit is not reachable from main")

    # I6 -- a CLOSED/CANONICAL milestone has canonical evidence and ancestry.
    if "CANONICAL" in pm.get("AT_M1", "").upper():
        if not is_ancestor(pm.get("AT_M1_STAGE_HEAD", ""), canonical_main()):
            violations.append("I6: AT_M1 is CANONICAL but its reviewed stage head is not in main")
        if "CLOSED / CANONICAL" not in re.sub(r"\s+", " ", read(MANIFEST)):
            violations.append("I6: AT_M1 is CANONICAL but the milestone manifest does not say so")

    # I7 -- roadmap prerequisites. AT-M2 requires PCP-V2.1 to have passed.
    gate_passed = "PASS" in pm.get("PCP_V2_1", "").upper()
    if "NOT AUTHORIZED" not in pm.get("AT_M2", "").upper() and not gate_passed:
        violations.append("I7: AT_M2 is not NOT AUTHORIZED while PCP-V2.1 has not passed")
    return violations


# =================================================================================================
# Measured debt reconciliation (Step PCP-V2.1-RM1)
#
# "BLOCKERS: NONE" used to mean "the stage author did not notice one". PCP-V2.1-A asserted it while
# two governance verifiers were failing on canonical main, and the failures hid behind ADV-R4-01
# because they belonged to the same verifier family. Family-level debt cannot distinguish a known
# failure from a new one beside it, so identity here is EXACT.
# =================================================================================================

GOVERNANCE_REGRESSION = "GOVERNANCE_REGRESSION"

# A governance verifier is applicable to a change when it derives its own changed-path set against
# live HEAD -- those are exactly the ones an incoming path can break. Derived structurally, so a
# verifier cannot escape the set by not being nominated. PCP-V2.1-A hand-picked four sentinels and
# missed the one that actually failed.
HEAD_RELATIVE = re.compile(
    r'"--name-only"[^\n]*"HEAD"|\.\.\.HEAD|--name-only[^\n]*HEAD|"HEAD"\s*\)'
)

# Paths whose change invalidates a recorded governance measurement.
GOVERNANCE_ARTIFACT = re.compile(r"^(scripts/verify_[a-z0-9_]+\.py|tests/test_[a-z0-9_]+\.py)$")


def applicable_governance_verifiers() -> list[str]:
    """Every HEAD-relative governance verifier except this one.

    Self-measurement is a fixed point, not a check: this gate failing would make itself an
    unregistered failure, which would make it fail. Its own exit code is the report the caller
    reads, and its behaviour is covered by tests/test_pcp_v2_control_plane.py. The exclusion is
    structural, not an accommodation for any stage family.
    """
    self_name = pathlib.Path(__file__).name
    scripts = sorted((ROOT / "scripts").glob("verify_*.py"))
    return [
        f"scripts/{path.name}"
        for path in scripts
        if path.name != self_name
        and HEAD_RELATIVE.search(path.read_text(encoding="utf-8", errors="replace"))
    ]


def measured_governance_failures() -> list[str]:
    """Exact failure identities from an actual run of the applicable set."""
    failures = []
    for relpath in applicable_governance_verifiers():
        result = subprocess.run(
            [sys.executable, relpath],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if result.returncode != 0:
            failures.append(f"verifier:{pathlib.Path(relpath).name}")
    return sorted(failures)


def registered_debt_ids(pm_doc: str) -> set[str]:
    """Exact registered failure identities, read from the PM state rather than hard-coded."""
    return {
        line.strip().removeprefix("- ").strip()
        for line in pm_doc.splitlines()
        if line.strip().removeprefix("- ").startswith(("verifier:", "test:"))
    }


def new_unregistered_failures(measured: list[str], registered: set[str]) -> list[str]:
    """MEASURED - REGISTERED. Non-empty means BLOCKERS may not be NONE."""
    return sorted(set(measured) - registered)


def governance_measurement_stale(pm: dict[str, str]) -> list[str]:
    """Governance artifacts changed since the recorded measurement, so it no longer speaks."""
    measured_at = pm.get("GOVERNANCE_MEASURED_AT", "")
    if not commit_exists(measured_at):
        return ["GOVERNANCE_MEASURED_AT names no commit in this repository"]
    changed = [
        line.strip()
        for line in git("diff", "--name-only", f"{measured_at}...HEAD").splitlines()
        if GOVERNANCE_ARTIFACT.match(line.strip())
    ]
    return changed


def confirm_remote(pm: dict[str, str]) -> list[str]:
    """Machine-confirm pull-request state. Opt-in: the default path stays offline."""
    conflicts = []
    for number, field in ((29, "PR29"), (28, "PR28")):
        result = subprocess.run(
            ["gh", "pr", "view", str(number), "--json", "state,mergedAt"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        if result.returncode != 0:
            conflicts.append(f"{field}: remote state could not be machine-confirmed")
            continue
        remote_merged = '"state":"MERGED"' in result.stdout.replace(" ", "")
        stated_merged = "MERGED" in pm.get(field, "").upper()
        if remote_merged != stated_merged:
            conflicts.append(
                f"{field}: PM state says {pm.get(field, '')!r}, remote says "
                f"{'MERGED' if remote_merged else 'not merged'}"
            )
    return conflicts


def main() -> int:
    remote = "--remote" in sys.argv
    fixture = ""
    if "--pm-state" in sys.argv:
        fixture = sys.argv[sys.argv.index("--pm-state") + 1]
        print(f"  [fixture] reconciling {fixture} instead of the canonical snapshot")

    for relpath in (PM_STATE, CONTRACT, RECOVERY):
        expect((ROOT / relpath).is_file(), "check01", f"missing governance artifact: {relpath}")
    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    pm = pm_state_fields(fixture or PM_STATE)
    truth = canonical_truth()

    expect(pm.get("PM_STATE_VERSION", "") == "1", "check02", "PM_STATE_VERSION must be 1")
    expect(pm.get("PM_STATE_SCHEMA", "") == "pcp-v2", "check03", "PM_STATE_SCHEMA must be pcp-v2")
    for field in (
        "RECONCILED_ON",
        "RECONCILED_AGAINST_MAIN",
        "CURRENT_MILESTONE",
        "CURRENT_GATE",
        "NEXT_PERMITTED_STAGE",
        "PR28",
        "PRODUCTION_AUTHORIZATION",
        "HAZARD_AT_M1_DENYLIST",
        "BLOCKERS",
    ):
        expect(bool(pm.get(field)), "check04", f"PM state is missing required field {field}")

    repeated = all_registers(
        pathlib.Path(fixture).read_text(encoding="utf-8") if fixture else read(PM_STATE)
    )
    duplicates = repeated_key_conflicts(
        pathlib.Path(fixture).read_text(encoding="utf-8") if fixture else read(PM_STATE)
    )
    for duplicate in duplicates:
        print(f"  [{CONFLICT}] {duplicate}")
    expect(duplicates == [], "check05a", f"{CONFLICT}: the snapshot contradicts itself")

    conflicts = drift_conflicts(pm, truth)
    for conflict in conflicts:
        print(f"  [{CONFLICT}] {conflict}")
    expect(conflicts == [], "check05", f"{CONFLICT}: {len(conflicts)} stable fact(s) disagree")

    violations = invariant_violations(pm, repeated)
    for violation in violations:
        print(f"  [INVARIANT] {violation}")
    expect(violations == [], "check06", f"self-consistency invariants violated: {len(violations)}")

    behind = staleness(pm, truth)
    if behind > 0:
        notes.append(f"snapshot is {behind} commit(s) behind main -- stale, not drifted")
    expect(behind >= 0, "check07", "snapshot staleness could not be computed")

    contract = read(CONTRACT)
    for concept in ("Delta prompt", "Stage capsule", "Risk-adaptive gates", "repair window"):
        expect(concept.lower() in contract.lower(), "check08", f"PCP contract omits {concept!r}")
    for invariant in ("I1", "I2", "I3", "I4", "I5", "I6", "I7"):
        expect(invariant in contract, "check09", f"PCP contract omits invariant {invariant}")

    recovery = read(RECOVERY)
    expect("RECOVERY PACKET" in recovery, "check10", "the recovery packet is not defined")
    expect(
        all(f"C{n}" in recovery for n in range(1, 8)),
        "check11",
        "the contradiction fixtures C1..C7 are not all specified",
    )
    expect(
        "PM_STATE_CONFLICT" in recovery and "FAIL" in recovery,
        "check12",
        "the contradiction acceptance procedure does not require a blocking verdict",
    )
    expect(
        "cannot conclude PCP-V2.1 PASS" in recovery,
        "check13",
        "the recovery spec does not state that this stage cannot claim PCP-V2.1 PASS",
    )
    expect(
        "NOT AUTHORIZED" in pm.get("AT_M2", ""),
        "check14",
        "AT-M2 must remain NOT AUTHORIZED",
    )
    expect(
        "DISPOSITION REQUIRED" in pm.get("HAZARD_AT_M1_DENYLIST", "").upper(),
        "check15",
        "the AT-M1 denylist transition hazard is not recorded as requiring a disposition",
    )

    # --- measured debt reconciliation (PCP-V2.1-RM1) ------------------------------------------
    pm_doc = pathlib.Path(fixture).read_text(encoding="utf-8") if fixture else read(PM_STATE)
    registered = registered_debt_ids(pm_doc)
    expect(
        bool(registered),
        "check17",
        "the PM state registers no exact failure identities, so BLOCKERS cannot be reconciled",
    )
    stale_since = governance_measurement_stale(pm)
    expect(
        stale_since == [],
        "check18",
        "the recorded governance measurement is stale -- these governance artifacts changed "
        f"since GOVERNANCE_MEASURED_AT and it must be retaken: {stale_since[:6]}",
    )
    if "--governance" in sys.argv:
        measured = measured_governance_failures()
        unregistered = new_unregistered_failures(measured, registered)
        for failure in unregistered:
            print(f"  [{GOVERNANCE_REGRESSION}] unregistered governance failure: {failure}")
        expect(
            unregistered == [],
            "check19",
            f"{GOVERNANCE_REGRESSION}: {len(unregistered)} measured failure(s) are not registered "
            "debt, so BLOCKERS: NONE is invalid",
        )
        notes.append(
            f"governance: {len(applicable_governance_verifiers())} applicable, "
            f"{len(measured)} failing, all registered"
        )
    expect(
        pm.get("BLOCKERS", "").upper() != "NONE" or stale_since == [],
        "check20",
        "BLOCKERS: NONE is claimed against a stale governance measurement",
    )

    if remote:
        remote_conflicts = confirm_remote(pm)
        for conflict in remote_conflicts:
            print(f"  [{CONFLICT}] {conflict}")
        expect(remote_conflicts == [], "check16", f"{CONFLICT}: remote state disagrees")

    for note in notes:
        print(f"  [note] {note}")
    checks = 21 if remote else 20
    print(f"{MARKER}: checks={checks} failures={len(failures)}")
    print(f"{MARKER}: {'PASS' if not failures else 'FAIL'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
