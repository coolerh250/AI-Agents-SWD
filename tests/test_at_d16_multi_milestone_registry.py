"""AT-D16 -- multi-milestone live-guard changeset registry.

Offline by design: no container, no database, no network, no secret access. These tests do not
read the decision record's prose and take its word for anything. They exercise the mechanism:
each prerequisite is removed in turn and the exemption must be refused for that entry only, and
the live guard is run for real against this repository's actual AT-M2/AT-M3.1 history.

Decision authority (AT-D16 and everything it names) is read through a canonical Git ref, not the
working tree (AT-GOV-DECISION-DISCOVERY-REMEDIATION-1) -- and this branch's own AT-D16 has not yet
been merged to the real ``origin/main``. Every test below therefore runs under an autouse fixture
that points ``_canonical_commit`` at a fresh, parentless, unreferenced ("orphan") commit built from
this branch's own currently-committed tree, so AT-D16's real, current, final content is genuinely
canonical for the duration of each test -- proving the registry's OWN logic (this file's actual
concern), not decision-discovery's canonicality bootstrap (covered directly in
``test_at_d17_decision_discovery.py``). An orphan snapshot, not this branch's own multi-commit tip,
is used deliberately: AT-D16 was itself legitimately edited in place once, during its own
Remediation-1 round -- exercising the new immutability check against that real, already-reviewed,
already-superseded intermediate version would wrongly judge AT-D16's own final content as
"diverged". Nothing here fakes canonicality by patching ``_read`` with arbitrary text; PM-state
reads remain working-tree based by design (mirror-only, never mints authority) and are the only
thing the pre-existing ``redact`` fixture still fakes.
"""

from __future__ import annotations

import os
import pathlib
import re
import subprocess
import sys
import tempfile

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import successor_lifecycle as lifecycle  # noqa: E402

RECORD = "docs/decisions/at-d16-multi-milestone-changeset-registry.md"
SNAPSHOT = lifecycle.SUPERSESSION_RECORD

# A commit old enough to predate both AT-M2's and AT-M3.1's own reviewed work.
OLD_BASELINE = "c1db4cc"

PROTECTED_PREFIXES = ("apps/", "agents/", "shared/", "migrations/", "infra/")


def read(relpath: str) -> str:
    return (REPO / relpath).read_text(encoding="utf-8")


def _offenders(baseline: str = OLD_BASELINE) -> list[str]:
    changed = lifecycle.live_guard_changed_paths(baseline)
    return [p for p in changed if p.startswith(PROTECTED_PREFIXES)]


@pytest.fixture
def redact(monkeypatch):
    """Serve a doctored copy of the PM snapshot to the mechanism, leaving disk untouched. PM-state
    reads remain working-tree based by design (mirror-only, never mints authority) -- unlike
    decision-content reads, which are now canonical-Git-rooted (see ``as_canonical`` below).
    """
    real = lifecycle._read

    def install(target: str, transform):
        def fake(relpath: str) -> str:
            text = real(relpath)
            return transform(text) if relpath == target else text

        monkeypatch.setattr(lifecycle, "_read", fake)

    return install


@pytest.fixture
def as_canonical(monkeypatch):
    """Point ``_canonical_commit`` at an explicit commit -- the module's own documented test
    substitution seam. Every subsequent Git read still runs for real against that commit."""

    def install(commit: str) -> None:
        monkeypatch.setattr(lifecycle, "_canonical_commit", lambda: commit)

    return install


def build_orphan_snapshot(overrides: dict[str, str] | None = None) -> str:
    """A fresh, parentless, unreferenced commit -- this branch's currently-committed tree, with
    any given paths' content overridden -- so a doctored value is tested with no real, earlier,
    undoctored version of the same file anywhere in ITS history to conflict with the new
    immutability check. Never touches any ref; this repository's real history is unaffected.
    """
    head_tree = lifecycle._git("rev-parse", "HEAD^{tree}")
    with tempfile.TemporaryDirectory() as tmp:
        env = dict(os.environ, GIT_INDEX_FILE=str(pathlib.Path(tmp) / "index"))
        subprocess.run(
            ["git", "read-tree", head_tree],
            cwd=lifecycle.ROOT,
            check=True,
            env=env,
            capture_output=True,
        )
        for relpath, content in (overrides or {}).items():
            blob_sha = subprocess.run(
                ["git", "hash-object", "-w", "--stdin"],
                cwd=lifecycle.ROOT,
                input=content,
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=True,
                env=env,
            ).stdout.strip()
            subprocess.run(
                ["git", "update-index", "--add", "--cacheinfo", f"100644,{blob_sha},{relpath}"],
                cwd=lifecycle.ROOT,
                check=True,
                env=env,
                capture_output=True,
            )
        tree_sha = subprocess.run(
            ["git", "write-tree"],
            cwd=lifecycle.ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
            env=env,
        ).stdout.strip()
        return subprocess.run(
            ["git", "commit-tree", tree_sha, "-m", "test-only: orphan snapshot, never referenced"],
            cwd=lifecycle.ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
            env=env,
        ).stdout.strip()


