"""AT-D17 -- data-driven decision discovery and future authority bootstrap.

Offline by design: no container, no database, no network, no secret access, no persistent
repository change. These tests do not read the decision record's prose and take its word for
anything. They exercise the mechanism: a synthetic future decision (AT-D18, AT-D19) is faked
purely by monkeypatching ``_read`` to return synthetic content for a path that already exists on
disk (and is otherwise inert -- it claims no decision id of its own), so ``directory.glob()``
genuinely finds a real file while its *content* is substituted. No file is written to or deleted
from the repository at any point.
"""

from __future__ import annotations

import pathlib
import re
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import successor_lifecycle as lifecycle  # noqa: E402

SNAPSHOT = lifecycle.SUPERSESSION_RECORD
AT_D17_RECORD = "docs/decisions/at-d17-decision-discovery-bootstrap.md"
AT_D16_RECORD = lifecycle._decision_record_path("AT-D16")

# Two real, existing files under docs/decisions/ that currently claim no AT-D<n> identity of
# their own -- safe, inert stand-ins for synthetic future decisions. Faking their _read() content
# makes ``directory.glob()`` find a genuinely-existing file while the text it reads is synthetic.
STAND_IN_A = "docs/decisions/adr-template.md"
STAND_IN_B = "docs/decisions/README.md"

OLD_BASELINE = "c1db4cc"


def read(relpath: str) -> str:
    return (REPO / relpath).read_text(encoding="utf-8")


@pytest.fixture
def fake_content(monkeypatch):
    """Serve synthetic content for one or more paths, leaving disk untouched.

    Unlike the simpler single-target ``redact`` fixture the AT-D16 suite uses, decision discovery
    needs several paths faked at once (a stand-in file plus the PM snapshot plus, sometimes,
    AT-D16 itself), so this takes a dict of path -> content/transform.
    """
    real = lifecycle._read

    def install(overrides: dict[str, object]) -> None:
        def fake(relpath: str) -> str:
            if relpath in overrides:
                value = overrides[relpath]
                return value(real(relpath)) if callable(value) else value
            return real(relpath)

        monkeypatch.setattr(lifecycle, "_read", fake)

    return install


def _at_d18_text(authorizes_implementation: str = "", authorizes_acceptance: str = "") -> str:
    lines = ["AT-D18:                      RESOLVED / BINDING"]
    if authorizes_implementation:
        lines.append(f"AUTHORIZES_IMPLEMENTATION: {authorizes_implementation}")
    if authorizes_acceptance:
        lines.append(f"AUTHORIZES_ACCEPTANCE_MERGE: {authorizes_acceptance}")
    return "\n".join(lines) + "\n"


# --- the record exists and is canonical ----------------------------------------------------------


def test_the_record_exists_and_is_binding() -> None:
    assert re.search(r"^AT-D17:\s+RESOLVED / BINDING\b", read(AT_D17_RECORD), re.M)


def test_the_decision_leaks_no_internal_identifier() -> None:
    forbidden = re.compile(r"10\.0\.1\.(31|32)|aiagent-swd|itadmin|stpadmin", re.IGNORECASE)
    assert forbidden.search(read(AT_D17_RECORD)) is None


# --- 1/2: existing decisions discovered ------------------------------------------------------------


def test_at_d11_discovered() -> None:
    assert lifecycle._decision_record_path("AT-D11") == "docs/decisions/at-m2-authorization.md"


def test_at_d16_discovered() -> None:
    assert AT_D16_RECORD == "docs/decisions/at-d16-multi-milestone-changeset-registry.md"


# --- 3: AT-D17 discovers itself, for real, with no id map -----------------------------------------


def test_at_d17_discovered_with_no_hard_coded_map() -> None:
    assert lifecycle._decision_record_path("AT-D17") == AT_D17_RECORD
    assert lifecycle._decision_is_binding("AT-D17")


def test_no_python_literal_enumerates_decision_ids() -> None:
    """The defect this record closes: a fixed dict/list of every known decision id."""
    module = (REPO / "scripts" / "successor_lifecycle.py").read_text(encoding="utf-8")
    assert "_DECISION_RECORD_PATHS" not in module
    # every real decision id besides the ones the module's OWN fixed AT-D16 grandfather references
    # by name (AT-D16 itself only) must be absent as a literal
    for forbidden_id in ("AT-D11", "AT-D13", "AT-D14", "AT-D15", "AT-D17", "AT-D18"):
        assert f'"{forbidden_id}"' not in module, forbidden_id


