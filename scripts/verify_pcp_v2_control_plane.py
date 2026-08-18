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

import ast
import hashlib
import os
import pathlib
import re
import subprocess
import sys
import tempfile

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

ACTIVE_DEBT_HEADING = "### Active registered debt"
HISTORICAL_DEBT_HEADING = "### Historical debt"

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

# The OUTER governance domain: the repository's own verifier/test naming convention. Structural and
# finite. Runtime, application, migration and infrastructure paths are outside it by construction.
GOVERNANCE_ARTIFACT = re.compile(r"^(scripts/verify_[a-z0-9_]+\.py|tests/test_[a-z0-9_]+\.py)$")

# APPLICABILITY -- fail closed on repository-state dependency (Step PCP-V2.1-RM3, gap A1).
#
# RM2 asked "does this module invoke git?", detected by finding the constant "git" in its AST. That
# is a classification by COMMAND FORM, and command forms are unbounded: a shell string, a binary
# name built from pieces, os.system, or a wrapper all query the same state and all escaped. It was
# the same enumeration defect as B-1, one axis over.
#
# The question is no longer asked. A governance module reads repository files, and repository files
# advance, so EVERY module in the outer governance domain depends on repository state. Applicability
# is therefore the default and needs no proof; only EXCLUSION needs proof.
#
# Note the polarity of the one enumeration below. It sits on the EXCLUSION side: a spelling this
# list does not recognise leaves the module IN the measured set. An unseen shape can only ever cause
# over-inclusion, never the under-sampling that produced A1 and B-1.

# Clients whose presence proves the module reaches outside the repository.
EXTERNAL_CLIENTS = frozenset(
    {"urllib", "requests", "http", "socket", "psycopg", "psycopg2", "redis", "boto3", "httpx"}
)
# Tools that require an environment this measurement cannot assume.
#
# `gh` was missing until RM4. It needs GitHub credentials, which live in the operator's account
# rather than in the repository, so a verifier calling it answered from whichever machine ran the
# measurement -- the DEF-PCPE-01 defect reached through a subprocess instead of a file. The tracer
# cannot see inside another process, so this dependency has to be recognised statically.
EXTERNAL_TOOLS = frozenset(
    {"docker", "docker-compose", "gh", "helm", "kubectl", "psql", "minikube", "kind", "terraform"}
)


def environment_dependent(source: str) -> tuple[bool, str]:
    """(excluded, reason). Only a PROVEN external dependency excludes a module.

    A tool name is recognised only in EXECUTABLE position. `verify_step66c4_be1_merge.py` mentions
    "helm" as a forbidden path prefix; reading that as an invocation dropped a registered debt
    identity out of the domain, which is exactly the false exclusion this rule must not make.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False, ""
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in EXTERNAL_CLIENTS:
                    return True, f"imports the external client {alias.name}"
        if isinstance(node, ast.ImportFrom) and node.module:
            if node.module.split(".")[0] in EXTERNAL_CLIENTS:
                return True, f"imports from the external client {node.module}"
        if isinstance(node, (ast.List, ast.Tuple)) and node.elts:
            head = node.elts[0]
            if isinstance(head, ast.Constant) and head.value in EXTERNAL_TOOLS:
                return True, f"invokes the external tool {head.value}"
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            command = node.value.strip()
            executable = command.split(" ")[0]
            if " " in command and executable in EXTERNAL_TOOLS:
                return True, f"shell-invokes the external tool {executable}"
    return False, ""


def repository_state_dependent(source: str) -> tuple[bool, str]:
    """(applicable, reason). Fail closed: applicable unless external dependency is PROVEN.

    No command form, executable name, subprocess API shape, wrapper name or reference spelling is
    consulted. There is nothing here for an unseen spelling to slip past.
    """
    excluded, reason = environment_dependent(source)
    if excluded:
        return False, reason
    return True, "governance module reading repository state"


def governance_modules(directory: str, prefix: str, root: pathlib.Path | None = None) -> list[str]:
    """The OUTER governance domain: the repository's verifier/test naming convention."""
    base = root or ROOT
    return sorted(
        f"{directory}/{path.name}"
        for path in (base / directory).glob(f"{prefix}*.py")
        if GOVERNANCE_ARTIFACT.match(f"{directory}/{path.name}")
    )


def applicable_governance_verifiers() -> list[str]:
    """Every governance verifier except this one and the provably environment-dependent.

    Self-measurement is a fixed point, not a check: this gate failing would make itself an
    unregistered failure, which would make it fail. Its own exit code is the report, and the
    external observer in the focused tests keys on that. Keyed off __file__, not a name list.
    """
    self_relpath = f"scripts/{pathlib.Path(__file__).name}"
    applicable = []
    for relpath in governance_modules("scripts", "verify_"):
        if relpath == self_relpath:
            continue
        live, _ = repository_state_dependent(read(relpath))
        if live:
            applicable.append(relpath)
    return applicable


def excluded_environment_verifiers() -> list[tuple[str, str]]:
    """Reported, never silent: an exclusion nobody can see is indistinguishable from a gap."""
    excluded = []
    for relpath in governance_modules("scripts", "verify_"):
        dependent, reason = environment_dependent(read(relpath))
        if dependent:
            excluded.append((relpath, reason))
    return excluded


def applicable_governance_tests() -> list[str]:
    """Governance tests that can fail because of current repository state.

    Derived, never hand-picked: a test mirroring a measured verifier by the repository's own stem
    convention. Unrelated runtime and application tests stay outside the governance domain.
    """
    mirrored = {
        pathlib.Path(relpath).stem[len("verify_") :]
        for relpath in applicable_governance_verifiers()
    }
    applicable = []
    for relpath in governance_modules("tests", "test_"):
        stem = pathlib.Path(relpath).stem[len("test_") :]
        if stem not in mirrored:
            continue
        live, _ = repository_state_dependent(read(relpath))
        if live:
            applicable.append(relpath)
    return applicable


# ===================== CANONICAL MEASUREMENT AND ADMISSIBILITY (Step PCP-V2.1-RM4) ===============
#
# DEF-PCPE-01: the measurement ran with cwd=ROOT, the operator's own working tree. Three verifiers
# read a gitignored `.runtime/` directory, so they passed here and failed in a clean checkout of the
# SAME commit, with a byte-identical authority digest. "BLOCKERS: NONE" described the workstation.
#
# Two defects, deliberately fixed separately:
#
#   ISOLATION      canonical measurement now runs in a disposable pristine worktree under a
#                  sanitized environment. Developer-tree leftovers cannot reach it at all.
#
#   ADMISSIBILITY  a check whose truth needs a non-canonical input must not become repository debt
#                  just because that input is absent from a clean checkout. "This machine had no
#                  runtime evidence" is not a known governance failure.
#
# Admissibility is decided by OBSERVING what a module actually reads, not by inspecting how it is
# written. A path can be spelled an unbounded number of ways -- constant, f-string, loop variable,
# helper return value -- and a static classifier must anticipate every one. That is the enumeration
# defect this project has now hit ten times. What a process opens is decidable regardless of
# spelling, so a future verifier reading a newly ignored directory is caught with nobody editing
# this file.