@pytest.fixture(autouse=True)
def _simulate_canonical_main(as_canonical) -> None:
    as_canonical(build_orphan_snapshot())


# --- the record exists and is canonical ----------------------------------------------------------


def test_the_record_exists_and_is_binding() -> None:
    assert re.search(r"^AT-D16:\s+RESOLVED / BINDING\b", read(RECORD), re.M)


def test_the_canonical_snapshot_names_the_decision_and_the_record() -> None:
    snapshot = read(SNAPSHOT)
    assert lifecycle._field(snapshot, lifecycle.REGISTRY_DECISION_FIELD) == "AT-D16"
    assert lifecycle._field(snapshot, lifecycle.REGISTRY_RECORD_FIELD) == RECORD


def test_the_decision_leaks_no_internal_identifier() -> None:
    forbidden = re.compile(r"10\.0\.1\.(31|32)|aiagent-swd|itadmin|stpadmin", re.IGNORECASE)
    assert forbidden.search(read(RECORD)) is None


# --- 1/2: both milestones' reviewed content is recognised ------------------------------------------


def test_at_m2_reviewed_content_is_accepted() -> None:
    """AT-M2's own runtime paths, changed only inside its reviewed changeset, are exempt."""
    offenders = _offenders()
    assert offenders == [], f"AT-M2's own authorized work was not excluded: {offenders}"


def test_at_m3_1_reviewed_content_is_accepted() -> None:
    """The exact regression this record closes: AT-M3.1's reasoning/migration files are exempt.

    ``live_guard_changed_paths`` returns paths AFTER exemption, so a reviewed path is expected to
    be ABSENT from its output, not present. The raw two-commit diff is checked separately to prove
    these files were genuinely part of what changed, not merely untouched all along.
    """
    raw = lifecycle._git("diff", "--name-only", OLD_BASELINE, "HEAD").splitlines()
    at_m3_1_paths = [
        p
        for p in raw
        if p.startswith("shared/sdk/agent_reasoning/") or p.startswith("migrations/037_")
    ]
    assert at_m3_1_paths, "expected AT-M3.1's own files to appear in the raw diff at all"

    changed = lifecycle.live_guard_changed_paths(OLD_BASELINE)
    still_flagged = [p for p in at_m3_1_paths if p in changed]
    assert still_flagged == [], f"AT-M3.1's reviewed files were not exempted: {still_flagged}"
    assert _offenders() == []


# --- 3/4: content-version handling, not path membership --------------------------------------------


def test_a_path_reviewed_by_at_m2_then_legally_changed_by_at_m3_1_is_accepted() -> None:
    """docs/governance/AI_AGENTS_PM_STATE.md itself: touched by both AT-M2 and AT-M3.1 reconciliations.

    Its HEAD content does not match either recorded end (this session's own edits are ahead of
    both), but a file matching neither committee's reviewed content is exactly what SHOULD be
    caught -- this test proves the comparison is per-content-version, not merely "was this path
    ever touched by an authorized milestone", by checking the mechanism actually distinguishes the
    two recorded versions of the same path.
    """
    entries = {e["milestone"]: e["implementation_end"] for e in lifecycle.authorized_changesets()}
    assert entries["AT-M2"] != entries["AT-M3.1"]
    rel = "docs/governance/AI_AGENTS_PM_STATE.md"
    at_m2_blob = lifecycle._blob(rel, entries["AT-M2"])
    at_m3_1_blob = lifecycle._blob(rel, entries["AT-M3.1"])
    assert at_m2_blob != at_m3_1_blob, "the two milestones must have reviewed distinct content"