def test_at_d17_authorizes_its_own_milestone_only() -> None:
    assert lifecycle._decision_authorizes("AT-D17", "AT-GOV-DECISION-DISCOVERY-1", "IMPLEMENTATION")
    assert not lifecycle._decision_authorizes("AT-D17", "AT-M2", "IMPLEMENTATION")
    assert not lifecycle._decision_authorizes(
        "AT-D17", "AT-GOV-DECISION-DISCOVERY-1", "ACCEPTANCE_MERGE"
    )


# --- 4/5: synthetic future decisions, discovered without touching the module ----------------------


def test_synthetic_at_d18_discovered_without_code_change(fake_content) -> None:
    fake_content({STAND_IN_A: _at_d18_text(authorizes_implementation="AT-GOV-FUTURE-SLICE-1")})
    assert lifecycle._decision_record_path("AT-D18") == STAND_IN_A
    assert lifecycle._decision_is_binding("AT-D18")
    assert lifecycle._decision_authorizes("AT-D18", "AT-GOV-FUTURE-SLICE-1", "IMPLEMENTATION")


def test_synthetic_at_d19_discovered_without_code_change(fake_content) -> None:
    at_d19_text = "AT-D19:                      RESOLVED / BINDING\nAUTHORIZES_ACCEPTANCE_MERGE: AT-GOV-FUTURE-SLICE-1\n"
    fake_content({STAND_IN_B: at_d19_text})
    assert lifecycle._decision_record_path("AT-D19") == STAND_IN_B
    assert lifecycle._decision_authorizes("AT-D19", "AT-GOV-FUTURE-SLICE-1", "ACCEPTANCE_MERGE")


# --- 6: unknown decision rejected ------------------------------------------------------------------


def test_unknown_at_d99_rejected() -> None:
    assert lifecycle._decision_record_path("AT-D99") == ""
    assert not lifecycle._decision_is_binding("AT-D99")
    assert not lifecycle._decision_authorizes("AT-D99", "AT-M2", "IMPLEMENTATION")


# --- 7: duplicate identity across two files fails closed --------------------------------------------


def test_duplicate_at_d18_identity_across_two_files_is_rejected(fake_content) -> None:
    fake_content(
        {
            STAND_IN_A: _at_d18_text(authorizes_implementation="AT-GOV-FUTURE-SLICE-1"),
            STAND_IN_B: _at_d18_text(authorizes_implementation="AT-GOV-FUTURE-SLICE-1"),
        }
    )
    assert lifecycle._decision_record_path("AT-D18") == ""
    # every OTHER decision remains unambiguous and independently usable
    assert lifecycle._decision_record_path("AT-D16") == AT_D16_RECORD
    assert lifecycle._decision_record_path("AT-D17") == AT_D17_RECORD


# --- 8: one file claiming multiple decision identities fails closed for all of them ----------------


def test_one_file_claiming_two_ids_is_rejected_for_both(fake_content) -> None:
    both = (
        "AT-D18:                      RESOLVED / BINDING\n"
        "AT-D19:                      RESOLVED / BINDING\n"
    )
    fake_content({STAND_IN_A: both})
    assert lifecycle._decision_record_path("AT-D18") == ""
    assert lifecycle._decision_record_path("AT-D19") == ""


# --- 9: non-binding decision rejected, distinctly from "unknown" -----------------------------------


def test_non_binding_at_d18_is_discovered_but_not_binding(fake_content) -> None:
    """Discovery finds the id even though it is not (yet) binding -- a different failure reason
    from AT-D99, which is never discovered at all."""
    fake_content({STAND_IN_A: "AT-D18:                      PENDING\n"})
    assert lifecycle._decision_record_path("AT-D18") == STAND_IN_A, "discovery must still find it"
    assert not lifecycle._decision_is_binding("AT-D18")
    assert not lifecycle._decision_authorizes("AT-D18", "AT-GOV-FUTURE-SLICE-1", "IMPLEMENTATION")


# --- 10: wrong authorization type (slot) rejected ---------------------------------------------------


def test_implementation_only_authority_does_not_satisfy_acceptance_slot(fake_content) -> None:
    fake_content({STAND_IN_A: _at_d18_text(authorizes_implementation="AT-GOV-FUTURE-SLICE-1")})
    assert lifecycle._decision_authorizes("AT-D18", "AT-GOV-FUTURE-SLICE-1", "IMPLEMENTATION")
    assert not lifecycle._decision_authorizes("AT-D18", "AT-GOV-FUTURE-SLICE-1", "ACCEPTANCE_MERGE")


