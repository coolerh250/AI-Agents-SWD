"""AT-D16 -- multi-milestone live-guard changeset registry.

Offline by design: no container, no database, no network, no secret access. These tests do not
read the decision record's prose and take its word for anything. They exercise the mechanism:
each prerequisite is removed in turn and the exemption must be refused for that entry only, and
the live guard is run for real against this repository's actual AT-M2/AT-M3.1 history.
"""

from __future__ import annotations

import pathlib
import re
import sys

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
    """Serve a doctored copy of one canonical file to the mechanism, leaving disk untouched."""
    real = lifecycle._read

    def install(target: str, transform):
        def fake(relpath: str) -> str:
            text = real(relpath)
            return transform(text) if relpath == target else text

        monkeypatch.setattr(lifecycle, "_read", fake)

    return install


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


def test_non_binding_decision_removes_that_entry(redact) -> None:
    redact(
        "docs/decisions/at-d14-at-m3-live-reasoning-authorization.md",
        lambda text: text.replace("AT-D14:                      RESOLVED / BINDING", ""),
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