def test_a_path_changed_again_after_every_recognised_end_is_rejected(monkeypatch) -> None:
    """A path reviewed at BOTH AT-M2's and AT-M3.1's ends, then changed again, must still be caught.

    No real "future unauthorized commit" exists in this repository (HEAD is HEAD), so the
    post-review edit is simulated for one path: its diff/blob calls are faked while every other
    call -- including both real, currently-recognised registry entries -- goes through the real
    mechanism unchanged. This proves content-version matching, not path membership: the path is
    NOT special-cased out, it is compared against every recognised end and matches none of them.
    """
    fake_path = "shared/sdk/agent_reasoning/fake_future_edit.py"
    entries = {e["milestone"]: e["implementation_end"] for e in lifecycle.authorized_changesets()}
    recognised_ends = set(entries.values())

    real_git = lifecycle._git

    def fake_git(*args: str) -> str:
        if args[:2] == ("diff", "--name-only"):
            return fake_path
        return real_git(*args)

    monkeypatch.setattr(lifecycle, "_git", fake_git)

    real_blob = lifecycle._blob

    def fake_blob(path: str, commit: str) -> str | None:
        if path == fake_path:
            if commit == "HEAD":
                return "future-unauthorized-content\n"
            if commit in recognised_ends:
                return "reviewed-content-at-that-end\n"
        return real_blob(path, commit)

    monkeypatch.setattr(lifecycle, "_blob", fake_blob)

    changed = lifecycle.live_guard_changed_paths(OLD_BASELINE)
    assert fake_path in changed, "a path matching no recognised end must stay in the result"


# --- 5: brand-new unauthorized path -----------------------------------------------------------------


def test_a_new_unauthorized_protected_path_is_rejected() -> None:
    """A protected path with no history at all in any recognised end is never exempt."""
    entries = lifecycle.authorized_changesets()
    hypothetical = "shared/sdk/agent_reasoning/does_not_exist_anywhere.py"
    for entry in entries:
        assert lifecycle._blob(hypothetical, entry["implementation_end"]) is None
    legacy_end, _why = lifecycle.authorized_changeset_end()
    assert lifecycle._blob(hypothetical, legacy_end) is None


# --- 6/7/8: per-entry fail-closed authority checks --------------------------------------------------


def test_missing_authorization_decision_removes_that_entry(redact) -> None:
    redact(
        SNAPSHOT,
        lambda text: re.sub(r"AUTHORIZED_CHANGESET_2_AUTHORIZATION_ID:\s*\S+", "", text),
    )
    milestones = {e["milestone"] for e in lifecycle.authorized_changesets()}
    assert milestones == {"AT-M2"}


def test_non_binding_decision_removes_that_entry(as_canonical) -> None:
    doctored = read("docs/decisions/at-d14-at-m3-live-reasoning-authorization.md").replace(
        "AT-D14:                      RESOLVED / BINDING", ""
    )
    as_canonical(
        build_orphan_snapshot(
            {"docs/decisions/at-d14-at-m3-live-reasoning-authorization.md": doctored}
        )
    )
    milestones = {e["milestone"] for e in lifecycle.authorized_changesets()}
    assert milestones == {"AT-M2"}


def test_wrong_milestone_authority_removes_that_entry(redact) -> None:
    """The authorization record must actually be ABOUT the milestone the entry claims."""
    redact(
        SNAPSHOT,
        lambda text: text.replace(
            "AUTHORIZED_CHANGESET_2_AUTHORIZATION_ID:     AT-D14",
            "AUTHORIZED_CHANGESET_2_AUTHORIZATION_ID:     AT-D11",
        ),
    )
    milestones = {e["milestone"] for e in lifecycle.authorized_changesets()}
    assert milestones == {"AT-M2"}, "AT-D11 is about AT-M2, not AT-M3.1 -- must not satisfy entry 2"


def test_missing_merge_authority_removes_that_entry(redact) -> None:
    redact(
        SNAPSHOT,
        lambda text: re.sub(r"AUTHORIZED_CHANGESET_2_MERGE_ID:\s*\S+", "", text),
    )
    milestones = {e["milestone"] for e in lifecycle.authorized_changesets()}
    assert milestones == {"AT-M2"}


# --- 9/10: ancestry -----------------------------------------------------------------------------


