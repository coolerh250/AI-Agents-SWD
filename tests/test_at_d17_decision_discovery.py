"""AT-D17 -- data-driven decision discovery and future authority bootstrap.

AT-GOV-DECISION-DISCOVERY-VALIDATION-1 found the first cut of this trusted the working tree for
decision authority: an untracked file, or one that existed only on a feature branch never merged
to canonical main, was already fully binding merely by sitting on disk in the right shape, and a
later in-place edit to an already-accepted decision took effect immediately. AT-GOV-DECISION-
DISCOVERY-REMEDIATION-1 closes both: every decision-authority read is rooted at a canonical Git
ref (``CANONICAL_DECISION_REF``) and bound to the earliest canonical commit its authority-bearing
fields have held unchanged since.

Two kinds of proof appear below. Real-repository tests exercise this actual repository's actual
history (AT-D11-AT-D17, real commit SHAs) with `_canonical_commit` pointed either at the real,
unmodified ``origin/main`` (proving AT-D16/AT-D17 are correctly NOT yet canonically authoritative)
or, via monkeypatch, at an orphan snapshot of this branch's own real tree (proving the same real
data becomes fully authoritative the moment it IS canonical). Fixture tests use ``canonical_git_repo``
-- a real, isolated, disposable Git repository -- to exercise scenarios no real commit can provide: synthetic
future decisions, a decision mutated after acceptance, and a full self-registration chain. Every
fixture commit is real; nothing here fakes canonicality by patching ``_read`` with arbitrary text,
and no file is written to or deleted from this actual repository at any point.
"""

from __future__ import annotations

import inspect
import pathlib
import re
import subprocess
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import successor_lifecycle as lifecycle  # noqa: E402

SNAPSHOT = lifecycle.SUPERSESSION_RECORD
AT_D17_RECORD = "docs/decisions/at-d17-decision-discovery-bootstrap.md"
AT_D16_RECORD = "docs/decisions/at-d16-multi-milestone-changeset-registry.md"


def read(relpath: str) -> str:
    return (REPO / relpath).read_text(encoding="utf-8")


