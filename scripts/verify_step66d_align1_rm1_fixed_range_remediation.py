"""Deterministic verifier for Step 66D-ALIGN1-RM1 fixed-range verifier integrity remediation.

Offline and read-only. Starts no container, opens no database connection, contacts no Vault, OIDC
provider or Kubernetes API, reads no secret, and performs no network operation other than reading
local Git objects.

Closes Step 66D-ALIGN1-R1 findings R1-F01 through R1-F05.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

MARKER = "STEP66D_ALIGN1_RM1_FIXED_RANGE_REMEDIATION_VERIFY: PASS"

ROOT = Path(__file__).resolve().parents[1]

CANONICAL_MAIN = "64467fefc9a9ec303f9ddf4c0ce6d46486504d71"
ALIGN1_COMMIT = "f25d12baea7a76e1bc5d29bf884765f16c8536ac"
# BOUNDED POST-MERGE SCOPE FREEZE (Step 66D-ALIGN1-M1): the RM1 commit is now an ancestor of
# main, so "commits above ALIGN1" must be measured over the frozen branch range, not to HEAD.
RM1_COMMIT = "6a8a7bfa2ae758e944b1126881a69fef2d122dcb"

MANIFEST = (
    ROOT
    / "docs"
    / "handoffs"
    / "66d-delivery-acceptance"
    / "step66d-align1-rm1-stage-boundary-manifest.md"
)
EVIDENCE = ROOT / "docs" / "test" / "step66d-align1-rm1-verifier-remediation-evidence.md"
ALIGN1_EVIDENCE = ROOT / "docs" / "test" / "step66d-align1-canonical-alignment-evidence.md"
ALIGN1_VERIFIER = ROOT / "scripts" / "verify_step66d_align1_delivery_decision_model.py"

# The six historical stages whose scope checks R1 found drifting, with the frozen boundary each
# must now use. These values are also recorded in the stage-boundary manifest; check05 proves the
# two agree, so neither can be moved on its own.
STAGE_BOUNDARIES = {
    "scripts/verify_step66sync1_claude_code_reconciliation.py": (
        "c1db4ccbfd88fa775e4761c932835896b9b980ed",
        "828ea900d53edab6f8441f50723e52955a1049e1",
    ),
    "tests/test_step66sync1_claude_code_reconciliation.py": (
        "c1db4ccbfd88fa775e4761c932835896b9b980ed",
        "828ea900d53edab6f8441f50723e52955a1049e1",
    ),
    "scripts/verify_step66sync1_final_partner_reconciliation.py": (
        "c1db4ccbfd88fa775e4761c932835896b9b980ed",
        "2396c6c7002387c886463bd38158b9ddc3bfb9e2",
    ),
    "tests/test_step66sync1_final_partner_reconciliation.py": (
        "c1db4ccbfd88fa775e4761c932835896b9b980ed",
        "2396c6c7002387c886463bd38158b9ddc3bfb9e2",
    ),
    "scripts/verify_step66sync1_m1_canonicalization.py": (
        "c1db4ccbfd88fa775e4761c932835896b9b980ed",
        "1278b8944e3a8f824a9b35f82382fa8587e7989d",
    ),
    "tests/test_step66sync1_m1_canonicalization.py": (
        "c1db4ccbfd88fa775e4761c932835896b9b980ed",
        "1278b8944e3a8f824a9b35f82382fa8587e7989d",
    ),
    "scripts/verify_step66c4_be3_ra2m_canonicalization.py": (
        "44ab32ceab60d417ef1e0800be6cd00fc730b12e",
        "edafc0ca9111bc6dd76bc3ab59b5ea110f2f05d6",
    ),
    "tests/test_step66c4_be3_ra2m_canonicalization.py": (
        "44ab32ceab60d417ef1e0800be6cd00fc730b12e",
        "edafc0ca9111bc6dd76bc3ab59b5ea110f2f05d6",
    ),
}

# M2 and RA-2M2 express the same frozen range through their pre-existing MERGE_COMMIT and
# RECORD_COMMIT constants rather than a separate STAGE_BASELINE/STAGE_HEAD pair.
RECORD_RANGE_FILES = {
    "scripts/verify_step66sync1_m2_canonical_merge.py": (
        "7971ae0c5a5d90a186efd4c52f75988720ce214e",
        "44ab32ceab60d417ef1e0800be6cd00fc730b12e",
    ),
    "tests/test_step66sync1_m2_canonical_merge.py": (
        "7971ae0c5a5d90a186efd4c52f75988720ce214e",
        "44ab32ceab60d417ef1e0800be6cd00fc730b12e",
    ),
    "scripts/verify_step66c4_be3_ra2m2_canonical_merge.py": (
        "aa02ad5b7fa5ed3997d44420c2f2ec8a2c87c798",
        "64467fefc9a9ec303f9ddf4c0ce6d46486504d71",
    ),
    "tests/test_step66c4_be3_ra2m2_canonical_merge.py": (
        "aa02ad5b7fa5ed3997d44420c2f2ec8a2c87c798",
        "64467fefc9a9ec303f9ddf4c0ce6d46486504d71",
    ),
}

CROSS_STAGE_FILES = tuple(sorted({*STAGE_BOUNDARIES, *RECORD_RANGE_FILES}))

PREVIOUSLY_OMITTED = "tests/test_step66c4_be3_ra2m2_canonical_merge.py"

GENERIC_PREFIXES = ('"docs/",', '"scripts/verify_step66",', '"tests/test_step66",')

RUNTIME_PREFIXES = ("apps/", "agents/", "services/", "shared/", "migrations/", "infra/")

PROBES = {
    "docs": "docs/review-probes/unrelated-governance-probe.md",
    "verifier": "scripts/verify_step66_unrelated_probe.py",
    "test": "tests/test_step66_unrelated_probe.py",
    "runtime": "apps/review_probe/unauthorized_runtime_change.txt",
}

FAILURES: list[str] = []


def bad(message: str) -> None:
    FAILURES.append(message)


def git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        return ""
    return result.stdout.decode("utf-8").strip()


def read(path: Path) -> str:
    if not path.is_file():
        bad(f"missing required file: {path.relative_to(ROOT).as_posix()}")
        return ""
    return path.read_text(encoding="utf-8")


def registered_paths(body: str) -> tuple[str, ...]:
    match = re.search(r"(?m)^EXPECTED_STAGE_PATHS\s*=\s*\((.*?)^\)", body, re.DOTALL)
    if not match:
        return ()
    return tuple(sorted(re.findall(r'"([^"]+)"', match.group(1))))


def align1_registered_paths(body: str) -> tuple[str, ...]:
    match = re.search(r"(?m)^ALIGN1_EXPECTED_PATHS\s*=\s*\((.*?)^\)", body, re.DOTALL)
    if not match:
        return ()
    return tuple(sorted(re.findall(r'"([^"]+)"', match.group(1))))


def is_ancestor(commit: str) -> bool:
    return (
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", commit, "HEAD"], cwd=ROOT, check=False
        ).returncode
        == 0
    )


def check01_pr_baseline() -> None:
    if not is_ancestor(CANONICAL_MAIN):
        bad(f"check01: canonical main {CANONICAL_MAIN[:7]} is not an ancestor of HEAD")


def check02_align1_commit_preserved() -> None:
    if not is_ancestor(ALIGN1_COMMIT):
        bad(f"check02: the original ALIGN1 commit {ALIGN1_COMMIT[:7]} is not an ancestor of HEAD")


def check03_single_remediation_commit() -> None:
    count = git("rev-list", "--count", f"{ALIGN1_COMMIT}..{RM1_COMMIT}")
    if count != "1":
        bad(f"check03: expected exactly one RM1 commit above the ALIGN1 commit, found {count}")


def check04_fixed_boundaries_present() -> None:
    for rel, (base, head) in STAGE_BOUNDARIES.items():
        body = read(ROOT / rel)
        if f'STAGE_BASELINE = "{base}"' not in body:
            bad(f"check04: {rel} does not pin STAGE_BASELINE to {base[:7]}")
        if f'STAGE_HEAD = "{head}"' not in body:
            bad(f"check04: {rel} does not pin STAGE_HEAD to {head[:7]}")
        if not registered_paths(body):
            bad(f"check04: {rel} has no EXPECTED_STAGE_PATHS registry")
    for rel, (base, head) in RECORD_RANGE_FILES.items():
        body = read(ROOT / rel)
        if f'"{base}"' not in body or f'"{head}"' not in body:
            bad(f"check04: {rel} does not pin its frozen merge/record range")


def check05_manifest_agrees_with_constants() -> None:
    """A boundary cannot be moved in the verifier alone, nor in the manifest alone."""
    manifest = read(MANIFEST)
    for rel, (base, head) in {**STAGE_BOUNDARIES, **RECORD_RANGE_FILES}.items():
        if base not in manifest:
            bad(f"check05: baseline for {rel} is not recorded in the boundary manifest")
        if head not in manifest:
            bad(f"check05: stage head for {rel} is not recorded in the boundary manifest")


def check06_no_head_endpoint() -> None:
    """No historical stage SCOPE may resolve against a moving endpoint.

    The runtime denylist is the deliberate exception: it must stay HEAD-relative or it would
    stop noticing runtime paths added after the stage. It can only ever reject, never admit.
    """
    for rel in CROSS_STAGE_FILES:
        body = read(ROOT / rel)
        for offender in re.findall(r'diff", "--name-only", [^)]*"HEAD"', body):
            if "RUNTIME_GUARD_ANCHOR" in offender:
                continue
            bad(f"check06: {rel} still compares a stage range to HEAD: {offender}")


def check06b_runtime_guard_scans_current_state() -> None:
    """Freezing the scope must not have frozen the denylist along with it."""
    for rel in CROSS_STAGE_FILES:
        body = read(ROOT / rel)
        if "RUNTIME_GUARD_ANCHOR" not in body:
            bad(f"check06b: {rel} has no current-state runtime guard")
            continue
        if not re.search(r'"--name-only", RUNTIME_GUARD_ANCHOR, "HEAD"', body):
            bad(f"check06b: {rel} runtime guard does not scan up to current HEAD")


def acceptance_body(body: str) -> str:
    """Source with rejection contexts stripped.

    A generic prefix named as something to REFUSE is the opposite of an allowlist, so lines that
    declare or assert its absence must not count as reintroducing it.
    """
    kept: list[str] = []
    in_forbidden_block = False
    for line in body.splitlines():
        if re.match(r"^\w*FORBIDDEN\w*\s*=\s*\($", line.strip()) or (
            "FORBIDDEN" in line and line.rstrip().endswith("(")
        ):
            in_forbidden_block = True
            continue
        if in_forbidden_block:
            if line.strip() == ")":
                in_forbidden_block = False
            continue
        if " not in " in line or "for generic in" in line:
            continue
        kept.append(line)
    return "\n".join(kept)


def check07_no_generic_docs_allowlist() -> None:
    for rel in CROSS_STAGE_FILES:
        if '"docs/",' in acceptance_body(read(ROOT / rel)):
            bad(f'check07: {rel} still carries the generic "docs/" allowlist')


def check08_no_generic_verifier_prefix() -> None:
    for rel in CROSS_STAGE_FILES:
        if '"scripts/verify_step66",' in acceptance_body(read(ROOT / rel)):
            bad(f"check08: {rel} still carries the generic verifier-prefix allowlist")


def check09_no_generic_test_prefix() -> None:
    for rel in CROSS_STAGE_FILES:
        if '"tests/test_step66",' in acceptance_body(read(ROOT / rel)):
            bad(f"check09: {rel} still carries the generic test-prefix allowlist")


def check10_twelve_cross_stage_files() -> None:
    if len(CROSS_STAGE_FILES) != 12:
        bad(f"check10: expected 12 cross-stage files, registered {len(CROSS_STAGE_FILES)}")
    evidence = read(EVIDENCE)
    for rel in CROSS_STAGE_FILES:
        if rel not in evidence:
            bad(f"check10: {rel} is not listed in the RM1 evidence inventory")


def check11_previously_omitted_file_disclosed() -> None:
    evidence = read(EVIDENCE)
    if PREVIOUSLY_OMITTED not in evidence:
        bad(f"check11: the previously omitted {PREVIOUSLY_OMITTED} is not disclosed")
    if "11" not in evidence or "12" not in evidence:
        bad("check11: the 11 -> 12 correction is not stated in the evidence record")


def check12_align1_positive_scope() -> None:
    body = read(ALIGN1_VERIFIER)
    registered = align1_registered_paths(body)
    if not registered:
        bad("check12: the ALIGN1 verifier has no ALIGN1_EXPECTED_PATHS registry")
        return
    if "check33_positive_exact_scope" not in body:
        bad("check12: the ALIGN1 verifier has no positive exact-scope check")
    changed = tuple(
        sorted(x for x in git("diff", "--name-only", CANONICAL_MAIN, RM1_COMMIT).splitlines() if x)
    )
    if changed and set(changed) - set(registered):
        bad(f"check12: unregistered ALIGN1 paths: {sorted(set(changed) - set(registered))}")


def check13_to_15_unregistered_probes_rejected() -> None:
    """A registered scope must not contain, or be satisfiable by, an unrelated probe path."""
    for number, key in (("check13", "docs"), ("check14", "verifier"), ("check15", "test")):
        probe = PROBES[key]
        for rel in STAGE_BOUNDARIES:
            registered = registered_paths(read(ROOT / rel))
            if probe in registered:
                bad(f"{number}: {rel} registered the unrelated probe path {probe}")
        align1 = align1_registered_paths(read(ALIGN1_VERIFIER))
        if probe in align1:
            bad(f"{number}: the ALIGN1 registry contains the unrelated probe path {probe}")


def check16_runtime_probe_rejected() -> None:
    probe = PROBES["runtime"]
    for rel in STAGE_BOUNDARIES:
        if probe in registered_paths(read(ROOT / rel)):
            bad(f"check16: {rel} registered a runtime probe path")
    if probe in align1_registered_paths(read(ALIGN1_VERIFIER)):
        bad("check16: the ALIGN1 registry contains a runtime probe path")


def check17_boundary_tampering_rejected() -> None:
    """Endpoints must be literal 40-character SHAs, not lookups that can be redirected."""
    for rel in CROSS_STAGE_FILES:
        body = read(ROOT / rel)
        for name in ("STAGE_BASELINE", "STAGE_HEAD", "MERGE_COMMIT", "RECORD_COMMIT"):
            for value in re.findall(rf"^{name}\s*=\s*(.+)$", body, re.M):
                literal = value.strip().rstrip(",").strip()
                if not re.fullmatch(r'"[0-9a-f]{40}"', literal):
                    bad(f"check17: {rel} {name} is not a literal full SHA: {literal}")
        if re.search(r"os\.environ.*(STAGE_|MERGE_COMMIT|RECORD_COMMIT)", body):
            bad(f"check17: {rel} allows a boundary to be overridden from the environment")


def check18_19_historical_provenance_intact() -> None:
    m1 = read(ROOT / "scripts" / "verify_step66sync1_m1_canonicalization.py")
    for needle in ("ANNOTATED", "ANNOTATION_MARKER", "git_blob_text"):
        if needle not in m1:
            bad(f"check18: the M1 append-only provenance guard lost {needle}")
    if "content above the annotation marker was modified" not in m1:
        bad("check18: the M1 guard no longer rejects edits above the annotation marker")
    if "must be additive" not in m1:
        bad("check19: the M1 guard no longer rejects deletions in annotated files")
    if "OPEN_PRODUCT_OWNER_DECISIONS" not in m1:
        bad("check19: the M1 guard no longer pins the historical open-decision count")


def check20_runtime_denylist_intact() -> None:
    for rel in CROSS_STAGE_FILES:
        body = read(ROOT / rel)
        if not any(f'"{prefix}"' in body for prefix in RUNTIME_PREFIXES):
            bad(f"check20: {rel} no longer names any runtime prefix in its denylist")


def check21_test_count_corrected() -> None:
    evidence = read(EVIDENCE)
    if "553" not in evidence:
        bad("check21: the verified 553-test baseline is not recorded in the RM1 evidence")
    align1 = read(ALIGN1_EVIDENCE)
    if "553" not in align1:
        bad("check21: the ALIGN1 evidence was not corrected to 553")


def check22_original_error_not_hidden() -> None:
    """The corrections must show what was wrong, not quietly overwrite it."""
    align1 = read(ALIGN1_EVIDENCE)
    if "552" not in align1:
        bad("check22: the ALIGN1 evidence hides the original 552 figure instead of correcting it")
    if "11" not in align1:
        bad("check22: the ALIGN1 evidence hides the original 11-file figure")
    evidence = read(EVIDENCE)
    for needle in ("R1-F01", "R1-F02", "R1-F03", "R1-F04", "R1-F05"):
        if needle not in evidence:
            bad(f"check22: the RM1 evidence does not address {needle}")


def check23_decisions_unchanged() -> None:
    binding = (
        "docs/contracts/66d-delivery-acceptance/"
        "step66d-delivery-decision-model-binding-decisions.md"
    )
    if git("diff", "--name-only", ALIGN1_COMMIT, "--", binding):
        bad("check23: 66D-D01..D04 substantive content was modified by this remediation")
    for rel in (
        "docs/contracts/66d-delivery-acceptance/step66d-canonical-terminology-registry.md",
        "docs/handoffs/66d-delivery-acceptance/step66d-canonical-conflict-supersession-matrix.md",
    ):
        if git("diff", "--name-only", ALIGN1_COMMIT, "--", rel):
            bad(f"check23: {rel} was modified by this remediation")


def check24_arch1_still_unauthorized() -> None:
    retry = read(
        ROOT / "docs" / "handoffs" / "66d-delivery-acceptance" / "step66d-arch1-retry-readiness.md"
    )
    if "NOT AUTHORIZED" not in retry:
        bad("check24: Step 66D-ARCH1 is no longer marked NOT AUTHORIZED")
    evidence = read(EVIDENCE)
    if "NOT AUTHORIZED" not in evidence:
        bad("check24: the RM1 evidence does not restate that Step 66D-ARCH1 is unauthorized")


def check25_merge_still_unauthorized() -> None:
    evidence = read(EVIDENCE)
    flat = re.sub(r"\s+", " ", evidence)
    if "MERGE AUTHORIZATION: NOT GRANTED" not in flat:
        bad("check25: the RM1 evidence does not restate that merge is not authorized")
    for claim in ("ready to merge", "independent review passed", "R2 passed"):
        if claim.lower() in flat.lower():
            bad(f"check25: the RM1 evidence claims {claim!r}, which is not true")


def check26_production_count_zero() -> None:
    evidence = read(EVIDENCE)
    if "production_executed_true_count: 0" not in evidence:
        bad("check26: the RM1 evidence does not record production_executed_true_count: 0")
    changed = [x for x in git("diff", "--name-only", CANONICAL_MAIN).splitlines() if x]
    offenders = [p for p in changed if p.startswith(RUNTIME_PREFIXES)]
    if offenders:
        bad(f"check26: runtime paths changed: {', '.join(sorted(offenders))}")


def main() -> int:
    check01_pr_baseline()
    check02_align1_commit_preserved()
    check03_single_remediation_commit()
    check04_fixed_boundaries_present()
    check05_manifest_agrees_with_constants()
    check06_no_head_endpoint()
    check06b_runtime_guard_scans_current_state()
    check07_no_generic_docs_allowlist()
    check08_no_generic_verifier_prefix()
    check09_no_generic_test_prefix()
    check10_twelve_cross_stage_files()
    check11_previously_omitted_file_disclosed()
    check12_align1_positive_scope()
    check13_to_15_unregistered_probes_rejected()
    check16_runtime_probe_rejected()
    check17_boundary_tampering_rejected()
    check18_19_historical_provenance_intact()
    check20_runtime_denylist_intact()
    check21_test_count_corrected()
    check22_original_error_not_hidden()
    check23_decisions_unchanged()
    check24_arch1_still_unauthorized()
    check25_merge_still_unauthorized()
    check26_production_count_zero()

    if FAILURES:
        for failure in dict.fromkeys(FAILURES):
            print(f"VERIFY FAILED: {failure}", file=sys.stderr)
        return 1
    print(MARKER)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