def test_an_unreachable_implementation_end_removes_that_entry(redact) -> None:
    redact(
        SNAPSHOT,
        lambda text: re.sub(
            r"AUTHORIZED_CHANGESET_2_IMPLEMENTATION_END:\s*\S+",
            "AUTHORIZED_CHANGESET_2_IMPLEMENTATION_END:   0000000000000000000000000000000000000000",
            text,
        ),
    )
    milestones = {e["milestone"] for e in lifecycle.authorized_changesets()}
    assert milestones == {"AT-M2"}


def test_a_non_descendant_implementation_end_removes_that_entry(redact) -> None:
    """implementation_end must descend from ITS OWN entry's baseline -- an old, unrelated commit
    predating the baseline must be refused even though it is a real, HEAD-reachable commit."""
    redact(
        SNAPSHOT,
        lambda text: re.sub(
            r"AUTHORIZED_CHANGESET_2_IMPLEMENTATION_END:\s*\S+",
            "AUTHORIZED_CHANGESET_2_IMPLEMENTATION_END:   c1db4ccbfd88fa775e4761c932835896b9b980ed",
            text,
        ),
    )
    milestones = {e["milestone"] for e in lifecycle.authorized_changesets()}
    assert milestones == {"AT-M2"}, "an end predating its own baseline must fail closed"


# --- 11: a malformed entry never widens or invalidates another entry ------------------------------


def test_a_malformed_at_m3_1_entry_does_not_invalidate_or_widen_the_at_m2_entry(redact) -> None:
    redact(
        SNAPSHOT,
        lambda text: re.sub(r"AUTHORIZED_CHANGESET_2_BASELINE:\s*\S+", "", text),
    )
    entries = lifecycle.authorized_changesets()
    assert len(entries) == 1
    assert entries[0]["milestone"] == "AT-M2"
    assert entries[0]["implementation_end"] == "9c002e06029a682f586013671e8cb30ed1a475f4"


def test_no_registry_authorization_means_the_registry_is_empty_but_the_legacy_scalar_survives(
    redact,
) -> None:
    redact(
        SNAPSHOT,
        lambda text: "\n".join(
            line for line in text.splitlines() if lifecycle.REGISTRY_RECORD_FIELD not in line
        ),
    )
    assert lifecycle.authorized_changesets() == []
    legacy_end, _why = lifecycle.authorized_changeset_end()
    assert legacy_end == "9c002e06029a682f586013671e8cb30ed1a475f4"


# --- 12: bookkeeping does not force tip chasing -----------------------------------------------------


def test_bookkeeping_commits_after_implementation_end_require_no_registry_movement() -> None:
    """AT-M3.1's own canonical-merge and PM-state-reconciliation commits stay outside its end."""
    entries = {e["milestone"]: e["implementation_end"] for e in lifecycle.authorized_changesets()}
    at_m3_1_end = entries["AT-M3.1"]
    assert at_m3_1_end == "1ba197a91867e77a9fa2256289b2766317b51b41"
    for bookkeeping_commit in (
        "1e9fe3b445e1ddaefe0c4ed0bdc5be8af4d0ad96",  # AT-D15 docs commit
        "5a04ec1c67453c4d90b525e94402b9515fbec0bf",  # PM-state reconciliation commit
    ):
        assert lifecycle.is_ancestor(at_m3_1_end, bookkeeping_commit)
        assert at_m3_1_end != bookkeeping_commit


def test_at_m2_entry_end_also_predates_its_own_bookkeeping() -> None:
    entries = {e["milestone"]: e["implementation_end"] for e in lifecycle.authorized_changesets()}
    assert entries["AT-M2"] == "9c002e06029a682f586013671e8cb30ed1a475f4"
    assert lifecycle.is_ancestor(entries["AT-M2"], "0986c895e85b426f3ca56239ad7cdb39288a8546")


# --- 13: an unknown future milestone gets nothing ----------------------------------------------------


def test_unknown_at_m3_2_content_receives_no_exemption(redact) -> None:
    """Simulate a hypothetical AT-M3.2 entry with no corresponding authorization record on disk."""
    redact(
        SNAPSHOT,
        lambda text: text + "\nAUTHORIZED_CHANGESET_3_MILESTONE:            AT-M3.2\n"
        "AUTHORIZED_CHANGESET_3_AUTHORIZATION_ID:     AT-D99\n"
        "AUTHORIZED_CHANGESET_3_MERGE_ID:             AT-D99\n"
        "AUTHORIZED_CHANGESET_3_BASELINE:             1e9fe3b445e1ddaefe0c4ed0bdc5be8af4d0ad96\n"
        "AUTHORIZED_CHANGESET_3_IMPLEMENTATION_END:   5a04ec1c67453c4d90b525e94402b9515fbec0bf\n"
        "AUTHORIZED_CHANGESET_REGISTRY:          3\n",
    )
    milestones = {e["milestone"] for e in lifecycle.authorized_changesets()}
    assert "AT-M3.2" not in milestones, "an unresolvable decision id must never seat an entry"