REPO_DETERMINISTIC = "REPO_DETERMINISTIC"
ENVIRONMENT_DEPENDENT = "ENVIRONMENT_DEPENDENT"
UNKNOWN = "UNKNOWN"

MEASUREMENT_POLICY_ID = "pcp-v2-canonical-isolated"
MEASUREMENT_POLICY_VERSION = "2"
ADMISSIBILITY_CONTRACT_VERSION = "2"
MEASUREMENT_ISOLATION_MODE = "standalone-clone+declared-refs+sanitized-environment"

# BLK-PCPF-01: RM4 measured in a linked worktree, whose `git rev-parse --git-common-dir` resolves
# to the operator's repository. The measurement therefore inherited 48 local branches, the
# operator's origin URL, their git identity and live network reachability -- and six verifiers
# returned different results at the SAME canonical commit when that namespace differed.
#
# The measurement repository is now built, not borrowed: a bare fixture is populated with exactly
# the canonical commit under a policy-declared ref namespace, and cloned into the scaffold. Nothing
# about the operator's repository is reachable from it.
GIT_ISOLATION_POLICY = "standalone-clone-from-policy-declared-bare-fixture"

# The only refs the measurement repository is allowed to contain. Operator-local branches are not
# copied, so creating or deleting one cannot move canonical truth.
DECLARED_REFS = ("refs/heads/main",)

# Remote authority is a deterministic local fixture, never the operator's origin and never the
# network. `git ls-remote origin` answers from objects this policy materialised, so an account,
# a credential helper or an unreachable network cannot change canonical debt.
REMOTE_AUTHORITY_POLICY = "declared-local-fixture-only; no network, no operator remote"

# BLK-PCPF-02: pytest's session-end cache write landed in .pytest_cache, which is gitignored, and
# the tracer attributed it to whichever node ran last -- so an identical new failing test blocked
# at first and middle position and was silently exempted at last position. Harness state now lives
# outside the measurement repository entirely; there is no filename filter to keep growing.
HARNESS_ARTIFACT_POLICY = "harness state outside the measured repository; pytest cache disabled"
PROBE_HEADER = "probe\tinput-authority-tracer/1"

# The environment the measurement policy PROVIDES. Reading anything outside it is reading ambient
# process state, whose value this measurement cannot reproduce.
ENVIRONMENT_ALLOWLIST = frozenset(
    {
        "PATH",
        "PATHEXT",
        "SYSTEMROOT",
        "SYSTEMDRIVE",
        "WINDIR",
        "COMSPEC",
        "TEMP",
        "TMP",
        "TMPDIR",
        "HOME",
        "USERPROFILE",
        "PYTHONPATH",
        "PYTHONHASHSEED",
        "PYTHONDONTWRITEBYTECODE",
        "PYTHONIOENCODING",
        "PYTHONUTF8",
        "PYTHONPYCACHEPREFIX",
        "PCP_MEASUREMENT_TRACE",
        "PCP_MEASUREMENT_ROOT",
        "PCP_GIT_TRACE_DIR",
        "GIT_CONFIG_NOSYSTEM",
        "GIT_CONFIG_GLOBAL",
        "GIT_TERMINAL_PROMPT",
        "LANG",
        "LC_ALL",
    }
)