def orphan_snapshot_of_head() -> str:
    """A fresh, parentless, unreferenced commit with exactly this branch's current committed
    tree -- simulates AT-D16/AT-D17 landing on canonical main via one clean commit, matching how
    they will actually arrive there (this branch's iterative, multi-commit history is a build
    artifact of developing them, not a real prior canonical version of either). Never touches any
    ref; the real repository's history is completely unaffected.
    """
    tree = lifecycle._git("rev-parse", "HEAD^{tree}")
    result = subprocess.run(
        [
            "git",
            "commit-tree",
            tree,
            "-m",
            "test-only: orphan snapshot, never referenced by any branch",
        ],
        cwd=lifecycle.ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    return result.stdout.strip()


@pytest.fixture
def as_canonical(monkeypatch):
    """Point ``_canonical_commit`` at an explicit commit -- the one seam the module itself
    documents as the test substitution point. Every subsequent Git read (ls-tree, show, log)
    still runs for real against that commit; only "which commit counts as canonical" is chosen
    by the test.
    """

    def install(commit: str) -> None:
        monkeypatch.setattr(lifecycle, "_canonical_commit", lambda: commit)

    return install


@pytest.fixture
def fake_pm_snapshot(monkeypatch):
    """PM-state reads remain working-tree based by design (mirror-only, never mints authority --
    see ``test_pm_mirror_corruption_cannot_inject_a_path`` and the AT-D16 suite's own coverage).
    This fakes only that one path, leaving every decision-authority read genuinely Git-rooted.
    """
    real = lifecycle._read

    def install(transform) -> None:
        def fake(relpath: str) -> str:
            text = real(relpath)
            return transform(text) if relpath == SNAPSHOT else text

        monkeypatch.setattr(lifecycle, "_read", fake)

    return install


def _at_d18_text(authorizes_implementation: str = "", authorizes_acceptance: str = "") -> str:
    lines = ["AT-D18:                      RESOLVED / BINDING"]
    if authorizes_implementation:
        lines.append(f"AUTHORIZES_IMPLEMENTATION: {authorizes_implementation}")
    if authorizes_acceptance:
        lines.append(f"AUTHORIZES_ACCEPTANCE_MERGE: {authorizes_acceptance}")
    return "\n".join(lines) + "\n"


# --- the record exists and is well-formed ----------------------------------------------------------


def test_the_record_exists_and_is_binding() -> None:
    assert re.search(r"^AT-D17:\s+RESOLVED / BINDING\b", read(AT_D17_RECORD), re.M)


def test_the_decision_leaks_no_internal_identifier() -> None:
    forbidden = re.compile(r"10\.0\.1\.(31|32)|aiagent-swd|itadmin|stpadmin", re.IGNORECASE)
    assert forbidden.search(read(AT_D17_RECORD)) is None


def test_no_python_literal_enumerates_decision_ids() -> None:
    """The defect this record closes: a fixed dict/list of every known decision id."""
    module = (REPO / "scripts" / "successor_lifecycle.py").read_text(encoding="utf-8")
    assert "_DECISION_RECORD_PATHS" not in module
    for forbidden_id in ("AT-D11", "AT-D13", "AT-D14", "AT-D15", "AT-D17", "AT-D18"):
        assert f'"{forbidden_id}"' not in module, forbidden_id


def test_no_authority_function_reads_the_working_tree() -> None:
    """The defect Validation 1 found: every one of these used to read through ``_read`` (a plain
    filesystem read with no Git-commit binding). Each must now read only through ``_blob`` against
    an explicit commit -- proven directly against each function's own source, not by inference.
    """
    for fn in (
        lifecycle._discovered_decision_paths,
        lifecycle._decision_record_path,
        lifecycle._binding_frozen_text,
        lifecycle._decision_is_binding,
        lifecycle._grandfathered_authorizes,
        lifecycle._typed_authorizes,
        lifecycle._decision_changeset_entries,
        lifecycle._canonical_changesets,
        lifecycle._frozen_binding_commit,
    ):
        source = inspect.getsource(fn)
        assert "_read(" not in source, fn.__name__


def test_canonical_ref_resolution_never_falls_back_to_head_or_disk() -> None:
    source = inspect.getsource(lifecycle._canonical_ref_commit)
    assert '"HEAD"' not in source
    assert lifecycle.CANONICAL_DECISION_REF != "HEAD"


# --- real repository: pre-canonical state is correctly dark -----------------------------------------


def test_at_d17_not_yet_canonically_authoritative_on_real_origin_main() -> None:
    """AT-D17 is real, on disk, RESOLVED / BINDING -- and lives only on this feature branch, never
    merged to the real ``origin/main``. That must not be a test failure (AT-D17-remediation
    section 15): it is the fail-closed behaviour this whole record exists to guarantee.
    """
    assert (
        lifecycle._canonical_ref_commit("origin/main") == "5a04ec1c67453c4d90b525e94402b9515fbec0bf"
    )
    assert not lifecycle._decision_is_binding("AT-D17")
    assert not lifecycle._decision_authorizes(
        "AT-D17", "AT-GOV-DECISION-DISCOVERY-1", "IMPLEMENTATION"
    )


def test_at_d16_not_yet_canonically_authoritative_on_real_origin_main() -> None:
    assert not lifecycle._decision_is_binding("AT-D16")
    assert lifecycle.authorized_changesets() == []


def test_an_unresolvable_canonical_ref_yields_no_authority_anywhere(monkeypatch) -> None:
    monkeypatch.setattr(lifecycle, "CANONICAL_DECISION_REF", "origin/this-ref-does-not-exist")
    assert lifecycle._canonical_commit() == ""
    assert lifecycle._discovered_decision_paths() == {}
    assert not lifecycle._decision_is_binding("AT-D11")
    assert lifecycle.authorized_changesets() == []


# --- real repository: the same real data becomes authoritative once genuinely canonical -------------


def test_this_branchs_real_data_is_fully_authoritative_once_simulated_canonical(
    as_canonical,
) -> None:
    """Real AT-D11/13/14/15/16/17, real commit SHAs, real AT-M2/AT-M3.1 provenance -- proven end
    to end using an orphan snapshot of this branch's own actual tree as the (simulated) canonical
    commit. Nothing here is faked text; only which commit counts as canonical is test-controlled.

    An orphan snapshot, not this branch's own multi-commit tip, is used deliberately: this
    branch's real history contains one legitimate in-place edit to AT-D16 itself (its own
    Remediation-1 round, reviewed and accepted at the time) -- exercising immutability against
    that incidental, already-superseded intermediate version would wrongly judge AT-D16's own,
    real, final content as "diverged". A single clean commit is also the more faithful simulation
    of how these records will actually land on canonical main: as one commit, not as this
    branch's own iterative development history.
    """
    as_canonical(orphan_snapshot_of_head())

    assert lifecycle._decision_record_path("AT-D11") == "docs/decisions/at-m2-authorization.md"
    assert lifecycle._decision_record_path("AT-D16") == AT_D16_RECORD
    assert lifecycle._decision_record_path("AT-D17") == AT_D17_RECORD
    assert lifecycle._decision_is_binding("AT-D17")
    assert lifecycle._decision_authorizes("AT-D17", "AT-GOV-DECISION-DISCOVERY-1", "IMPLEMENTATION")
    assert not lifecycle._decision_authorizes("AT-D17", "AT-M2", "IMPLEMENTATION")

    entries = {e["milestone"]: e["implementation_end"] for e in lifecycle.authorized_changesets()}
    assert entries["AT-M2"] == "9c002e06029a682f586013671e8cb30ed1a475f4"
    assert entries["AT-M3.1"] == "1ba197a91867e77a9fa2256289b2766317b51b41"


def test_pm_mirror_corruption_cannot_inject_a_path(as_canonical, fake_pm_snapshot) -> None:
    """Even against genuinely canonical AT-D16, a corrupted PM registry-record field is only ever
    compared for equality -- never dereferenced as a path.
    """
    as_canonical(orphan_snapshot_of_head())
    fake_pm_snapshot(
        lambda text: re.sub(
            r"AUTHORIZED_CHANGESET_REGISTRY_RECORD:\s*\S+",
            "AUTHORIZED_CHANGESET_REGISTRY_RECORD:   ../../../etc/passwd",
            text,
        )
    )
    assert lifecycle.authorized_changesets() == []


# --- fixture: bounded, content-driven, path-safe discovery ------------------------------------------


def test_discovery_is_bounded_to_exactly_docs_decisions(canonical_git_repo, as_canonical) -> None:
    repo = canonical_git_repo
    repo.write_decision("at-d18.md", _at_d18_text())
    repo.write("docs/decisions/nested/at-d19.md", "AT-D19: RESOLVED / BINDING\n")  # not discovered
    repo.write("elsewhere/at-d20.md", "AT-D20: RESOLVED / BINDING\n")  # not discovered
    commit = repo.commit("seed")
    as_canonical(commit)

    discovered = lifecycle._discovered_decision_paths()
    assert discovered == {"AT-D18": "docs/decisions/at-d18.md"}


def test_symlinked_decision_entry_is_not_discovered(canonical_git_repo, as_canonical) -> None:
    """A real Git symlink TREE ENTRY (mode 120000), not an OS-level symlink -- portable to a host
    with no symlink privilege, and exercises exactly what discovery must reject.
    """
    repo = canonical_git_repo
    repo.write_decision("at-d18-real.md", _at_d18_text())
    real_commit = repo.commit("real decision")
    repo.add_symlink_entry("at-d18-linked.md", "../../outside.md")
    linked_commit = repo.head()
    as_canonical(linked_commit)

    discovered = lifecycle._discovered_decision_paths()
    assert discovered == {"AT-D18": "docs/decisions/at-d18-real.md"}
    assert "at-d18-linked.md" not in " ".join(discovered.values())
    assert lifecycle.is_ancestor(real_commit, linked_commit)


@pytest.mark.parametrize(
    "malicious_id",
    [
        "../../etc/passwd",
        "/etc/passwd",
        "AT-D11/../../secrets.md",
        "AT-D11\x00.md",
        "at-d16-multi-milestone-changeset-registry.md",
        "docs/decisions/at-d16-multi-milestone-changeset-registry.md",
        "",
    ],
)
def test_arbitrary_or_malformed_ids_never_resolve_to_a_path(malicious_id: str) -> None:
    assert lifecycle._decision_record_path(malicious_id) == ""


# --- fixture: identity / duplicate handling ----------------------------------------------------------


def test_duplicate_identity_across_two_files_is_rejected(canonical_git_repo, as_canonical) -> None:
    repo = canonical_git_repo
    repo.write_decision("at-d18-a.md", _at_d18_text())
    repo.write_decision("at-d18-b.md", _at_d18_text())
    as_canonical(repo.commit("duplicate identity"))

    assert lifecycle._decision_record_path("AT-D18") == ""
    assert not lifecycle._decision_is_binding("AT-D18")


def test_one_file_claiming_two_ids_is_rejected_for_both(canonical_git_repo, as_canonical) -> None:
    repo = canonical_git_repo
    repo.write_decision("at-d18-and-19.md", _at_d18_text() + "AT-D19: RESOLVED / BINDING\n")
    repo.write_decision("at-d20.md", "AT-D20: RESOLVED / BINDING\n")
    as_canonical(repo.commit("ambiguous file"))

    assert lifecycle._decision_record_path("AT-D18") == ""
    assert lifecycle._decision_record_path("AT-D19") == ""
    assert lifecycle._decision_record_path("AT-D20") == "docs/decisions/at-d20.md"


def test_non_binding_decision_is_discovered_but_not_binding(
    canonical_git_repo, as_canonical
) -> None:
    repo = canonical_git_repo
    repo.write_decision("at-d18.md", "AT-D18: PROPOSED / UNDER_REVIEW\n")
    as_canonical(repo.commit("proposed, not yet binding"))

    assert lifecycle._decision_record_path("AT-D18") == "docs/decisions/at-d18.md"
    assert not lifecycle._decision_is_binding("AT-D18")


def test_unknown_decision_id_fails_closed(canonical_git_repo, as_canonical) -> None:
    repo = canonical_git_repo
    repo.write_decision("at-d18.md", _at_d18_text())
    as_canonical(repo.commit("seed"))

    assert lifecycle._decision_record_path("AT-D99") == ""
    assert not lifecycle._decision_authorizes("AT-D99", "AT-M2", "IMPLEMENTATION")


# --- fixture: synthetic future decisions require zero mechanism edits -------------------------------


def test_synthetic_at_d18_at_d19_at_d123_discovered_only_once_canonical(
    canonical_git_repo, as_canonical
) -> None:
    repo = canonical_git_repo
    repo.write_decision(
        "at-d18.md", _at_d18_text(authorizes_implementation="AT-GOV-FUTURE-SLICE-1")
    )
    repo.write_decision("at-d19.md", "AT-D19:                      RESOLVED / BINDING\n")
    repo.write_decision("at-d123.md", "AT-D123:                     RESOLVED / BINDING\n")
    branch_local_commit = repo.commit("branch-local: not yet canonical")

    # Before canonical inclusion: this exact commit exists, but is simply never pointed at.
    as_canonical("")
    assert lifecycle._discovered_decision_paths() == {}
    assert not lifecycle._decision_is_binding("AT-D18")

    # After canonical inclusion: the very same commit, now pointed at -- no code change anywhere.
    as_canonical(branch_local_commit)
    assert lifecycle._decision_is_binding("AT-D18")
    assert lifecycle._decision_is_binding("AT-D19")
    assert lifecycle._decision_is_binding("AT-D123")
    assert lifecycle._decision_authorizes("AT-D18", "AT-GOV-FUTURE-SLICE-1", "IMPLEMENTATION")


def test_typed_slots_are_exact_and_symmetric(canonical_git_repo, as_canonical) -> None:
    repo = canonical_git_repo
    repo.write_decision(
        "at-d18.md", _at_d18_text(authorizes_implementation="AT-GOV-FUTURE-SLICE-1")
    )
    repo.write_decision(
        "at-d19.md",
        _at_d18_text(authorizes_acceptance="AT-GOV-FUTURE-SLICE-1").replace("AT-D18", "AT-D19"),
    )
    as_canonical(repo.commit("seed"))

    assert lifecycle._decision_authorizes("AT-D18", "AT-GOV-FUTURE-SLICE-1", "IMPLEMENTATION")
    assert not lifecycle._decision_authorizes("AT-D18", "AT-GOV-FUTURE-SLICE-1", "ACCEPTANCE_MERGE")
    assert lifecycle._decision_authorizes("AT-D19", "AT-GOV-FUTURE-SLICE-1", "ACCEPTANCE_MERGE")
    assert not lifecycle._decision_authorizes("AT-D19", "AT-GOV-FUTURE-SLICE-1", "IMPLEMENTATION")


def test_wrong_milestone_rejected(canonical_git_repo, as_canonical) -> None:
    repo = canonical_git_repo
    repo.write_decision(
        "at-d18.md", _at_d18_text(authorizes_implementation="AT-GOV-FUTURE-SLICE-1")
    )
    as_canonical(repo.commit("seed"))
    assert not lifecycle._decision_authorizes("AT-D18", "AT-GOV-SOME-OTHER-SLICE", "IMPLEMENTATION")


def test_malformed_authority_field_rejected(canonical_git_repo, as_canonical) -> None:
    repo = canonical_git_repo
    repo.write_decision(
        "at-d18.md", "AT-D18:                      RESOLVED / BINDING\nAUTHORIZES_IMPLEMENTATION:\n"
    )
    as_canonical(repo.commit("seed"))
    assert not lifecycle._decision_authorizes("AT-D18", "", "IMPLEMENTATION")
    assert not lifecycle._decision_authorizes("AT-D18", "AT-GOV-FUTURE-SLICE-1", "IMPLEMENTATION")


# --- fixture: AT-D16 grandfather stays frozen, sourced canonically too ------------------------------


def test_at_d16_grandfather_still_works_read_canonically(canonical_git_repo, as_canonical) -> None:
    repo = canonical_git_repo
    repo.write_decision(
        "at-d16.md",
        "AT-D16:                      RESOLVED / BINDING\n"
        "AT_D16_AUTHORITY_AT_D11: AT-M2\n"
        "AT_D16_AUTHORITY_AT_D13: AT-M2\n"
        "AT_D16_AUTHORITY_AT_D14: AT-M3.1\n"
        "AT_D16_AUTHORITY_AT_D15: AT-M3.1\n",
    )
    as_canonical(repo.commit("synthetic AT-D16, isolated fixture"))

    assert lifecycle._grandfathered_authorizes("AT-D11", "AT-M2")
    assert lifecycle._grandfathered_authorizes("AT-D14", "AT-M3.1")
    assert not lifecycle._grandfathered_authorizes("AT-D14", "AT-M2")
    assert not lifecycle._grandfathered_authorizes("AT-D18", "AT-M2")  # never grows


# --- fixture: immutability -- the load-bearing proof this remediation exists for --------------------


def test_later_mutation_of_an_already_canonical_decision_fails_closed(
    canonical_git_repo, as_canonical
) -> None:
    """The exact scenario Validation 1 demonstrated: AT-D18 becomes canonical authorizing one
    milestone; a LATER commit widens its typed field to add another. The widened field must not
    take effect -- not by silently keeping the old value forever, but by the decision losing
    authority entirely the moment its authority-bearing content has diverged from the version that
    was actually first established, until a human resolves it.
    """
    repo = canonical_git_repo
    repo.write_decision(
        "at-d18.md", _at_d18_text(authorizes_implementation="AT-GOV-FUTURE-SLICE-1")
    )
    first_commit = repo.commit("AT-D18 becomes canonical")
    as_canonical(first_commit)
    assert lifecycle._decision_authorizes("AT-D18", "AT-GOV-FUTURE-SLICE-1", "IMPLEMENTATION")

    repo.write_decision(
        "at-d18.md",
        _at_d18_text(authorizes_implementation="AT-GOV-FUTURE-SLICE-1, AT-M2"),
    )
    mutated_commit = repo.commit("later, unreviewed widening of AT-D18's own authority")
    as_canonical(mutated_commit)

    assert not lifecycle._decision_authorizes("AT-D18", "AT-GOV-FUTURE-SLICE-1", "IMPLEMENTATION")
    assert not lifecycle._decision_authorizes("AT-D18", "AT-M2", "IMPLEMENTATION")
    assert not lifecycle._decision_is_binding("AT-D18")
    # still discoverable -- "known, no longer trustworthy" is distinct from "unknown"
    assert lifecycle._decision_record_path("AT-D18") == "docs/decisions/at-d18.md"


def test_unrelated_prose_edit_does_not_trip_immutability(canonical_git_repo, as_canonical) -> None:
    """Only authority-bearing fields are pinned -- a typo fix elsewhere in the same file must not
    void a decision's authority."""
    repo = canonical_git_repo
    repo.write_decision(
        "at-d18.md",
        _at_d18_text(authorizes_implementation="AT-GOV-FUTURE-SLICE-1")
        + "\nRationale: teh milestone.\n",
    )
    first_commit = repo.commit("AT-D18 becomes canonical")
    as_canonical(first_commit)
    assert lifecycle._decision_authorizes("AT-D18", "AT-GOV-FUTURE-SLICE-1", "IMPLEMENTATION")

    repo.write_decision(
        "at-d18.md",
        _at_d18_text(authorizes_implementation="AT-GOV-FUTURE-SLICE-1")
        + "\nRationale: the milestone.\n",
    )
    later_commit = repo.commit("fix a typo in prose only")
    as_canonical(later_commit)

    assert lifecycle._decision_authorizes("AT-D18", "AT-GOV-FUTURE-SLICE-1", "IMPLEMENTATION")


def test_changeset_registration_immutability(canonical_git_repo, as_canonical) -> None:
    """The same pin applies to a decision's own reviewed-changeset table: a later commit moving
    IMPLEMENTATION_END must not be silently adopted."""
    repo = canonical_git_repo
    baseline = "5a04ec1c67453c4d90b525e94402b9515fbec0bf"
    original_end = "1ba197a91867e77a9fa2256289b2766317b51b41"
    moved_end = "9c002e06029a682f586013671e8cb30ed1a475f4"

    def table(end: str) -> str:
        return (
            "AT-D18:                      RESOLVED / BINDING\n"
            "REGISTERED_CHANGESET_COUNT: 1\n"
            "REGISTERED_CHANGESET_1_MILESTONE:            AT-GOV-FUTURE-SLICE-1\n"
            "REGISTERED_CHANGESET_1_AUTHORIZATION_ID:     AT-D17\n"
            "REGISTERED_CHANGESET_1_MERGE_ID:             AT-D18\n"
            f"REGISTERED_CHANGESET_1_BASELINE:             {baseline}\n"
            f"REGISTERED_CHANGESET_1_IMPLEMENTATION_END:   {end}\n"
        )

    repo.write_decision("at-d18.md", table(original_end))
    first_commit = repo.commit("AT-D18 registers its reviewed end")
    as_canonical(first_commit)
    entries = dict(lifecycle._decision_changeset_entries("AT-D18"))
    assert entries["AT-GOV-FUTURE-SLICE-1"]["IMPLEMENTATION_END"] == original_end

    repo.write_decision("at-d18.md", table(moved_end))
    moved_commit = repo.commit("later, unreviewed move of the registered end")
    as_canonical(moved_commit)
    assert lifecycle._decision_changeset_entries("AT-D18") == []


# --- fixture: cross-decision conflict handling stays intact -----------------------------------------


def test_conflicting_registration_across_decisions_invalidates_only_that_milestone(
    canonical_git_repo, as_canonical
) -> None:
    repo = canonical_git_repo
    repo.write_decision(
        "at-d18.md",
        "AT-D18:                      RESOLVED / BINDING\n"
        "REGISTERED_CHANGESET_COUNT: 1\n"
        "REGISTERED_CHANGESET_1_MILESTONE:            AT-GOV-FUTURE-SLICE-1\n"
        "REGISTERED_CHANGESET_1_AUTHORIZATION_ID:     AT-D17\n"
        "REGISTERED_CHANGESET_1_MERGE_ID:             AT-D18\n"
        "REGISTERED_CHANGESET_1_BASELINE:             5a04ec1c67453c4d90b525e94402b9515fbec0bf\n"
        "REGISTERED_CHANGESET_1_IMPLEMENTATION_END:   9c002e06029a682f586013671e8cb30ed1a475f4\n",
    )
    repo.write_decision(
        "at-d19.md",
        "AT-D19:                      RESOLVED / BINDING\n"
        "REGISTERED_CHANGESET_COUNT: 1\n"
        "REGISTERED_CHANGESET_1_MILESTONE:            AT-GOV-FUTURE-SLICE-1\n"
        "REGISTERED_CHANGESET_1_AUTHORIZATION_ID:     AT-D17\n"
        "REGISTERED_CHANGESET_1_MERGE_ID:             AT-D19\n"
        "REGISTERED_CHANGESET_1_BASELINE:             5a04ec1c67453c4d90b525e94402b9515fbec0bf\n"
        "REGISTERED_CHANGESET_1_IMPLEMENTATION_END:   1ba197a91867e77a9fa2256289b2766317b51b41\n",
    )
    repo.write_decision("unrelated.md", "AT-D20: RESOLVED / BINDING\n")
    as_canonical(repo.commit("two decisions, same milestone, disagreeing ends"))

    canonical = lifecycle._canonical_changesets()
    assert "AT-GOV-FUTURE-SLICE-1" not in canonical


# --- self-registration: the exact candidate, dynamically resolved, never a stale predecessor --------


def test_self_registration_binds_to_the_actual_candidate_dynamically(
    canonical_git_repo, as_canonical
) -> None:
    """Registers this remediation's own real, current AT-D17 record as implementation authority,
    plus a synthetic acceptance decision (AT-D18 -- never a real, referenced decision anywhere in
    this repository), against a candidate commit resolved fresh at test-run time -- never a
    hard-coded SHA from any earlier round of this exercise.
    """
    repo = canonical_git_repo
    milestone = "AT-GOV-DECISION-DISCOVERY-1"  # AT-D17's own real AUTHORIZES_IMPLEMENTATION value

    repo.write("scripts/successor_lifecycle.py", "# earlier, pre-implementation placeholder\n")
    old_commit = repo.commit("baseline, before this milestone's own implementation")
    baseline = old_commit  # a commit that actually exists in this fixture's own object database

    repo.write_decision("at-d16.md", "AT-D16:                      RESOLVED / BINDING\n")
    repo.write_decision("at-d17.md", read(AT_D17_RECORD))  # the real, current AT-D17 text
    repo.write("scripts/successor_lifecycle.py", "# the actual implementation candidate content\n")
    candidate_end = repo.commit("the actual implementation candidate")

    # dynamically derived -- never a literal from an earlier round of this exercise
    assert candidate_end not in (
        "61f94017e1bf6a6e34e72d7440dfeb1c4a47ba02",
        "9cbe2c16bd1048a3fb0186e9195a61643cc60984",
    )

    at_d18_text = (
        "AT-D18:                      RESOLVED / BINDING\n"
        f"AUTHORIZES_ACCEPTANCE_MERGE: {milestone}\n"
        "REGISTERED_CHANGESET_COUNT: 1\n"
        f"REGISTERED_CHANGESET_1_MILESTONE:            {milestone}\n"
        "REGISTERED_CHANGESET_1_AUTHORIZATION_ID:     AT-D17\n"
        "REGISTERED_CHANGESET_1_MERGE_ID:             AT-D18\n"
        f"REGISTERED_CHANGESET_1_BASELINE:             {baseline}\n"
        f"REGISTERED_CHANGESET_1_IMPLEMENTATION_END:   {candidate_end}\n"
    )
    accept_commit = repo.commit_tree_with_extra_files(
        candidate_end,
        {"docs/decisions/at-d18.md": at_d18_text},
        "test-only: synthetic acceptance decision, never referenced by any branch",
    )
    as_canonical(accept_commit)

    repo.write(
        lifecycle.SUPERSESSION_RECORD,
        "AUTHORIZED_CHANGESET_REGISTRY_DECISION: AT-D16\n"
        f"AUTHORIZED_CHANGESET_REGISTRY_RECORD:   docs/decisions/at-d16.md\n"
        "AUTHORIZED_CHANGESET_REGISTRY:          1\n"
        f"AUTHORIZED_CHANGESET_1_MILESTONE:            {milestone}\n"
        "AUTHORIZED_CHANGESET_1_AUTHORIZATION_ID:     AT-D17\n"
        "AUTHORIZED_CHANGESET_1_MERGE_ID:             AT-D18\n"
        f"AUTHORIZED_CHANGESET_1_BASELINE:             {baseline}\n"
        f"AUTHORIZED_CHANGESET_1_IMPLEMENTATION_END:   {candidate_end}\n",
    )

    entries = {e["milestone"]: e for e in lifecycle.authorized_changesets()}
    assert milestone in entries, "AT-D18 registered the milestone through data alone"
    assert (
        entries[milestone]["implementation_end"] == candidate_end
    ), "must bind to the actual candidate, not any stale predecessor"

    changed = lifecycle.live_guard_changed_paths(old_commit)
    assert "scripts/successor_lifecycle.py" not in changed, "the exact candidate blob is reviewed"

    # a later, genuinely-committed edit past the candidate must still be caught
    repo.write("scripts/successor_lifecycle.py", "# a later, unreviewed edit\n")
    repo.commit("later unreviewed edit")
    changed_after_edit = lifecycle.live_guard_changed_paths(old_commit)
    assert "scripts/successor_lifecycle.py" in changed_after_edit

    # a brand-new protected path is covered by no entry at all
    hypothetical = "shared/sdk/agent_reasoning/still_unreviewed.py"
    for entry in lifecycle.authorized_changesets():
        assert lifecycle._blob(hypothetical, entry["implementation_end"]) is None


def test_acceptance_docs_commit_does_not_move_implementation_end(
    canonical_git_repo, as_canonical
) -> None:
    """A later, purely-documentary commit on top of the accepted decision must not cause the
    registered end to chase the newer tip."""
    repo = canonical_git_repo
    milestone = "AT-GOV-DECISION-DISCOVERY-1"

    repo.write("scripts/successor_lifecycle.py", "# earlier, pre-implementation placeholder\n")
    baseline = repo.commit("baseline, before this milestone's own implementation")

    repo.write_decision("at-d16.md", "AT-D16:                      RESOLVED / BINDING\n")
    repo.write_decision("at-d17.md", read(AT_D17_RECORD))
    repo.write("scripts/successor_lifecycle.py", "# candidate content\n")
    candidate_end = repo.commit("the actual implementation candidate")

    at_d18_text = (
        "AT-D18:                      RESOLVED / BINDING\n"
        f"AUTHORIZES_ACCEPTANCE_MERGE: {milestone}\n"
        "REGISTERED_CHANGESET_COUNT: 1\n"
        f"REGISTERED_CHANGESET_1_MILESTONE:            {milestone}\n"
        "REGISTERED_CHANGESET_1_AUTHORIZATION_ID:     AT-D17\n"
        "REGISTERED_CHANGESET_1_MERGE_ID:             AT-D18\n"
        f"REGISTERED_CHANGESET_1_BASELINE:             {baseline}\n"
        f"REGISTERED_CHANGESET_1_IMPLEMENTATION_END:   {candidate_end}\n"
    )
    accept_commit = repo.commit_tree_with_extra_files(
        candidate_end, {"docs/decisions/at-d18.md": at_d18_text}, "synthetic acceptance"
    )
    later_docs_commit = repo.commit_tree_with_extra_files(
        accept_commit,
        {"docs/decisions/readme-touchup.md": "unrelated docs-only note\n"},
        "later, unrelated docs-only commit",
    )
    as_canonical(later_docs_commit)

    repo.write(
        lifecycle.SUPERSESSION_RECORD,
        "AUTHORIZED_CHANGESET_REGISTRY_DECISION: AT-D16\n"
        "AUTHORIZED_CHANGESET_REGISTRY_RECORD:   docs/decisions/at-d16.md\n"
        "AUTHORIZED_CHANGESET_REGISTRY:          1\n"
        f"AUTHORIZED_CHANGESET_1_MILESTONE:            {milestone}\n"
        "AUTHORIZED_CHANGESET_1_AUTHORIZATION_ID:     AT-D17\n"
        "AUTHORIZED_CHANGESET_1_MERGE_ID:             AT-D18\n"
        f"AUTHORIZED_CHANGESET_1_BASELINE:             {baseline}\n"
        f"AUTHORIZED_CHANGESET_1_IMPLEMENTATION_END:   {candidate_end}\n",
    )

    entries = {e["milestone"]: e for e in lifecycle.authorized_changesets()}
    assert entries[milestone]["implementation_end"] == candidate_end, "must not chase the docs tip"


# --- historical / live semantics preserved, unaffected by this remediation --------------------------


def test_historical_window_functions_unaffected() -> None:
    milestone, boundary, _why = lifecycle.authorized_successor()
    assert milestone == "AT-M2"
    assert lifecycle.is_ancestor(boundary, "HEAD")
    assert lifecycle.live_guard_end() == "HEAD"


def test_at_m2_legacy_scalar_unmoved() -> None:
    snapshot = read(SNAPSHOT)
    assert (
        lifecycle._field(snapshot, lifecycle.AUTHORIZED_CHANGESET_END_FIELD)
        == "9c002e06029a682f586013671e8cb30ed1a475f4"
    )


def test_pre_acceptance_the_current_candidate_remains_visible_as_drift() -> None:
    """Without any simulated canonical inclusion, this branch's own changes to the mechanism
    correctly remain unreviewed -- fail-closed, not a defect (AT-D17-R07)."""
    entries = lifecycle.authorized_changesets()
    assert entries == []