# --- 14: the live guard still resolves through current HEAD, never a boundary ----------------------


def test_live_guard_still_resolves_through_head_not_a_boundary() -> None:
    assert lifecycle.live_guard_end() == "HEAD"
    milestone, boundary, _why = lifecycle.authorized_successor()
    assert milestone == "AT-M2"
    assert lifecycle.is_ancestor(boundary, "HEAD")
    # the historical (capped) path and the live (uncapped) path must still diverge, exactly as
    # AT-D12's own probe already established -- this record must not have changed that.
    historical_end, _why = lifecycle.window_end(OLD_BASELINE)
    assert historical_end == boundary
    assert lifecycle.live_guard_end() == "HEAD"


def test_the_registry_is_additive_registering_at_m3_1_did_not_move_at_m2s_field() -> None:
    snapshot = read(SNAPSHOT)
    assert (
        lifecycle._field(snapshot, lifecycle.AUTHORIZED_CHANGESET_END_FIELD)
        == "9c002e06029a682f586013671e8cb30ed1a475f4"
    )


# --- AT-D16-REMEDIATION-1: exact provenance binding, not ancestry-plausible substitution -----------
#
# Multi-Milestone Governance Validation 1 found the first cut trusted the PM snapshot's field
# values on their own (an ancestry-valid substitute commit passed as readily as the real reviewed
# one) and decided a decision's authority over a milestone by searching that decision's prose for
# the milestone's name (so AT-D14's incidental "AT-M2" mentions satisfied an AT-M2 check). These
# probes reproduce those exact attacks against the fix: AT-D16's own table is now the sole
# canonical source of values and of decision authority, and the PM snapshot must mirror it exactly.

AT_D16_RECORD = RECORD


def _milestones(entries: list[dict[str, str]]) -> set[str]:
    return {e["milestone"] for e in entries}


def test_a_swapped_but_ancestry_valid_at_m3_1_end_is_rejected(redact) -> None:
    """Probe A: 1ba197a (the real Validated_candidate) -> 1e9fe3b (AT-D15's own docs commit).

    1e9fe3b is a real commit, a descendant of the AT-M3.1 baseline, and an ancestor of HEAD -- it
    passes every ancestry check the first cut relied on. It must still be rejected because it does
    not match AT-D16's own canonical value for AT-M3.1's implementation_end.
    """
    redact(
        SNAPSHOT,
        lambda text: re.sub(
            r"AUTHORIZED_CHANGESET_2_IMPLEMENTATION_END:\s*\S+",
            "AUTHORIZED_CHANGESET_2_IMPLEMENTATION_END:   1e9fe3b445e1ddaefe0c4ed0bdc5be8af4d0ad96",
            text,
        ),
    )
    assert _milestones(lifecycle.authorized_changesets()) == {"AT-M2"}


def test_a_swapped_but_ancestry_valid_at_m2_end_is_rejected(redact) -> None:
    """Probe B: 9c002e0 (AT-D13's pinned value) -> 0986c89 (AT-M2's later canonical-merge tip).

    AT-D13 section 5 explicitly states the legacy scalar "stays pinned at 9c002e0" -- 0986c89 is a
    real, later, ancestry-valid commit that is exactly the kind of substitute AT-D13 forbids.
    """
    redact(
        SNAPSHOT,
        lambda text: re.sub(
            r"AUTHORIZED_CHANGESET_1_IMPLEMENTATION_END:\s*\S+",
            "AUTHORIZED_CHANGESET_1_IMPLEMENTATION_END:   0986c895e85b426f3ca56239ad7cdb39288a8546",
            text,
        ),
    )
    assert _milestones(lifecycle.authorized_changesets()) == {"AT-M3.1"}