# The subset the policy PASSES THROUGH from the operator's environment rather than setting itself.
# Needed to locate the interpreter and git at all.
AMBIENT_ENVIRONMENT = frozenset(
    {"PATH", "PATHEXT", "SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "COMSPEC"}
)

# Why admissibility has no environment axis.
#
# Sanitising the environment does not merely classify environment dependence, it ELIMINATES it: the
# environment is fixed by policy, so two runs under the same policy see the same environment. Every
# variable is either granted a value the policy derives, passed through from the machine, or absent
# -- and absence is as deterministic as any value.
#
# Only the six pass-through names above carry a machine-specific value, and an attempt to treat
# reading one as evidence of dependence classified THREE ALREADY-REGISTERED debt identities as
# environment-dependent. Python's own process machinery reads COMSPEC, PATH and PATHEXT on every
# subprocess call, and separating the interpreter's reads from the module's by call stack proved
# unreliable. Shipping it would have silently removed real debt from measurement, which is the
# exact under-sampling this stage exists to stop -- so the axis is not shipped.
#
# The case that actually matters is not lost. A verifier whose result depends on PATH's value is
# probing the filesystem for an executable, and those reads land outside the repository, where the
# path rule below catches them.
ENVIRONMENT_NOTE = (
    "environment is fixed by measurement policy, so it is controlled rather than classified"
)


# The tracer is written into the disposable scaffold at measurement time rather than kept as
# repository files. It is part of the measurement POLICY, not a governance artifact, and
# shipping it as loose files under scripts/ put paths into the tree that the ALIGN1 scope guard
# correctly rejects. Holding the source here also guarantees the tracer and the policy digest
# can never describe different code.
TRACER_SOURCE = '''"""Input-authority tracer for the canonical governance measurement (Step PCP-V2.1-RM4).

Loaded by the measurement harness through PYTHONPATH, so it runs before the module under
measurement. It records every filesystem path and environment variable the module actually
touches, and whether the module's OWN code made the call.

Observation, not inspection. DEF-PCPE-01 escaped a static classifier because a path can be spelled
an unbounded number of ways -- a constant, an f-string, a loop variable, a helper's return value.
What a process opens is decidable regardless of spelling, so a verifier reading a non-canonical
input is caught without anyone having to anticipate the mechanism.

Attribution matters because the interpreter is noisy. Python reads COMSPEC, PATH and PATHEXT on
every subprocess call, APPDATA and USERPROFILE at startup, and imported libraries probe machine
paths of their own. Counting those as dependencies of the governance module made almost every
verifier look ambient and silently excluded three already-registered debt identities.

Emitted records:

    probe   header proving the tracer loaded at all
    path    a filesystem path touched by anyone in the process
    mpath   a filesystem path touched by the module's own frame
    env     an environment variable read by the module's own frame
    node    the pytest identity subsequent records belong to (written by the pytest plugin)
"""

import io
import os
import sys

_TRACE = os.environ.get("PCP_MEASUREMENT_TRACE")

PROBE_HEADER = "probe\\tinput-authority-tracer/1"

if _TRACE:
    _sink = open(_TRACE, "a", encoding="utf-8", errors="replace")
    # Proves the module's inputs were actually observed. A trace without this line means the
    # tracer never loaded, and an unobserved module is UNKNOWN, never assumed deterministic.
    _sink.write(PROBE_HEADER + "\\n")
    _sink.flush()

    _MEASURED_ROOT = os.path.normcase(os.path.abspath(os.environ.get("PCP_MEASUREMENT_ROOT", "")))

    def _from_measured_module(depth: int) -> bool:
        """True when the frame `depth` levels above the tracer wrapper is the module's own code."""
        if not _MEASURED_ROOT:
            return True
        try:
            filename = sys._getframe(depth + 1).f_code.co_filename
        except (ValueError, AttributeError):
            return False
        return os.path.normcase(os.path.abspath(filename)).startswith(_MEASURED_ROOT)

    def _emit(kind: str, value: object) -> None:
        try:
            value = os.fspath(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return
        if isinstance(value, bytes):
            value = value.decode("utf-8", "replace")
        _sink.write(f"{kind}\\t{value}\\n")
        _sink.flush()

    def _emit_path(value: object, depth: int) -> None:
        # Repository-relative authority is judged without attribution, so that a non-canonical
        # dependency reached through any depth of helper is still caught. Attribution only decides
        # whether an OUT-OF-repository read belongs to the module or to machinery beneath it.
        _emit("path", value)
        if _from_measured_module(depth + 1):
            _emit("mpath", value)

    def _trace_path(module: object, name: str) -> None:
        original = getattr(module, name)

        def traced(path, *args, **kwargs):  # type: ignore[no-untyped-def]
            _emit_path(path, 1)
            return original(path, *args, **kwargs)

        setattr(module, name, traced)

    for _name in ("stat", "lstat", "listdir", "scandir", "open", "readlink"):
        _trace_path(os, _name)
    _trace_path(os.path, "exists")
    _trace_path(os.path, "isfile")
    _trace_path(os.path, "isdir")

    _real_open = io.open

    def _traced_open(file, *args, **kwargs):  # type: ignore[no-untyped-def]
        _emit_path(file, 1)
        return _real_open(file, *args, **kwargs)

    io.open = _traced_open  # type: ignore[assignment]
    import builtins

    builtins.open = _traced_open  # type: ignore[assignment]

    def _emit_env(key: object, depth: int) -> None:
        if _from_measured_module(depth + 1):
            _emit("env", key)

    _real_getenv = os.getenv

    def _traced_getenv(key, default=None):  # type: ignore[no-untyped-def]
        _emit_env(key, 1)
        return _real_getenv(key, default)

    os.getenv = _traced_getenv  # type: ignore[assignment]

    _environ_class = type(os.environ)
    _real_getitem = _environ_class.__getitem__
    _real_get = _environ_class.get
    _real_contains = _environ_class.__contains__

    def _traced_getitem(self, key):  # type: ignore[no-untyped-def]
        _emit_env(key, 1)
        return _real_getitem(self, key)

    def _traced_get(self, key, default=None):  # type: ignore[no-untyped-def]
        _emit_env(key, 1)
        return _real_get(self, key, default)

    def _traced_contains(self, key):  # type: ignore[no-untyped-def]
        _emit_env(key, 1)
        return _real_contains(self, key)

    _environ_class.__getitem__ = _traced_getitem  # type: ignore[assignment]
    _environ_class.get = _traced_get  # type: ignore[assignment]
    _environ_class.__contains__ = _traced_contains  # type: ignore[assignment]
'''

PYTEST_PLUGIN_SOURCE = '''"""Attributes traced inputs to the exact pytest node that touched them (Step PCP-V2.1-RM4).

The verifier domain gets one process per identity, so its trace needs no attribution. The test
domain runs in a single pytest process, so without a marker the tracer could only say "something in
this batch read a non-canonical input" -- which is not an exact identity, and exact identity is the
property the debt register depends on.
"""

import os


_counter = [0]


def _mark(nodeid: str) -> None:
    trace = os.environ.get("PCP_MEASUREMENT_TRACE")
    if not trace:
        return
    with open(trace, "a", encoding="utf-8", errors="replace") as sink:
        sink.write(f"node\\t{nodeid}\\n")
        # Rotate git's own argv log per identity. A single session-wide log made one
        # module's dependency on a foreign commit look like every node's dependency,
        # which would have exempted every failing test in the batch.
        directory = os.environ.get("PCP_GIT_TRACE_DIR")
        if directory:
            _counter[0] += 1
            target = os.path.join(directory, f"node-{_counter[0]:05d}.git")
            os.environ["GIT_TRACE"] = target
            sink.write(f"gitlog\\t{nodeid}\\t{target}\\n")


def pytest_collectstart(collector):  # type: ignore[no-untyped-def]
    # Import-time reads happen during collection, before any node starts. Attributing them to the
    # file lets them reach every identity in it instead of escaping attribution entirely.
    _mark(getattr(collector, "nodeid", "") or "")


def pytest_runtest_logstart(nodeid, location):  # type: ignore[no-untyped-def]
    _mark(nodeid)
'''


def _write_probe(scaffold: pathlib.Path) -> pathlib.Path:
    probe = scaffold / "probe"
    probe.mkdir(exist_ok=True)
    (probe / "sitecustomize.py").write_text(TRACER_SOURCE, encoding="utf-8")
    (probe / "pcp_trace_plugin.py").write_text(PYTEST_PLUGIN_SOURCE, encoding="utf-8")
    return probe


def measurement_policy() -> dict[str, str]:
    """What a recorded measurement must state so another session can reproduce its execution."""
    return {
        "MEASUREMENT_POLICY_ID": MEASUREMENT_POLICY_ID,
        "MEASUREMENT_POLICY_VERSION": MEASUREMENT_POLICY_VERSION,
        "ADMISSIBILITY_CONTRACT_VERSION": ADMISSIBILITY_CONTRACT_VERSION,
        "MEASUREMENT_ISOLATION_MODE": MEASUREMENT_ISOLATION_MODE,
        "GIT_ISOLATION_POLICY": GIT_ISOLATION_POLICY,
        "REMOTE_AUTHORITY_POLICY": REMOTE_AUTHORITY_POLICY,
        "HARNESS_ARTIFACT_POLICY": HARNESS_ARTIFACT_POLICY,
        "DECLARED_REFS": " ".join(DECLARED_REFS),
    }


def measurement_policy_digest() -> str:
    """Distinguishes 'same commit under another ambient environment' from 'same policy'.

    Covers the policy fields, the environment the policy grants, and the tracer the admissibility
    contract is implemented by -- so changing how measurement decides anything invalidates the
    recorded result.
    """
    hasher = hashlib.sha256()
    for key, value in sorted(measurement_policy().items()):
        hasher.update(f"{key}={value}\n".encode())
    for name in sorted(ENVIRONMENT_ALLOWLIST):
        hasher.update(f"env:{name}\n".encode())
    for name, source in (("tracer", TRACER_SOURCE), ("plugin", PYTEST_PLUGIN_SOURCE)):
        hasher.update(name.encode("utf-8"))
        hasher.update(source.encode("utf-8"))
    return hasher.hexdigest()


def domains_at(root: pathlib.Path) -> tuple[list[str], list[str]]:
    """(verifiers, tests) applicable at a given checkout, derived from that checkout's own files."""
    self_relpath = f"scripts/{pathlib.Path(__file__).name}"
    verifiers = []
    for relpath in governance_modules("scripts", "verify_", root):
        if relpath == self_relpath:
            continue
        source = (root / relpath).read_text(encoding="utf-8", errors="replace")
        if repository_state_dependent(source)[0]:
            verifiers.append(relpath)
    mirrored = {pathlib.Path(relpath).stem[len("verify_") :] for relpath in verifiers}
    tests = []
    for relpath in governance_modules("tests", "test_", root):
        if pathlib.Path(relpath).stem[len("test_") :] not in mirrored:
            continue
        source = (root / relpath).read_text(encoding="utf-8", errors="replace")
        if repository_state_dependent(source)[0]:
            tests.append(relpath)
    return verifiers, tests


def non_canonical_paths(root: pathlib.Path, candidates: set[str]) -> set[str]:
    """Which repo-relative paths the REPOSITORY itself declares non-canonical.

    git answers, not a list maintained here. A tracked file is never ignored, so this is exactly
    "content a clean checkout of this commit cannot contain".
    """
    if not candidates:
        return set()
    # NUL-separated in both directions. Newline separation is silently corrupted on Windows, where
    # text-mode pipes rewrite \n as \r\n and git then quotes every path back with a trailing CR --
    # so nothing matched and three non-canonical dependencies looked deterministic.
    result = subprocess.run(
        ["git", "check-ignore", "--stdin", "-z"],
        cwd=root,
        input="\0".join(sorted(candidates)),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return {entry.replace("\\", "/") for entry in result.stdout.split("\0") if entry.strip()}


# Objects a measured module asked git about. GIT_TRACE is git's own native argv log, so this
# observes child git processes without a shell shim and without any quoting hazard -- closing the
# RM4 gap where a dependency carried inside a child git process was invisible.
GIT_TRACE_INVOCATION = re.compile(r"trace: built-in: git (.+)$")
REVISION_TOKEN = re.compile(r"^(?:[0-9a-f]{7,40}|refs/[\w./-]+|origin/[\w./-]+)$")


def requested_revisions(git_trace: str) -> set[str]:
    """Revision-shaped arguments the module handed to git."""
    requested = set()
    for line in git_trace.splitlines():
        matched = GIT_TRACE_INVOCATION.search(line)
        if not matched:
            continue
        for token in matched.group(1).split():
            candidate = token.strip("'\",;()[]{}").split("...")[0].split("..")[0].split("^")[0]
            if REVISION_TOKEN.match(candidate):
                requested.add(candidate)
    return requested


def _revisions_from(logs: list[str]) -> set[str]:
    """Revisions requested during ONE identity's execution, from its own rotated git logs."""
    requested: set[str] = set()
    for target in logs:
        path = pathlib.Path(target)
        if path.is_file():
            requested |= requested_revisions(path.read_text(encoding="utf-8", errors="replace"))
    return requested


def unresolvable_revisions(
    repo: pathlib.Path, scaffold: pathlib.Path, home: pathlib.Path, requested: set[str]
) -> list[str]:
    """Which of them the DECLARED canonical namespace cannot resolve.

    A verifier pinning a commit that lives only on an operator-local branch is not measurable
    against canonical truth: its answer would come from whichever branches the operator happens to
    keep. Deciding this against the canonical repository -- not against the operator's -- is what
    makes the classification identical on every machine.
    """
    missing = []
    for revision in sorted(requested):
        probe = _isolated_git(scaffold, home, repo, "rev-parse", "--verify", "--quiet", revision)
        if probe.returncode != 0:
            missing.append(revision)
    return missing


def parse_trace(
    text: str,
) -> tuple[bool, dict[str, set[str]], dict[str, set[str]], dict, dict[str, list[str]]]:
    """(observed, paths, module paths, env names, git-log files) -- all keyed by node."""
    observed = PROBE_HEADER in text
    paths: dict[str, set[str]] = {}
    module_paths: dict[str, set[str]] = {}
    env: dict[str, set[str]] = {}
    gitlogs: dict[str, list[str]] = {}
    node = ""
    for line in text.splitlines():
        kind, _, value = line.partition("\t")
        if kind == "node":
            node = value
        elif kind == "gitlog":
            attributed, _, target = value.partition("\t")
            gitlogs.setdefault(attributed, []).append(target)
        elif kind == "path":
            paths.setdefault(node, set()).add(value)
        elif kind == "mpath":
            module_paths.setdefault(node, set()).add(value)
        elif kind == "env":
            env.setdefault(node, set()).add(value)
    return observed, paths, module_paths, env, gitlogs


def admissibility(
    tree: pathlib.Path,
    scaffold: pathlib.Path,
    home: pathlib.Path,
    observed: bool,
    accessed: set[str],
    module_accessed: set[str],
    env_names: set[str],
    ignored: set[str],
    missing_revisions: list[str],
) -> tuple[str, str]:
    """(state, reason) for one measured identity, from what it actually read.

    UNKNOWN is never mapped to either neighbour. An unobserved module does not quietly enter debt
    reconciliation using the workstation's answer, and it is not quietly excluded either.
    """
    if not observed:
        return UNKNOWN, "inputs were not observed, so their authority cannot be established"
    if missing_revisions:
        return (
            ENVIRONMENT_DEPENDENT,
            f"asks git for {missing_revisions[0]}, which the declared canonical ref namespace "
            "does not contain, so its answer would come from operator-local refs",
        )
    # There is deliberately no environment axis here; see ENVIRONMENT_NOTE. env_names is carried
    # so the harness can report what was read without it deciding admissibility.
    del env_names
    # Repository authority, judged without attribution: a non-canonical dependency reached through
    # any depth of helper is still this identity's dependency. This is the DEF-PCPE-01 class.
    for raw in sorted(accessed):
        relative = _repo_relative(tree, raw)
        if relative is not None and relative in ignored:
            return (
                ENVIRONMENT_DEPENDENT,
                f"depends on {relative}, which this repository declares non-canonical",
            )
    # A separate pass, so the repository-authority reason always wins. Interleaving the two let
    # whichever path happened to sort first decide the reason, and a module reading BOTH a
    # non-canonical repository path and a home location was reported only as the latter.
    for raw in sorted(accessed):
        if _repo_relative(tree, raw) is None and _under(tree, home, raw):
            # The home the policy grants is an empty scaffold directory nothing else touches, so a
            # read there is always the module reaching for a home or cache location.
            return ENVIRONMENT_DEPENDENT, "reads an ambient home or cache location"
    # Elsewhere outside the repository, attribution decides. An imported library probing a machine
    # path is not this module's dependency; the module opening one itself is.
    for raw in sorted(module_accessed):
        if _repo_relative(tree, raw) is not None:
            continue
        resolved = pathlib.Path(raw)
        resolved = resolved if resolved.is_absolute() else tree / resolved
        if _outside_measurement(resolved, scaffold):
            return ENVIRONMENT_DEPENDENT, f"reads the out-of-repository path {raw}"
    return REPO_DETERMINISTIC, "every observed input is canonical tracked repository state"


def _under(tree: pathlib.Path, base: pathlib.Path, raw: str) -> bool:
    candidate = pathlib.Path(raw)
    resolved = candidate if candidate.is_absolute() else tree / candidate
    try:
        return resolved.resolve().is_relative_to(base.resolve())
    except (ValueError, OSError):
        return False


def _repo_relative(tree: pathlib.Path, raw: str) -> str | None:
    candidate = pathlib.Path(raw)
    resolved = candidate if candidate.is_absolute() else tree / candidate
    try:
        return resolved.resolve().relative_to(tree.resolve()).as_posix()
    except (ValueError, OSError):
        return None


def _outside_measurement(resolved: pathlib.Path, scaffold: pathlib.Path) -> bool:
    """The harness's own scaffolding and the interpreter's install are not ambient inputs."""
    for base in (
        scaffold,
        pathlib.Path(sys.prefix),
        pathlib.Path(sys.base_prefix),
    ):
        try:
            if resolved.resolve().is_relative_to(base.resolve()):
                return False
        except (ValueError, OSError):
            continue
    return True


def _sanitized_environment(
    scaffold: pathlib.Path, home: pathlib.Path, trace: pathlib.Path, repo: pathlib.Path
) -> dict:
    """Only what the policy grants. Undeclared ambient values cannot reach the measurement."""
    temp = scaffold / "tmp"
    temp.mkdir(exist_ok=True)
    granted = {
        "PATH": os.environ.get("PATH", ""),
        "PATHEXT": os.environ.get("PATHEXT", ""),
        "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
        "SYSTEMDRIVE": os.environ.get("SYSTEMDRIVE", ""),
        "WINDIR": os.environ.get("WINDIR", ""),
        "COMSPEC": os.environ.get("COMSPEC", ""),
        "TEMP": str(temp),
        "TMP": str(temp),
        "TMPDIR": str(temp),
        "HOME": str(home),
        "USERPROFILE": str(home),
        "PYTHONPATH": str(_write_probe(scaffold)),
        "PYTHONHASHSEED": "0",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUTF8": "1",
        # Bytecode is derived from canonical source, so it is not an ambient input -- but it lands
        # in a gitignored __pycache__, which the authority rule would rightly call non-canonical.
        # Writing it outside the tree removes the phenomenon instead of special-casing its name.
        "PYTHONPYCACHEPREFIX": str(scaffold / "pycache"),
        "PCP_MEASUREMENT_TRACE": str(trace),
        "PCP_MEASUREMENT_ROOT": str(repo),
        # git's own argv log. The RM4 tracer cannot see inside a child git process, and a
        # dependency on a commit that exists only on an operator branch hides there.
        "GIT_TRACE": str(trace.with_suffix(".git")),
        "PCP_GIT_TRACE_DIR": str(scaffold / "gitlogs"),
        # A measured verifier shells out to git constantly. Without these it would answer from the
        # operator's global config, credential helper and terminal, which is precisely the
        # authority BLK-PCPF-01 is about -- and the tracer cannot see inside a child git process.
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": str(scaffold / "gitconfig"),
        "GIT_TERMINAL_PROMPT": "0",
    }
    return {key: value for key, value in granted.items() if value}


def _isolated_git_environment(scaffold: pathlib.Path, home: pathlib.Path) -> dict:
    """Git with no operator config, no credentials and no terminal to prompt at."""
    config = scaffold / "gitconfig"
    if not config.is_file():
        config.write_text("", encoding="utf-8")
    granted = {
        "PATH": os.environ.get("PATH", ""),
        "PATHEXT": os.environ.get("PATHEXT", ""),
        "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
        "SYSTEMDRIVE": os.environ.get("SYSTEMDRIVE", ""),
        "WINDIR": os.environ.get("WINDIR", ""),
        "COMSPEC": os.environ.get("COMSPEC", ""),
        "HOME": str(home),
        "USERPROFILE": str(home),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": str(config),
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_ASKPASS": "",
        "SSH_ASKPASS": "",
        "GIT_AUTHOR_NAME": "pcp-canonical-measurement",
        "GIT_AUTHOR_EMAIL": "pcp@localhost",
        "GIT_COMMITTER_NAME": "pcp-canonical-measurement",
        "GIT_COMMITTER_EMAIL": "pcp@localhost",
    }
    return {key: value for key, value in granted.items() if value != "" or key.endswith("ASKPASS")}


def _isolated_git(
    scaffold: pathlib.Path, home: pathlib.Path, cwd: pathlib.Path, *args: str
) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        env=_isolated_git_environment(scaffold, home),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def materialize_canonical_repository(
    commit: str, scaffold: pathlib.Path, home: pathlib.Path
) -> tuple[pathlib.Path, pathlib.Path, str]:
    """Build the measurement repository instead of borrowing the operator's.

    A bare fixture receives exactly the canonical commit under the declared ref namespace, and the
    measurement repository is cloned from it. The clone therefore has its own .git, exactly the
    declared refs, and an origin pointing at a deterministic local fixture -- so operator branches,
    the operator's origin URL, their credentials and the network are all simply absent rather than
    filtered out.
    """
    remote = scaffold / "canonical-remote.git"
    repo = scaffold / "repo"
    created = _isolated_git(scaffold, home, scaffold, "init", "--quiet", "--bare", str(remote))
    if created.returncode != 0:
        return repo, remote, f"the canonical remote fixture could not be created: {created.stderr}"
    for ref in DECLARED_REFS:
        fetched = _isolated_git(
            scaffold, home, remote, "fetch", "--quiet", str(ROOT), f"{commit}:{ref}"
        )
        if fetched.returncode != 0:
            return repo, remote, f"{commit[:12]} could not be placed on {ref}: {fetched.stderr}"
    # Without this the fixture's HEAD names whichever default branch git was configured for, the
    # clone finds it missing, and checks out an empty working tree -- an empty domain, silently.
    pointed = _isolated_git(scaffold, home, remote, "symbolic-ref", "HEAD", DECLARED_REFS[0])
    if pointed.returncode != 0:
        return repo, remote, f"the fixture HEAD could not be set: {pointed.stderr}"
    cloned = _isolated_git(scaffold, home, scaffold, "clone", "--quiet", str(remote), str(repo))
    if cloned.returncode != 0:
        return repo, remote, f"the measurement repository could not be cloned: {cloned.stderr}"
    return repo, remote, ""


def ref_manifest(repo: pathlib.Path, scaffold: pathlib.Path, home: pathlib.Path) -> list[str]:
    """Every ref the measurement repository contains, so provenance can state the namespace."""
    listed = _isolated_git(
        scaffold, home, repo, "for-each-ref", "--format=%(refname) %(objectname)"
    )
    return sorted(line.strip() for line in listed.stdout.splitlines() if line.strip())


def canonical_measurement(commit: str = "", ambient: pathlib.Path | None = None) -> dict:
    """Measure both governance domains from a standalone canonical repository.

    `ambient` exists only so a test can PROVE isolation by seeding state into the measurement
    repository. Canonical runs never pass it.
    """
    # Resolved, never the caller's spelling: recording "b21d0b0" for one run and the full
    # SHA for another makes two records of the SAME measurement look like two measurements.
    commit = git("rev-parse", commit or "HEAD") or commit
    with tempfile.TemporaryDirectory(
        prefix="pcp-canonical-", ignore_cleanup_errors=True
    ) as scaffold_name:
        scaffold = pathlib.Path(scaffold_name)
        home = scaffold / "home"
        home.mkdir()
        traces = scaffold / "traces"
        traces.mkdir()
        (scaffold / "gitlogs").mkdir()
        repo, remote, error = materialize_canonical_repository(commit, scaffold, home)
        if error:
            return {"error": error}
        return _measure_tree(repo, scaffold, home, traces, commit, ambient)


def _measure_tree(
    tree: pathlib.Path,
    scaffold: pathlib.Path,
    home: pathlib.Path,
    traces: pathlib.Path,
    commit: str,
    ambient: pathlib.Path | None,
) -> dict:
    residue = subprocess.run(
        ["git", "status", "--porcelain", "--ignored"],
        cwd=tree,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    ).stdout.strip()
    if ambient and ambient.is_dir():
        for source in ambient.rglob("*"):
            if source.is_file():
                target = tree / source.relative_to(ambient)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(source.read_bytes())
    elif residue:
        return {"error": f"the measurement checkout is not pristine: {residue.splitlines()[0]}"}

    verifiers, tests = domains_at(tree)
    states: dict[str, tuple[str, str]] = {}
    failing: set[str] = set()
    seen_paths: set[str] = set()
    raw: dict[str, tuple[bool, set[str], set[str], set[str]]] = {}
    requested: dict[str, set[str]] = {}

    for relpath in verifiers:
        identity = f"verifier:{pathlib.Path(relpath).name}"
        trace = traces / f"{pathlib.Path(relpath).stem}.trace"
        result = subprocess.run(
            [sys.executable, relpath],
            cwd=tree,
            env=_sanitized_environment(scaffold, home, trace, tree),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        observed, paths, module_paths, env, gitlogs = parse_trace(
            trace.read_text(encoding="utf-8", errors="replace") if trace.is_file() else ""
        )
        accessed = set().union(*paths.values()) if paths else set()
        git_log = trace.with_suffix(".git")
        requested[identity] = requested_revisions(
            git_log.read_text(encoding="utf-8", errors="replace") if git_log.is_file() else ""
        )
        raw[identity] = (
            observed,
            accessed,
            set().union(*module_paths.values()) if module_paths else set(),
            set().union(*env.values()) if env else set(),
        )
        seen_paths |= accessed
        if result.returncode != 0:
            failing.add(identity)

    node_failures: set[str] = set()
    if tests:
        trace = traces / "pytest.trace"
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "-p",
                "no:randomly",
                # BLK-PCPF-02: the session-end cache write is harness I/O, and attributing it to
                # whichever node happened to run last silently exempted a real new failure.
                # Disabled rather than filtered by name, so there is no list to keep growing.
                "-p",
                "no:cacheprovider",
                "-p",
                "pcp_trace_plugin",
                "-o",
                f"cache_dir={scaffold / 'pytest_cache'}",
                "--tb=no",
                *tests,
            ],
            cwd=tree,
            env=_sanitized_environment(scaffold, home, trace, tree),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        node_failures = {
            line.split()[1]
            for line in result.stdout.splitlines()
            if line.startswith("FAILED") and len(line.split()) > 1
        }
        observed, paths, module_paths, env, gitlogs = parse_trace(
            trace.read_text(encoding="utf-8", errors="replace") if trace.is_file() else ""
        )
        for node in sorted(node_failures):
            origin = node.split("::")[0]
            accessed = paths.get(node, set()) | paths.get(origin, set())
            attributed = module_paths.get(node, set()) | module_paths.get(origin, set())
            names = env.get(node, set()) | env.get(origin, set())
            raw[f"test:{node}"] = (observed, accessed, attributed, names)
            requested[f"test:{node}"] = _revisions_from(
                gitlogs.get(node, []) + gitlogs.get(origin, [])
            )
            seen_paths |= accessed
        failing |= {f"test:{node}" for node in node_failures}

    ignored = non_canonical_paths(tree, _relative_candidates(tree, seen_paths))
    resolvable_cache: dict[tuple[str, ...], list[str]] = {}
    for identity, (observed, accessed, attributed, names) in raw.items():
        key = tuple(sorted(requested.get(identity, set())))
        if key not in resolvable_cache:
            resolvable_cache[key] = unresolvable_revisions(
                tree, scaffold, home, requested.get(identity, set())
            )
        states[identity] = admissibility(
            tree,
            scaffold,
            home,
            observed,
            accessed,
            attributed,
            names,
            ignored,
            resolvable_cache[key],
        )

    admissible = sorted(
        identity for identity in failing if states.get(identity, ("", ""))[0] == REPO_DETERMINISTIC
    )
    return {
        "commit": commit,
        "verifiers": len(verifiers),
        "tests": len(tests),
        "failures": admissible,
        "environment_dependent": sorted(
            (identity, reason)
            for identity, (state, reason) in states.items()
            if state == ENVIRONMENT_DEPENDENT
        ),
        "unknown": sorted(
            (identity, reason) for identity, (state, reason) in states.items() if state == UNKNOWN
        ),
        "policy_digest": measurement_policy_digest(),
        "ref_manifest": ref_manifest(tree, scaffold, home),
        **measurement_policy(),
    }


def _relative_candidates(tree: pathlib.Path, accessed: set[str]) -> set[str]:
    candidates = set()
    for raw in accessed:
        candidate = pathlib.Path(raw)
        resolved = candidate if candidate.is_absolute() else tree / candidate
        try:
            candidates.add(resolved.resolve().relative_to(tree.resolve()).as_posix())
        except (ValueError, OSError):
            continue
    return {path for path in candidates if path not in {"", "."}}


def measured_governance_failures() -> list[str]:
    """Exact ADMISSIBLE failure identities from a canonical isolated measurement.

    Only REPO_DETERMINISTIC identities reach debt reconciliation. Environment-dependent and unknown
    identities are reported separately by the caller, because registering them as repository debt
    would record "this machine lacked runtime evidence" as a known governance failure (RM4 §12).
    """
    return list(canonical_measurement().get("failures", []))


def _identities(block: str) -> set[str]:
    return {
        line.strip().removeprefix("- ").strip()
        for line in block.splitlines()
        if line.strip().removeprefix("- ").startswith(("verifier:", "test:"))
    }


def debt_sections(pm_doc: str) -> tuple[set[str], set[str]]:
    """(ACTIVE, HISTORICAL) exact identities, read from the PM state.

    ACTIVE debt exempts a CURRENTLY failing identity. HISTORICAL debt is audit record only and
    exempts nothing: an identity that starts failing again while only historical is a new blocker.
    Keeping a resolved identity active would pre-absolve the regression that reintroduces it (A-4).
    """
    active_block, _, rest = pm_doc.partition(ACTIVE_DEBT_HEADING)
    if not _:
        return set(), set()
    active_body, _, historical_body = rest.partition(HISTORICAL_DEBT_HEADING)
    return _identities(active_body), _identities(historical_body)


def registered_debt_ids(pm_doc: str) -> set[str]:
    """Only ACTIVE debt participates in current blocker reconciliation."""
    return debt_sections(pm_doc)[0]


def new_unregistered_failures(measured: list[str], registered: set[str]) -> list[str]:
    """MEASURED - ACTIVE. Non-empty means BLOCKERS may not be NONE."""
    return sorted(set(measured) - registered)


def overregistered_active_debt(measured: list[str], registered: set[str]) -> list[str]:
    """ACTIVE - MEASURED. An active identity that no longer fails must be retired, not retained."""
    return sorted(registered - set(measured))


def authority_inputs() -> list[str]:
    """Every input whose change can alter the measured result.

    Derived from what reconciliation actually consumes, not from "files this stage happened to
    touch". The active-debt register is an input -- it decides exemption -- which is why editing it
    must invalidate a measurement (gap A2).
    """
    return sorted(
        {
            *applicable_governance_verifiers(),
            *applicable_governance_tests(),
            f"scripts/{pathlib.Path(__file__).name}",
        }
    )


def authority_input_digest() -> str:
    """Deterministic provenance: a measurement can prove WHICH input state it measured.

    Path-based freshness could only see files it was told to watch. A digest cannot miss an input
    that reconciliation reads, because the input's content is what is hashed.
    """
    hasher = hashlib.sha256()
    for relpath in authority_inputs():
        hasher.update(relpath.encode("utf-8"))
        hasher.update(read(relpath).encode("utf-8"))
    active, historical = debt_sections(read(PM_STATE))
    for entry in sorted(active):
        hasher.update(b"active:" + entry.encode("utf-8"))
    for entry in sorted(historical):
        hasher.update(b"historical:" + entry.encode("utf-8"))
    # RM4: how the measurement is taken decides what it can see, so the policy and the tracer that
    # implements the admissibility contract are authority inputs too.
    hasher.update(b"policy:" + measurement_policy_digest().encode("utf-8"))
    return hasher.hexdigest()


def governance_measurement_stale(pm: dict[str, str]) -> list[str]:
    """Empty when the recorded measurement still describes the current authority-input state."""
    recorded = pm.get("GOVERNANCE_INPUT_DIGEST", "")
    if not recorded:
        return ["GOVERNANCE_INPUT_DIGEST is absent, so no measurement provenance exists"]
    current = authority_input_digest()
    if recorded != current:
        return [
            f"authority inputs changed since the measurement: recorded {recorded[:12]}, "
            f"current {current[:12]} over {len(authority_inputs())} inputs plus the debt register"
        ]
    return []


def provenance_conflicts(pm: dict[str, str]) -> list[str]:
    """A4: the snapshot's own provenance fields must form a coherent record."""
    conflicts = []
    by_stage = pm.get("RECONCILED_BY_STAGE", "")
    current_stage = pm.get("CURRENT_STAGE", "")
    if by_stage and current_stage and by_stage != current_stage:
        conflicts.append(
            f"RECONCILED_BY_STAGE is {by_stage!r} but the snapshot's CURRENT_STAGE is "
            f"{current_stage!r}; the values were re-recorded by a different stage than they claim"
        )
    measured_at = pm.get("GOVERNANCE_MEASURED_AT", "")
    against = pm.get("RECONCILED_AGAINST_MAIN", "")
    if commit_exists(measured_at) and commit_exists(against):
        if not (measured_at == against or is_ancestor(measured_at, against)):
            conflicts.append(
                "GOVERNANCE_MEASURED_AT is not the reconciliation commit nor an ancestor of it; "
                "the measurement claims a state the snapshot was never reconciled against"
            )
    return conflicts


def measurement_provenance_conflicts(pm: dict[str, str]) -> list[str]:
    """RM4: a recorded measurement must state the policy it was taken under, and that policy must
    still be the current one. Otherwise two results that disagree cannot be told apart."""
    conflicts = []
    required = (
        "CANONICAL_MEASURED_COMMIT",
        "MEASUREMENT_POLICY_ID",
        "MEASUREMENT_POLICY_DIGEST",
        "MEASUREMENT_ISOLATION_MODE",
    )
    for field in required:
        if not pm.get(field):
            conflicts.append(f"{field} is absent, so the measurement's execution policy is unknown")
    if pm.get("MEASUREMENT_POLICY_ID") and pm["MEASUREMENT_POLICY_ID"] != MEASUREMENT_POLICY_ID:
        conflicts.append(
            f"MEASUREMENT_POLICY_ID is {pm['MEASUREMENT_POLICY_ID']!r} but this gate measures "
            f"under {MEASUREMENT_POLICY_ID!r}"
        )
    recorded = pm.get("MEASUREMENT_POLICY_DIGEST", "")
    if recorded and recorded != measurement_policy_digest():
        conflicts.append(
            "the measurement policy changed since the recorded measurement, which must be retaken"
        )
    commit = pm.get("CANONICAL_MEASURED_COMMIT", "")
    against = pm.get("RECONCILED_AGAINST_MAIN", "")
    if commit_exists(commit) and commit_exists(against):
        if not (commit == against or is_ancestor(commit, against)):
            conflicts.append(
                "CANONICAL_MEASURED_COMMIT is neither the reconciliation commit nor an ancestor"
            )
    return conflicts


def final_head_conflicts(pm: dict[str, str]) -> list[str]:
    """Whether anything the measurement depends on changed after the measurement was taken.

    A stage can otherwise end with an authority-bearing commit landing after its last measurement,
    leaving evidence that describes a state no longer on main. Machine-checked rather than argued:
    every path changed between the measured commit and current main is examined, and a governance
    verifier or test among them means the measurement must be retaken.
    """
    measured = pm.get("CANONICAL_MEASURED_COMMIT", "")
    head = canonical_main()
    if not commit_exists(measured) or not head or measured == head:
        return []
    if not is_ancestor(measured, head):
        return [f"CANONICAL_MEASURED_COMMIT {measured[:12]} is not an ancestor of current main"]
    changed = git("diff", "--name-only", f"{measured}..{head}").splitlines()
    authority = sorted(path for path in changed if GOVERNANCE_ARTIFACT.match(path.strip()))
    if authority:
        return [
            f"{len(authority)} governance artifact(s) changed after the measurement "
            f"({', '.join(authority[:3])}); the measurement must be retaken"
        ]
    return []


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
    known = {"--remote", "--governance", "--pm-state"}
    unknown = [
        arg
        for index, arg in enumerate(sys.argv[1:], start=1)
        if arg.startswith("--") and arg not in known
    ]
    if unknown:
        # A3: a mistyped --governance must not silently produce a weaker PASS that a recovery
        # session could mistake for a full measurement.
        print(f"  [FAIL] usage: unknown option(s) {unknown}; known options are {sorted(known)}")
        print(f"{MARKER}: FAIL")
        return 2
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
    provenance = provenance_conflicts(pm)
    for conflict in provenance:
        print(f"  [{CONFLICT}] provenance: {conflict}")
    expect(provenance == [], "check17a", f"{CONFLICT}: snapshot provenance is self-inconsistent")

    stale_since = governance_measurement_stale(pm)
    expect(
        stale_since == [],
        "check18",
        f"the recorded governance measurement no longer describes current authority inputs and "
        f"must be retaken: {stale_since}",
    )
    if "--governance" in sys.argv:
        measurement = canonical_measurement()
        expect(
            "error" not in measurement,
            "check19c",
            f"the canonical measurement could not be taken: {measurement.get('error', '')}",
        )
        measured = list(measurement.get("failures", []))
        unregistered = new_unregistered_failures(measured, registered)
        overregistered = overregistered_active_debt(measured, registered)
        for failure in unregistered:
            print(f"  [{GOVERNANCE_REGRESSION}] unregistered governance failure: {failure}")
        for stale in overregistered:
            print(f"  [{GOVERNANCE_REGRESSION}] active debt that no longer fails: {stale}")
        for identity, reason in measurement.get("environment_dependent", []):
            print(f"  [ENVIRONMENT_DEPENDENT] {identity}: {reason}")
        for identity, reason in measurement.get("unknown", []):
            print(f"  [UNKNOWN] {identity}: {reason}")
        expect(
            unregistered == [],
            "check19",
            f"{GOVERNANCE_REGRESSION}: {len(unregistered)} measured failure(s) are not active "
            "registered debt, so BLOCKERS: NONE is invalid",
        )
        expect(
            overregistered == [],
            "check19a",
            f"{GOVERNANCE_REGRESSION}: {len(overregistered)} active debt identity(ies) no longer "
            "fail; retire them, or they pre-absolve the regression that reintroduces them",
        )
        # An input whose authority nobody can establish must not be resolved by guessing. Mapping
        # UNKNOWN to environment-dependent would silently exclude it; mapping it to deterministic
        # would silently admit the workstation's answer. It blocks instead.
        expect(
            measurement.get("unknown", []) == [],
            "check19b",
            f"{len(measurement.get('unknown', []))} measured identity(ies) have inputs of "
            "unestablished authority, so BLOCKERS: NONE is invalid",
        )
        reconciled = not unregistered and not overregistered and not measurement.get("unknown")
        notes.append(
            f"canonical measurement at {measurement.get('commit', '')[:12]} "
            f"[{MEASUREMENT_ISOLATION_MODE}]: {measurement.get('verifiers', 0)} verifiers + "
            f"{measurement.get('tests', 0)} tests applicable, "
            f"{len(measurement.get('environment_dependent', []))} environment-dependent, "
            f"{len(measurement.get('unknown', []))} unknown, {len(measured)} admissible failing, "
            + ("all reconciled" if reconciled else "NOT reconciled")
        )
    expect(
        pm.get("BLOCKERS", "").upper() != "NONE" or stale_since == [],
        "check20",
        "BLOCKERS: NONE is claimed against a stale governance measurement",
    )

    # RM4: evidence must distinguish "same commit measured under another ambient environment" from
    # "same canonical measurement policy". Without this a recorded result cannot be reproduced.
    policy_conflicts = measurement_provenance_conflicts(pm)
    for conflict in policy_conflicts:
        print(f"  [{CONFLICT}] measurement provenance: {conflict}")
    expect(
        policy_conflicts == [],
        "check21",
        f"{CONFLICT}: the recorded measurement does not state a reproducible execution policy",
    )

    # RM5 section 25: the measured commit and the final head must not disagree about anything the
    # measurement read.
    head_conflicts = final_head_conflicts(pm)
    for conflict in head_conflicts:
        print(f"  [{CONFLICT}] final head: {conflict}")
    expect(
        head_conflicts == [],
        "check22",
        f"{CONFLICT}: an authority-bearing change landed after the recorded measurement",
    )

    if remote:
        remote_conflicts = confirm_remote(pm)
        for conflict in remote_conflicts:
            print(f"  [{CONFLICT}] {conflict}")
        expect(remote_conflicts == [], "check16", f"{CONFLICT}: remote state disagrees")

    for note in notes:
        print(f"  [note] {note}")
    checks = 24 if remote else 23
    print(f"{MARKER}: checks={checks} failures={len(failures)}")
    print(f"{MARKER}: {'PASS' if not failures else 'FAIL'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
