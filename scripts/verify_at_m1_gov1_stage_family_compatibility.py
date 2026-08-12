#!/usr/bin/env python3
"""AT-M1-GOV1 -- stage-family governance compatibility verifier.

Deterministic and read-only. Confirms that GOV-STAGE-FAMILY-ALLOWLIST-01 is closed: the ALIGN1
current-state admission rule no longer depends on the literal `step66` stage-family name, while the
historical frozen positive-scope check is untouched, the Step66 family keeps working, arbitrary
scripts/ and tests/ paths are still rejected, and no broad path allowlist was introduced.

Positive scope is a fixed baseline plus an explicit path registry compared by SET EQUALITY.

Starts no runtime, container, database, migration apply or external provider.

Marker: AT_M1_GOV1_STAGE_FAMILY_COMPATIBILITY_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import importlib.util
import pathlib
import re
import subprocess
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
MARKER = "AT_M1_GOV1_STAGE_FAMILY_COMPATIBILITY_VERIFY"

GOV1_BASELINE = "2d4da808b1a89ea278fbb760e27f49047995165e"
GOV1_BASELINE_SHORT = "2d4da80"
# Frozen at canonicalization (AT-M1-GOV1-M1). While PR #30 was open this was BASELINE...HEAD,
# safe only because HEAD was the PR head bounded by the exact 5-path registry. Merged, HEAD is
# main and advances, so it can no longer be a positive endpoint.
GOV1_STAGE_HEAD = "2faa9c7fe68dcd1bb04aab971c34a6d0bb047e2c"
GOV1_POSITIVE_RANGE = f"{GOV1_BASELINE}...{GOV1_STAGE_HEAD}"

ALIGN1_VERIFIER = "scripts/verify_step66d_align1_delivery_decision_model.py"
ALIGN1_TEST = "tests/test_step66d_align1_delivery_decision_model.py"
GOV1_VERIFIER = "scripts/verify_at_m1_gov1_stage_family_compatibility.py"
GOV1_TEST = "tests/test_at_m1_gov1_stage_family_compatibility.py"
GOV1_EVIDENCE = "docs/handoffs/autonomous-team/at-m1-gov1-stage-family-compatibility-evidence.md"

GOV1_EXPECTED_PATHS = frozenset(
    {ALIGN1_VERIFIER, ALIGN1_TEST, GOV1_VERIFIER, GOV1_TEST, GOV1_EVIDENCE}
)

# The ALIGN1 historical boundary. GOV1 must not alter either endpoint or the exact-equality rule.
ALIGN1_CANONICAL_MAIN = "64467fefc9a9ec303f9ddf4c0ce6d46486504d71"
ALIGN1_STAGE_HEAD = "6a8a7bfa2ae758e944b1126881a69fef2d122dcb"
ALIGN1_EXPECTED_PATH_COUNT = 34

# Paths that MUST be admitted by the repaired current-state rule.
MUST_ADMIT = (
    "scripts/verify_step66d_align1_delivery_decision_model.py",
    "tests/test_step66d_align1_delivery_decision_model.py",
    "scripts/verify_step66c4_be3_ra2m_canonicalization.py",
    "tests/test_step66sync1_m2_canonical_merge.py",
    "scripts/verify_at_m1_architecture_reset.py",
    "tests/test_at_m1_architecture_reset.py",
    "scripts/verify_at_m1_gov1_stage_family_compatibility.py",
    "tests/test_at_m1_gov1_stage_family_compatibility.py",
    "scripts/verify_at_m2_team_identity_collaboration.py",
    "tests/test_at_m2_team_identity_collaboration.py",
    "docs/handoffs/autonomous-team/at-m1-gov1-stage-family-compatibility-evidence.md",
    "source/progress.md",
)

# Paths that MUST still be rejected. Being under scripts/ or tests/ is never sufficient.
MUST_REJECT = (
    "scripts/at_runtime_patch.py",
    "scripts/random_helper.py",
    "tests/at_random_helper.py",
    "tests/random_test_helper.py",
    "scripts/verify_unregistered_family.py",
    "tests/test_unregistered_family.py",
    "scripts/verify_.py",
    "tests/test_.py",
    "agents/qa-agent/src/agent.py",
    "apps/orchestrator/src/main.py",
    "shared/sdk/tasks/rbac.py",
    "migrations/037_example.sql",
    "infra/docker-compose/docker-compose.yml",
    "runtime/whatever.py",
    ".github/workflows/ci.yml",
)

# Broad-admission shapes that must not appear in the repaired admission rule.
FORBIDDEN_BROAD_PATTERNS = (
    r'startswith\(\s*"scripts/"\s*\)',
    r'startswith\(\s*"tests/"\s*\)',
    r'"scripts/\*\*"',
    r'"tests/\*\*"',
    r'"docs/\*\*"',
)

FORBIDDEN_SCOPE_PREFIXES = (
    "agents/",
    "apps/",
    "shared/",
    "migrations/",
    "infra/",
    "runtime/",
    ".github/",
)

# AT-M1 architecture artifacts and PR #28 content are out of GOV1's scope entirely.
FORBIDDEN_EXACT_PREFIXES = (
    "docs/architecture/autonomous-team/",
    "docs/contracts/autonomous-team/",
    "docs/decisions/at-m1-architecture-decisions.md",
    "docs/alignment/66-project-completion/master/",
    "shared/sdk/delivery_acceptance/",
    "migrations/036",
)

LEAK_PATTERNS = (
    (r"\b10\.0\.1\.\d{1,3}\b", "internal IPv4 address"),
    (r"aiagent[-]swd", "SSH host alias"),
    (r"\bi[t]admin\b", "internal username"),
    (r"\bstp[a]dmin\b", "internal username"),
    (r"[C]:\\Users\\", "local absolute path"),
    (r"/hom[e]/\w", "local absolute path"),
    (r"post[g]res(?:ql)?://", "database DSN"),
)

failures: list[str] = []
checks_run = 0


def expect(ok: bool, label: str, message: str) -> None:
    global checks_run
    checks_run += 1
    if not ok:
        failures.append(f"{label}: {message}")
        print(f"  [FAIL] {label}: {message}")


def read(relpath: str) -> str:
    path = ROOT / relpath
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=False
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def align1_module():
    """The repaired ALIGN1 verifier, loaded so its real admission rule can be exercised."""
    spec = importlib.util.spec_from_file_location("gov1_align1_verifier", ROOT / ALIGN1_VERIFIER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check33_records_failure(module: Any, registry: tuple[str, ...]) -> bool:
    """Run the REAL check33 against a perturbed registry and observe whether it records a failure.

    This is a behavioral probe, not a source-text assertion: a check33 that still COMPUTES both
    set differences but no longer ENFORCES one of them passes any substring test yet returns
    False here for the disabled direction. Only the imported module instance is perturbed --
    no canonical file is edited -- and its registry and failure list are restored afterwards.
    """
    saved_registry = module.ALIGN1_EXPECTED_PATHS
    saved_failures = list(module.FAILURES)
    module.ALIGN1_EXPECTED_PATHS = tuple(registry)
    module.FAILURES.clear()
    try:
        module.check33_positive_exact_scope()
        return any(message.startswith("check33") for message in module.FAILURES)
    finally:
        module.FAILURES.clear()
        module.FAILURES.extend(saved_failures)
        module.ALIGN1_EXPECTED_PATHS = saved_registry


def main() -> int:  # noqa: PLR0915
    align1_src = read(ALIGN1_VERIFIER)
    align1_test_src = read(ALIGN1_TEST)
    evidence = read(GOV1_EVIDENCE)
    module = align1_module()

    # --- 1. baseline and exact positive scope ------------------------------------------------
    expect(
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", GOV1_BASELINE, "HEAD"], cwd=ROOT, check=False
        ).returncode
        == 0,
        "check01",
        f"the GOV1 canonical baseline {GOV1_BASELINE_SHORT} is not an ancestor of HEAD",
    )
    changed = {
        line.strip().replace("\\", "/")
        for line in git("diff", "--name-only", GOV1_POSITIVE_RANGE).splitlines()
        if line.strip()
    }
    expect(
        changed == GOV1_EXPECTED_PATHS,
        "check02",
        "changed paths are not exactly the GOV1 registry: "
        f"unexpected={sorted(changed - GOV1_EXPECTED_PATHS)} "
        f"missing={sorted(GOV1_EXPECTED_PATHS - changed)}",
    )
    expect(
        len(GOV1_EXPECTED_PATHS) == 5,
        "check03",
        f"the GOV1 registry must hold exactly 5 paths, holds {len(GOV1_EXPECTED_PATHS)}",
    )
    offenders = sorted(p for p in changed if p.startswith(FORBIDDEN_SCOPE_PREFIXES))
    expect(offenders == [], "check04", f"GOV1 changed runtime/source paths: {offenders}")
    out_of_scope = sorted(p for p in changed if p.startswith(FORBIDDEN_EXACT_PREFIXES))
    expect(
        out_of_scope == [],
        "check05",
        f"GOV1 touched AT-M1 architecture, precedence/manifest or PR #28 content: {out_of_scope}",
    )
    expect(
        "source/progress.md" not in changed,
        "check06",
        "source/progress.md must remain unchanged",
    )

    # --- 2. historical frozen scope untouched ------------------------------------------------
    expect(
        f'CANONICAL_MAIN = "{ALIGN1_CANONICAL_MAIN}"' in align1_src,
        "check07",
        "the ALIGN1 canonical baseline constant changed",
    )
    expect(
        f'ALIGN1_STAGE_HEAD = "{ALIGN1_STAGE_HEAD}"' in align1_src,
        "check08",
        "the ALIGN1 frozen stage head changed",
    )
    expect(
        'git("diff", "--name-only", CANONICAL_MAIN, ALIGN1_STAGE_HEAD)' in align1_src,
        "check09",
        "check33 no longer diffs the frozen two-endpoint historical range",
    )
    expect(
        "ALIGN1_STAGE_HEAD" in align1_src and '"HEAD"' not in align1_src.split("def check33")[1],
        "check10",
        "the historical check appears to have been switched to a HEAD endpoint",
    )
    check33 = align1_src.split("def check33_positive_exact_scope")[1].split("\ndef ")[0]
    # Assert the two SET DIFFERENCE EXPRESSIONS, not merely the variable names: `missing = []`
    # keeps the word "missing" while silently turning exact equality into a subset check.
    expect(
        "sorted(set(changed) - set(ALIGN1_EXPECTED_PATHS))" in check33
        and "sorted(set(ALIGN1_EXPECTED_PATHS) - set(changed))" in check33,
        "check11",
        "check33 no longer computes exact set equality in BOTH directions "
        "(unexpected = changed - expected, missing = expected - changed)",
    )
    # check11 proves both differences are COMPUTED; check11a-c prove both are ENFORCED, by
    # perturbing the imported registry in each direction and observing the real check33 fail
    # (AT-M1-GOV1-R1 finding D-01: X2/X3 enforcement-deletion escapes).
    registry = tuple(module.ALIGN1_EXPECTED_PATHS)
    phantom = "docs/handoffs/gov1-rm1-behavioral-probe-phantom.md"
    expect(
        phantom not in registry and check33_records_failure(module, registry + (phantom,)),
        "check11a",
        "check33 does not ENFORCE the missing direction: a registered-but-unchanged path "
        "was not recorded as a failure",
    )
    expect(
        len(registry) > 0 and check33_records_failure(module, registry[:-1]),
        "check11b",
        "check33 does not ENFORCE the unexpected direction: a changed-but-unregistered path "
        "was not recorded as a failure",
    )
    expect(
        not check33_records_failure(module, registry),
        "check11c",
        "behavioral probe control failed: check33 records a failure on the untampered registry",
    )
    expect(
        len(getattr(module, "ALIGN1_EXPECTED_PATHS", ())) == ALIGN1_EXPECTED_PATH_COUNT,
        "check12",
        f"the ALIGN1 historical registry no longer holds {ALIGN1_EXPECTED_PATH_COUNT} paths",
    )
    historical = sorted(
        line
        for line in git(
            "diff", "--name-only", ALIGN1_CANONICAL_MAIN, ALIGN1_STAGE_HEAD
        ).splitlines()
        if line.strip()
    )
    expect(
        set(historical) == set(module.ALIGN1_EXPECTED_PATHS),
        "check13",
        "the ALIGN1 historical frozen scope no longer matches its registry exactly",
    )

    # --- 3. the repaired current-state admission rule ----------------------------------------
    expect(
        hasattr(module, "is_admitted_current_state_path"),
        "check14",
        "the ALIGN1 verifier exposes no single-source admission rule",
    )
    expect(
        hasattr(module, "is_registered_governance_artifact"),
        "check15",
        "the ALIGN1 verifier exposes no registered-governance-artifact classifier",
    )
    expect(
        hasattr(module, "REGISTERED_GOVERNANCE_FAMILIES"),
        "check16",
        "no explicit stage-family registry exists",
    )
    families = {f[0] for f in getattr(module, "REGISTERED_GOVERNANCE_FAMILIES", ())}
    expect(
        "step66" in families,
        "check17",
        f"the step66 stage family is no longer registered: {sorted(families)}",
    )
    expect(
        "autonomous-team" in families,
        "check18",
        f"the autonomous-team stage family is not registered: {sorted(families)}",
    )
    expect(
        len(families) == 2,
        "check19",
        f"exactly two stage families are expected, found {sorted(families)}",
    )

    admit = getattr(module, "is_admitted_current_state_path", lambda _p: False)
    for index, path in enumerate(MUST_ADMIT, start=20):
        expect(admit(path), f"check{index:02d}", f"legitimate governance artifact rejected: {path}")
    for index, path in enumerate(MUST_REJECT, start=32):
        expect(
            not admit(path), f"check{index:02d}", f"non-governance path wrongly admitted: {path}"
        )

    # --- 4. no broad allowlist ---------------------------------------------------------------
    for index, pattern in enumerate(FORBIDDEN_BROAD_PATTERNS, start=47):
        expect(
            re.search(pattern, align1_src) is None,
            f"check{index:02d}",
            f"a broad admission pattern was introduced: {pattern}",
        )
    expect(
        re.search(r'if not p\.startswith\(\(\s*"docs/",\s*"scripts/verify_step66"', align1_src)
        is None,
        "check52",
        "the original step66-bound inline allowlist is still present in the verifier",
    )
    expect(
        'allowed = ("docs/", "scripts/verify_step66", "tests/test_step66")' not in align1_test_src,
        "check53",
        "the mirrored inline allowlist is still present in the ALIGN1 test",
    )
    expect(
        "is_admitted_current_state_path" in align1_test_src,
        "check54",
        "the ALIGN1 test does not consume the verifier's single-source admission rule",
    )

    # --- 5. no governance bypass -------------------------------------------------------------
    for index, bypass in enumerate(
        ("pytest.mark.skip", "pytest.skip", "xfail", "return True  # unknown"), start=55
    ):
        expect(
            bypass not in align1_src and bypass not in align1_test_src,
            f"check{index:02d}",
            f"a governance bypass was introduced: {bypass!r}",
        )
    expect(
        "except Exception" not in align1_src.split("def is_admitted_current_state_path")[1][:600],
        "check59",
        "the admission rule swallows exceptions",
    )
    expect(
        admit("") is False,
        "check60",
        "an empty path is admitted -- the rule has an empty/fallback admission hole",
    )

    # --- 6. the ALIGN1 verifier still passes -------------------------------------------------
    result = subprocess.run(
        [sys.executable, str(ROOT / ALIGN1_VERIFIER)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    expect(
        result.returncode == 0
        and "STEP66D_ALIGN1_DELIVERY_DECISION_MODEL_VERIFY: PASS" in result.stdout,
        "check61",
        f"the repaired ALIGN1 verifier does not pass: {result.stdout[-400:]}",
    )

    # --- 7. evidence -------------------------------------------------------------------------
    expect(bool(evidence), "check62", "the GOV1 evidence document is missing")
    for index, needle in enumerate(
        (
            GOV1_BASELINE_SHORT,
            "GOV-STAGE-FAMILY-ALLOWLIST-01",
            "REGISTERED_GOVERNANCE_FAMILIES",
            ALIGN1_STAGE_HEAD[:7],
            "992",
            "production_executed_true_count",
        ),
        start=63,
    ):
        expect(
            needle in evidence,
            f"check{index:02d}",
            f"the evidence document does not record {needle!r}",
        )
    expect(
        "3f18e07" in evidence and "c9145cd" in evidence,
        "check69",
        "the evidence does not record the PR #29 and PR #28 heads as unchanged",
    )

    scanned = "\n".join(read(path) for path in sorted(GOV1_EXPECTED_PATHS))
    for index, (pattern, label) in enumerate(LEAK_PATTERNS, start=70):
        expect(
            re.search(pattern, scanned) is None,
            f"check{index:02d}",
            f"a GOV1 file leaks a {label}",
        )

    print(f"{MARKER}: checks={checks_run} failures={len(failures)}")
    if failures:
        print(f"{MARKER}: FAIL")
        return 1
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