def test_a_swapped_but_ancestry_valid_baseline_is_rejected(redact) -> None:
    """Probe C: 44cdd6f (AT-D14's own Canonical_main_at_decision) -> an arbitrary earlier ancestor."""
    redact(
        SNAPSHOT,
        lambda text: re.sub(
            r"AUTHORIZED_CHANGESET_2_BASELINE:\s*\S+",
            "AUTHORIZED_CHANGESET_2_BASELINE:             229ac56",
            text,
        ),
    )
    assert _milestones(lifecycle.authorized_changesets()) == {"AT-M2"}


def test_at_d14_cannot_be_reused_as_at_m2_authority(as_canonical, redact) -> None:
    """Probe D: the exact false-positive Validation 1 demonstrated concretely.

    AT-D14's prose contains the literal substring "AT-M2" four times without authorizing it. Even
    when BOTH the PM mirror and AT-D16's own canonical table are mutated to claim AT-D14 authorizes
    AT-M2's entry, the authority check must still refuse: AT-D16's authority index lists AT-D14
    against AT-M3.1 only, and prose is never consulted.

    AT-D16's own table is mutated by building a fresh, self-consistent orphan snapshot (never a
    later commit layered on top of the real one) -- the new immutability check would otherwise
    correctly treat an in-place edit to an already-canonical AT-D16 as a divergence and void the
    WHOLE decision, which is a different (and already separately covered) property than this
    probe's target: that a decision's own authority index is exact, not a mention of a name.
    """
    assert "AT-M2" in read("docs/decisions/at-d14-at-m3-live-reasoning-authorization.md")
    doctored_at_d16 = read(AT_D16_RECORD).replace(
        "AT_D16_CHANGESET_1_AUTHORIZATION_ID:     AT-D11",
        "AT_D16_CHANGESET_1_AUTHORIZATION_ID:     AT-D14",
    )
    as_canonical(build_orphan_snapshot({AT_D16_RECORD: doctored_at_d16}))
    redact(
        SNAPSHOT,
        lambda text: text.replace(
            "AUTHORIZED_CHANGESET_1_AUTHORIZATION_ID:     AT-D11",
            "AUTHORIZED_CHANGESET_1_AUTHORIZATION_ID:     AT-D14",
        ),
    )
    assert _milestones(lifecycle.authorized_changesets()) == {"AT-M3.1"}


def test_at_d13_cannot_be_reused_as_at_m3_1_merge_authority() -> None:
    """The reverse direction: AT-D13 is about AT-M2's merge, never AT-M3.1's."""
    assert not lifecycle._decision_authorizes("AT-D13", "AT-M3.1", "ACCEPTANCE_MERGE")


def test_unknown_decision_id_fails_closed() -> None:
    assert lifecycle._decision_record_path("AT-D99") == ""
    assert not lifecycle._decision_authorizes("AT-D99", "AT-M2", "IMPLEMENTATION")


def _inject_pm_entry(
    text: str, index: int, milestone: str, auth_id: str, merge_id: str, baseline: str, end: str
) -> str:
    text = re.sub(r"(AUTHORIZED_CHANGESET_REGISTRY:\s*)\d+", rf"\g<1>{index}", text)
    return text + (
        f"\nAUTHORIZED_CHANGESET_{index}_MILESTONE:            {milestone}\n"
        f"AUTHORIZED_CHANGESET_{index}_AUTHORIZATION_ID:     {auth_id}\n"
        f"AUTHORIZED_CHANGESET_{index}_MERGE_ID:             {merge_id}\n"
        f"AUTHORIZED_CHANGESET_{index}_BASELINE:             {baseline}\n"
        f"AUTHORIZED_CHANGESET_{index}_IMPLEMENTATION_END:   {end}\n"
    )


def test_duplicate_conflicting_at_m2_entry_invalidates_at_m2_not_at_m3_1(redact) -> None:
    """Probe E: a genuine entry plus a conflicting one for the SAME milestone -- no union, no pick."""
    redact(
        SNAPSHOT,
        lambda text: _inject_pm_entry(
            text,
            3,
            "AT-M2",
            "AT-D11",
            "AT-D13",
            "192ebb74ba600f7a53ddf5967a7254a1f7a72fb8",
            "0986c895e85b426f3ca56239ad7cdb39288a8546",  # conflicts with entry 1's real end
        ),
    )
    assert _milestones(lifecycle.authorized_changesets()) == {"AT-M3.1"}