def test_acceptance_only_authority_does_not_satisfy_implementation_slot(fake_content) -> None:
    fake_content({STAND_IN_A: _at_d18_text(authorizes_acceptance="AT-GOV-FUTURE-SLICE-1")})
    assert lifecycle._decision_authorizes("AT-D18", "AT-GOV-FUTURE-SLICE-1", "ACCEPTANCE_MERGE")
    assert not lifecycle._decision_authorizes("AT-D18", "AT-GOV-FUTURE-SLICE-1", "IMPLEMENTATION")


# --- 11: wrong milestone rejected ---------------------------------------------------------------


def test_wrong_milestone_rejected(fake_content) -> None:
    fake_content({STAND_IN_A: _at_d18_text(authorizes_implementation="AT-GOV-FUTURE-SLICE-1")})
    assert not lifecycle._decision_authorizes("AT-D18", "AT-GOV-SOME-OTHER-SLICE", "IMPLEMENTATION")


# --- 12: malformed typed field rejected -----------------------------------------------------------


def test_malformed_typed_field_grants_nothing(fake_content) -> None:
    fake_content(
        {
            STAND_IN_A: "AT-D18:                      RESOLVED / BINDING\nAUTHORIZES_IMPLEMENTATION:\n"
        }
    )
    assert not lifecycle._decision_authorizes("AT-D18", "", "IMPLEMENTATION")
    assert not lifecycle._decision_authorizes("AT-D18", "AT-GOV-FUTURE-SLICE-1", "IMPLEMENTATION")


# --- 13: arbitrary path injection is impossible -----------------------------------------------------


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


def test_discovery_never_takes_a_path_from_pm_or_registry_data(fake_content) -> None:
    """Even if the PM snapshot's registry-record field is corrupted to an arbitrary path, that
    value is only ever compared for equality -- never passed to a file read."""
    fake_content(
        {
            SNAPSHOT: lambda text: re.sub(
                r"AUTHORIZED_CHANGESET_REGISTRY_RECORD:\s*\S+",
                "AUTHORIZED_CHANGESET_REGISTRY_RECORD:   ../../../etc/passwd",
                text,
            )
        }
    )
    assert lifecycle.authorized_changesets() == []


# --- 14: symlink escape rejected, where the filesystem actually has one to test --------------------


def test_symlinked_decision_files_are_not_discovered(tmp_path) -> None:
    """A symlink placed inside a scratch decisions directory, pointing at a real decision file
    elsewhere, must not be discovered -- proven against an isolated scratch copy so this
    repository's real docs/decisions/ is never touched."""
    scratch_root = tmp_path / "repo"
    decisions_dir = scratch_root / "docs" / "decisions"
    decisions_dir.mkdir(parents=True)
    target = tmp_path / "outside.md"
    target.write_text("AT-D18:                      RESOLVED / BINDING\n", encoding="utf-8")
    link = decisions_dir / "at-d18-linked.md"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("symlinks not supported in this environment")

    import unittest.mock as mock

    with mock.patch.object(lifecycle, "ROOT", scratch_root):
        assert lifecycle._discovered_decision_paths() == {}


# --- 15: AT-D16 legacy grandfather still works, unmodified -----------------------------------------


def test_at_d16_grandfather_authority_still_works() -> None:
    assert lifecycle._decision_authorizes("AT-D11", "AT-M2", "IMPLEMENTATION")
    assert lifecycle._decision_authorizes("AT-D13", "AT-M2", "ACCEPTANCE_MERGE")
    assert lifecycle._decision_authorizes("AT-D14", "AT-M3.1", "IMPLEMENTATION")
    assert lifecycle._decision_authorizes("AT-D15", "AT-M3.1", "ACCEPTANCE_MERGE")
    assert not lifecycle._decision_authorizes("AT-D14", "AT-M2", "IMPLEMENTATION")


# --- 16/17: AT-M2 / AT-M3.1 reviewed entries remain accepted ---------------------------------------


def test_at_m2_and_at_m3_1_entries_remain_accepted() -> None:
    entries = {e["milestone"]: e for e in lifecycle.authorized_changesets()}
    assert entries["AT-M2"]["implementation_end"] == "9c002e06029a682f586013671e8cb30ed1a475f4"
    assert entries["AT-M3.1"]["implementation_end"] == "1ba197a91867e77a9fa2256289b2766317b51b41"