def test_duplicate_conflicting_at_m3_1_entry_invalidates_at_m3_1_not_at_m2(redact) -> None:
    """Probe F: same as E, mirrored onto AT-M3.1."""
    redact(
        SNAPSHOT,
        lambda text: _inject_pm_entry(
            text,
            3,
            "AT-M3.1",
            "AT-D14",
            "AT-D15",
            "44cdd6f14333915932428d190b0a3e117d033b6d",
            "1e9fe3b445e1ddaefe0c4ed0bdc5be8af4d0ad96",  # conflicts with entry 2's real end
        ),
    )
    assert _milestones(lifecycle.authorized_changesets()) == {"AT-M2"}


def test_an_identical_duplicate_entry_collapses_harmlessly(redact) -> None:
    """A milestone named twice with IDENTICAL values is not a conflict -- it still validates."""
    redact(
        SNAPSHOT,
        lambda text: _inject_pm_entry(
            text,
            3,
            "AT-M2",
            "AT-D11",
            "AT-D13",
            "192ebb74ba600f7a53ddf5967a7254a1f7a72fb8",
            "9c002e06029a682f586013671e8cb30ed1a475f4",  # identical to entry 1
        ),
    )
    assert _milestones(lifecycle.authorized_changesets()) == {"AT-M2", "AT-M3.1"}


def test_extra_unexpected_milestone_with_no_at_d16_authority_is_rejected(redact) -> None:
    """Probe G: a well-formed PM entry with no corresponding AT-D16 canonical entry at all."""
    redact(
        SNAPSHOT,
        lambda text: _inject_pm_entry(
            text,
            3,
            "AT-M3.2",
            "AT-D99",
            "AT-D99",
            "1e9fe3b445e1ddaefe0c4ed0bdc5be8af4d0ad96",
            "5a04ec1c67453c4d90b525e94402b9515fbec0bf",
        ),
    )
    assert _milestones(lifecycle.authorized_changesets()) == {"AT-M2", "AT-M3.1"}


def test_legacy_scalar_mismatch_invalidates_the_at_m2_registry_entry_only(redact) -> None:
    """Section 6: the registry's AT-M2 entry additionally requires the legacy scalar to match
    its canonical end exactly. A mismatch invalidates the registry entry -- the legacy scalar
    mechanism itself (``authorized_changeset_end``) stays completely independent and unaffected.
    """
    stale = "192ebb74ba600f7a53ddf5967a7254a1f7a72fb8"
    redact(
        SNAPSHOT,
        lambda text: re.sub(
            rf"{lifecycle.AUTHORIZED_CHANGESET_END_FIELD}:\s*\S+",
            f"{lifecycle.AUTHORIZED_CHANGESET_END_FIELD}: {stale}",
            text,
        ),
    )
    assert _milestones(lifecycle.authorized_changesets()) == {"AT-M3.1"}
    end, _why = lifecycle.authorized_changeset_end()
    assert (
        end == stale
    ), "authorized_changeset_end() must reflect the (mutated) scalar independently"


def test_positive_control_malforming_at_d16s_own_canonical_entry_restores_offenders(
    as_canonical,
) -> None:
    """The ultimate root of trust: corrupt AT-D16's OWN table, not just the PM mirror.

    Confirms the current green state is caused by AT-D16's genuine canonical authority, not by an
    accidentally weakened denylist -- mutating the PM mirror alone is not sufficient to prove this,
    since AT-D16 is supposed to be the thing that actually matters. A fresh, self-consistent orphan
    snapshot is used for the same reason as the AT-D14-reuse probe above: the new immutability
    check is a different, already-covered property from this positive control's target.
    """
    doctored_at_d16 = read(AT_D16_RECORD).replace(
        "AT_D16_CHANGESET_2_BASELINE:             44cdd6f14333915932428d190b0a3e117d033b6d", ""
    )
    as_canonical(build_orphan_snapshot({AT_D16_RECORD: doctored_at_d16}))
    assert _milestones(lifecycle.authorized_changesets()) == {"AT-M2"}
    changed = lifecycle.live_guard_changed_paths(OLD_BASELINE)
    at_m3_1_offenders = [
        p
        for p in changed
        if p.startswith("shared/sdk/agent_reasoning/") or p.startswith("migrations/037_")
    ]
    assert (
        at_m3_1_offenders
    ), "AT-M3.1's files must reappear as offenders when its authority is gone"