def test_at_m3_1_reviewed_content_still_exempt() -> None:
    raw = lifecycle._git("diff", "--name-only", OLD_BASELINE, "HEAD").splitlines()
    at_m3_1_paths = [
        p
        for p in raw
        if p.startswith("shared/sdk/agent_reasoning/") or p.startswith("migrations/037_")
    ]
    changed = lifecycle.live_guard_changed_paths(OLD_BASELINE)
    assert not any(p in changed for p in at_m3_1_paths)


# --- 18: exact provenance substitutions remain rejected ---------------------------------------------


def test_ancestry_valid_but_non_canonical_end_still_rejected(fake_content) -> None:
    fake_content(
        {
            SNAPSHOT: lambda text: re.sub(
                r"AUTHORIZED_CHANGESET_2_IMPLEMENTATION_END:\s*\S+",
                "AUTHORIZED_CHANGESET_2_IMPLEMENTATION_END:   1e9fe3b445e1ddaefe0c4ed0bdc5be8af4d0ad96",
                text,
            )
        }
    )
    milestones = {e["milestone"] for e in lifecycle.authorized_changesets()}
    assert milestones == {"AT-M2"}


# --- 19: duplicate milestone registration still fails closed, now across decisions -----------------


def test_a_future_decision_conflicting_with_at_d16s_at_m2_entry_invalidates_at_m2(
    fake_content,
) -> None:
    """A synthetic later decision claiming to ALSO register AT-M2, with a different end, must not
    override or be unioned with AT-D16's real entry -- this is the cross-decision form of
    conflict-fails-closed, not merely the within-one-table form the AT-D16 suite already covers.
    """
    conflicting = (
        "AT-D18:                      RESOLVED / BINDING\n"
        "REGISTERED_CHANGESET_COUNT: 1\n"
        "REGISTERED_CHANGESET_1_MILESTONE:            AT-M2\n"
        "REGISTERED_CHANGESET_1_AUTHORIZATION_ID:     AT-D11\n"
        "REGISTERED_CHANGESET_1_MERGE_ID:             AT-D13\n"
        "REGISTERED_CHANGESET_1_BASELINE:             192ebb74ba600f7a53ddf5967a7254a1f7a72fb8\n"
        "REGISTERED_CHANGESET_1_IMPLEMENTATION_END:   0986c895e85b426f3ca56239ad7cdb39288a8546\n"
    )
    fake_content({STAND_IN_A: conflicting})
    canonical = lifecycle._canonical_changesets()
    assert "AT-M2" not in canonical
    assert "AT-M3.1" in canonical  # unrelated milestone unaffected


def test_a_future_decision_registering_a_new_milestone_identically_twice_collapses_harmlessly(
    fake_content,
) -> None:
    identical = (
        "AT-D18:                      RESOLVED / BINDING\n"
        "REGISTERED_CHANGESET_COUNT: 2\n"
        "REGISTERED_CHANGESET_1_MILESTONE:            AT-GOV-FUTURE-SLICE-1\n"
        "REGISTERED_CHANGESET_1_AUTHORIZATION_ID:     AT-D17\n"
        "REGISTERED_CHANGESET_1_MERGE_ID:             AT-D17\n"
        "REGISTERED_CHANGESET_1_BASELINE:             5a04ec1c67453c4d90b525e94402b9515fbec0bf\n"
        "REGISTERED_CHANGESET_1_IMPLEMENTATION_END:   61f94017e1bf6a6e34e72d7440dfeb1c4a47ba02\n"
        "REGISTERED_CHANGESET_2_MILESTONE:            AT-GOV-FUTURE-SLICE-1\n"
        "REGISTERED_CHANGESET_2_AUTHORIZATION_ID:     AT-D17\n"
        "REGISTERED_CHANGESET_2_MERGE_ID:             AT-D17\n"
        "REGISTERED_CHANGESET_2_BASELINE:             5a04ec1c67453c4d90b525e94402b9515fbec0bf\n"
        "REGISTERED_CHANGESET_2_IMPLEMENTATION_END:   61f94017e1bf6a6e34e72d7440dfeb1c4a47ba02\n"
    )
    fake_content({STAND_IN_A: identical})
    canonical = lifecycle._canonical_changesets()
    assert (
        canonical.get("AT-GOV-FUTURE-SLICE-1", {}).get("IMPLEMENTATION_END")
        == "61f94017e1bf6a6e34e72d7440dfeb1c4a47ba02"
    )


# --- 20/21/22: simulated self-registration through data only, no repository change -----------------


def test_simulated_self_registration_exempts_the_exact_candidate_only(fake_content) -> None:
    """Section 8/10's core proof: register this branch's own tip through AT-D17 (real, already
    on disk, implementation authority) + a synthetic AT-D18 (acceptance/merge authority) + PM data
    alone, confirm the mechanism's own file becomes exempt, and that a further edit is still caught.

    The milestone identity is AT-D17's own real ``AUTHORIZES_IMPLEMENTATION`` value -- a decision
    can only authorize the milestone it actually names, the exact property this whole record
    exists to enforce (never "AT-D14 authorizes AT-M2 because it mentions the name").
    """
    milestone = "AT-GOV-DECISION-DISCOVERY-1"
    candidate_end = "61f94017e1bf6a6e34e72d7440dfeb1c4a47ba02"
    baseline = "5a04ec1c67453c4d90b525e94402b9515fbec0bf"

    at_d18 = (
        "AT-D18:                      RESOLVED / BINDING\n"
        f"AUTHORIZES_ACCEPTANCE_MERGE: {milestone}\n"
        "REGISTERED_CHANGESET_COUNT: 1\n"
        f"REGISTERED_CHANGESET_1_MILESTONE:            {milestone}\n"
        "REGISTERED_CHANGESET_1_AUTHORIZATION_ID:     AT-D17\n"
        "REGISTERED_CHANGESET_1_MERGE_ID:             AT-D18\n"
        f"REGISTERED_CHANGESET_1_BASELINE:             {baseline}\n"
        f"REGISTERED_CHANGESET_1_IMPLEMENTATION_END:   {candidate_end}\n"
    )

    def snapshot_plus_entry(text: str) -> str:
        text = re.sub(r"(AUTHORIZED_CHANGESET_REGISTRY:\s*)2", r"\g<1>3", text)
        return text + (
            f"\nAUTHORIZED_CHANGESET_3_MILESTONE:            {milestone}\n"
            "AUTHORIZED_CHANGESET_3_AUTHORIZATION_ID:     AT-D17\n"
            "AUTHORIZED_CHANGESET_3_MERGE_ID:             AT-D18\n"
            f"AUTHORIZED_CHANGESET_3_BASELINE:             {baseline}\n"
            f"AUTHORIZED_CHANGESET_3_IMPLEMENTATION_END:   {candidate_end}\n"
        )

    fake_content({STAND_IN_A: at_d18, SNAPSHOT: snapshot_plus_entry})

    entries = {e["milestone"] for e in lifecycle.authorized_changesets()}
    assert milestone in entries, "AT-D18 registered the milestone through data alone"

    changed = lifecycle.live_guard_changed_paths(OLD_BASELINE)
    assert (
        "scripts/successor_lifecycle.py" not in changed
    ), "the exact candidate blob is now reviewed"

    # a later, unreviewed edit to the same file must still be caught
    real_blob = lifecycle._blob

    def fake_blob(path: str, commit: str) -> str | None:
        if path == "scripts/successor_lifecycle.py" and commit == "HEAD":
            return (real_blob(path, "HEAD") or "") + "\n# later unreviewed edit\n"
        return real_blob(path, commit)

    import unittest.mock as mock

    with mock.patch.object(lifecycle, "_blob", side_effect=fake_blob):
        changed_after_edit = lifecycle.live_guard_changed_paths(OLD_BASELINE)
    assert "scripts/successor_lifecycle.py" in changed_after_edit

    # a brand-new protected path is never covered by this or any entry
    hypothetical = "shared/sdk/agent_reasoning/still_unreviewed.py"
    for entry in lifecycle.authorized_changesets():
        assert lifecycle._blob(hypothetical, entry["implementation_end"]) is None


def test_pre_acceptance_the_current_candidate_remains_visible_as_drift() -> None:
    """Without the simulated registration above, the unmodified repository still correctly shows
    this branch's own changes to the mechanism as unreviewed -- fail-closed, not a defect.
    """
    changed = lifecycle.live_guard_changed_paths(OLD_BASELINE)
    assert "scripts/successor_lifecycle.py" in changed


# --- historical/live semantics preserved ------------------------------------------------------------


def test_historical_window_functions_unaffected() -> None:
    milestone, boundary, _why = lifecycle.authorized_successor()
    assert milestone == "AT-M2"
    we, _why = lifecycle.window_end(OLD_BASELINE)
    assert we == boundary
    assert lifecycle.live_guard_end() == "HEAD"


def test_at_m2_legacy_scalar_unmoved() -> None:
    snapshot = read(SNAPSHOT)
    assert (
        lifecycle._field(snapshot, lifecycle.AUTHORIZED_CHANGESET_END_FIELD)
        == "9c002e06029a682f586013671e8cb30ed1a475f4"
    )
