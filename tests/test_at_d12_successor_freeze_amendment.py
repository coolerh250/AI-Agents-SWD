"""AT-D12 -- historical freeze versus authorized successor evolution.

Offline by design: no container, no database, no network, no secret access. These tests do not
read the decision record's prose and take its word for anything. They exercise the mechanism:
each prerequisite is removed in turn and the amendment must be refused, and each amendment shape
is corrupted in turn and must be refused. The point of the record is that it can be checked.
"""

from __future__ import annotations

import pathlib
import re
import subprocess
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import successor_lifecycle as lifecycle  # noqa: E402

RECORD = "docs/decisions/at-d12-successor-freeze-amendment.md"
SNAPSHOT = lifecycle.SUPERSESSION_RECORD

# Where each amendable artifact's historical blob lives.
SOURCE_COMMIT = {
    "scripts/verify_step66c4_be3_ra2_identity_secret_decision.py": (
        "efa396dee6512d6f15b3fd079df87d2c70ee0c77"
    ),
    "tests/test_step66c4_be3_ra2_identity_secret_decision.py": (
        "efa396dee6512d6f15b3fd079df87d2c70ee0c77"
    ),
    "docs/test/step66sync1-codex-frontend-reconciliation-evidence.md": "78aa4ee",
}

# The RA-2 planning documents. These are evidence only, and AT-D12 must not make them amendable.
RA2_HISTORICAL_DOCUMENTS = (
    "docs/security/be3-ra2-current-state-identity-secret-inventory.md",
    "docs/security/be3-ra2-identity-secret-threat-and-trust-analysis.md",
    "docs/contracts/66c4-reminder-expiry-controlled-resume/"
    "be3-ra2-identity-secret-provisioning-decision-package.md",
    "docs/handoffs/66c4-reminder-expiry-controlled-resume/"
    "be3-ra2-implementation-stage-decomposition.md",
    "docs/test/step66c4-be3-ra2-identity-secret-decision-evidence.md",
    "docs/alignment/66-project-completion/master/next-executable-stage-sequence.md",
)


def read(relpath: str) -> str:
    return (REPO / relpath).read_text(encoding="utf-8")


def blob_text(commit: str, rel: str) -> str:
    result = subprocess.run(
        ["git", "show", f"{commit}:{rel}"],
        cwd=REPO,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return result.stdout.decode("utf-8") if result.returncode == 0 else ""


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


# --- the decision exists and is canonical -------------------------------------------------------


def test_the_record_exists_and_is_binding() -> None:
    assert re.search(r"^AT-D12:\s+RESOLVED / BINDING\b", read(RECORD), re.M)


def test_the_canonical_snapshot_names_the_decision_and_the_record() -> None:
    snapshot = read(SNAPSHOT)
    assert lifecycle._field(snapshot, lifecycle.FREEZE_AMENDMENT_DECISION_FIELD) == "AT-D12"
    assert lifecycle._field(snapshot, lifecycle.FREEZE_AMENDMENT_RECORD_FIELD) == RECORD


def test_the_record_is_about_the_milestone_that_is_actually_authorized() -> None:
    milestone, _boundary, _why = lifecycle.authorized_successor()
    assert milestone == "AT-M2"
    assert lifecycle._field(read(RECORD), "AT_D12_SUCCESSOR_MILESTONE") == milestone


def test_the_amendable_set_is_exactly_the_three_named_artifacts() -> None:
    amendable, _why = lifecycle.freeze_amendment_authority()
    assert amendable == {
        "scripts/verify_step66c4_be3_ra2_identity_secret_decision.py": "declared-line",
        "tests/test_step66c4_be3_ra2_identity_secret_decision.py": "declared-line",
        "docs/test/step66sync1-codex-frontend-reconciliation-evidence.md": "appended-note",
    }


def test_the_record_is_the_only_place_the_amendable_set_is_defined() -> None:
    """No path may be hard-coded into the mechanism itself."""
    module = (REPO / "scripts" / "successor_lifecycle.py").read_text(encoding="utf-8")
    for rel in SOURCE_COMMIT:
        assert rel not in module, rel


# --- the three artifacts satisfy their declared shape -------------------------------------------


@pytest.mark.parametrize("rel", sorted(SOURCE_COMMIT))
def test_each_amended_artifact_matches_its_declared_shape(rel: str) -> None:
    allowed, why = lifecycle.frozen_artifact_is_authorized(
        rel, blob_text(SOURCE_COMMIT[rel], rel), read(rel)
    )
    assert allowed, f"{rel}: {why}"


def test_the_appended_note_leaves_the_historical_bytes_as_an_exact_prefix() -> None:
    rel = "docs/test/step66sync1-codex-frontend-reconciliation-evidence.md"
    historical = blob_text(SOURCE_COMMIT[rel], rel).replace("\r\n", "\n")
    current = read(rel).replace("\r\n", "\n")
    assert current.startswith(historical)
    assert lifecycle.APPENDED_NOTE_MARKER in current[len(historical) :]


def test_the_historical_route_table_was_not_recounted() -> None:
    """The successor route is additive; the 66SYNC.1 measurement above the marker is untouched."""
    rel = "docs/test/step66sync1-codex-frontend-reconciliation-evidence.md"
    current = read(rel)
    historical, _, addendum = current.partition(lifecycle.APPENDED_NOTE_MARKER)
    assert "| `/team-room` |" not in historical
    assert "| `/team-room` |" in addendum


@pytest.mark.parametrize(
    "rel",
    [
        "scripts/verify_step66c4_be3_ra2_identity_secret_decision.py",
        "tests/test_step66c4_be3_ra2_identity_secret_decision.py",
    ],
)
def test_every_divergent_guard_line_declares_itself_in_place(rel: str) -> None:
    """A reader of the file can see which lines are not historical without consulting git."""
    historical = set(blob_text(SOURCE_COMMIT[rel], rel).replace("\r\n", "\n").split("\n"))
    divergent = [
        line
        for line in read(rel).replace("\r\n", "\n").split("\n")
        if line not in historical and line.strip()
    ]
    assert divergent
    assert all(lifecycle.DECLARED_LINE_MARKER in line for line in divergent)


# --- fail closed: remove one prerequisite at a time ----------------------------------------------


def test_no_snapshot_fields_means_nothing_is_amendable(redact) -> None:
    redact(
        SNAPSHOT,
        lambda text: "\n".join(
            line
            for line in text.splitlines()
            if lifecycle.FREEZE_AMENDMENT_RECORD_FIELD not in line
        ),
    )
    assert lifecycle.freeze_amendment_authority()[0] == {}


def test_a_missing_decision_record_means_nothing_is_amendable(redact) -> None:
    redact(RECORD, lambda _text: "")
    assert lifecycle.freeze_amendment_authority()[0] == {}


def test_a_non_binding_decision_record_means_nothing_is_amendable(redact) -> None:
    redact(RECORD, lambda text: text.replace("AT-D12:                      RESOLVED / BINDING", ""))
    assert lifecycle.freeze_amendment_authority()[0] == {}


def test_a_record_naming_a_different_successor_means_nothing_is_amendable(redact) -> None:
    redact(
        RECORD,
        lambda text: text.replace(
            "AT_D12_SUCCESSOR_MILESTONE: AT-M2", "AT_D12_SUCCESSOR_MILESTONE: AT-M7"
        ),
    )
    assert lifecycle.freeze_amendment_authority()[0] == {}


def test_no_authorized_successor_means_nothing_is_amendable(redact) -> None:
    """AT-D12 cannot stand on its own -- it rides on AT-D11's successor authorization."""
    redact(
        SNAPSHOT,
        lambda text: "\n".join(
            line for line in text.splitlines() if lifecycle.MILESTONE_FIELD not in line
        ),
    )
    assert lifecycle.authorized_successor()[0] == ""
    assert lifecycle.freeze_amendment_authority()[0] == {}


def test_dropping_a_path_from_the_record_refreezes_that_artifact(redact) -> None:
    rel = "tests/test_step66c4_be3_ra2_identity_secret_decision.py"
    redact(
        RECORD,
        lambda text: "\n".join(line for line in text.splitlines() if rel not in line),
    )
    allowed, why = lifecycle.frozen_artifact_is_authorized(
        rel, blob_text(SOURCE_COMMIT[rel], rel), read(rel)
    )
    assert not allowed
    assert "not named as amendable" in why


def test_an_artifact_no_record_names_can_never_be_amended() -> None:
    allowed, _why = lifecycle.frozen_artifact_is_authorized(
        "shared/sdk/tasks/rbac.py", "historical\n", "rewritten\n"
    )
    assert not allowed


# --- fail closed: corrupt each amendment shape ---------------------------------------------------


def test_an_undeclared_divergent_line_is_refused() -> None:
    rel = "scripts/verify_step66c4_be3_ra2_identity_secret_decision.py"
    historical = blob_text(SOURCE_COMMIT[rel], rel)
    smuggled = historical.replace("import re\n", "import re\nRUN_ANYTHING = True\n", 1)
    allowed, why = lifecycle.frozen_artifact_is_authorized(rel, historical, smuggled)
    assert not allowed
    assert "undeclared" in why


def test_deleting_a_historical_line_is_refused() -> None:
    rel = "scripts/verify_step66c4_be3_ra2_identity_secret_decision.py"
    historical = blob_text(SOURCE_COMMIT[rel], rel)
    gutted = historical.replace("import re\n", "", 1)
    allowed, why = lifecycle.frozen_artifact_is_authorized(rel, historical, gutted)
    assert not allowed
    assert "deletes" in why


def test_a_marker_cannot_launder_a_deletion() -> None:
    """The marker declares an addition. It does not license removing what was there."""
    rel = "tests/test_step66c4_be3_ra2_identity_secret_decision.py"
    historical = "alpha\nbeta\ngamma\n"
    current = f"alpha\ngamma\nadded  {lifecycle.DECLARED_LINE_MARKER}\n"
    allowed, _why = lifecycle.frozen_artifact_is_authorized(rel, historical, current)
    assert not allowed


def test_editing_the_prefix_of_an_appended_note_artifact_is_refused() -> None:
    rel = "docs/test/step66sync1-codex-frontend-reconciliation-evidence.md"
    historical = blob_text(SOURCE_COMMIT[rel], rel)
    tampered = historical.replace("IMPLEMENTED", "NOT_IMPLEMENTED", 1) + (
        f"{lifecycle.APPENDED_NOTE_MARKER}\nnote\n"
    )
    allowed, why = lifecycle.frozen_artifact_is_authorized(rel, historical, tampered)
    assert not allowed
    assert "prefix" in why


def test_an_appended_note_without_the_marker_is_refused() -> None:
    rel = "docs/test/step66sync1-codex-frontend-reconciliation-evidence.md"
    historical = blob_text(SOURCE_COMMIT[rel], rel)
    allowed, why = lifecycle.frozen_artifact_is_authorized(rel, historical, historical + "note\n")
    assert not allowed
    assert "marker" in why or "SUCCESSOR-NOTE-BEGIN" in why


def test_an_unknown_amendment_mode_is_ignored(redact) -> None:
    redact(RECORD, lambda text: text.replace("declared-line", "anything-goes"))
    amendable, _why = lifecycle.freeze_amendment_authority()
    assert "scripts/verify_step66c4_be3_ra2_identity_secret_decision.py" not in amendable


# --- historical evidence is untouched -------------------------------------------------------------


@pytest.mark.parametrize("rel", RA2_HISTORICAL_DOCUMENTS)
def test_ra2_planning_documents_are_not_amendable_and_are_byte_identical(rel: str) -> None:
    amendable, _why = lifecycle.freeze_amendment_authority()
    assert rel not in amendable

    planning = subprocess.run(
        ["git", "rev-parse", f"efa396dee6512d6f15b3fd079df87d2c70ee0c77:{rel}"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()
    current = subprocess.run(
        ["git", "rev-parse", f":{rel}"], cwd=REPO, capture_output=True, text=True, check=False
    ).stdout.strip()
    assert planning and planning == current, rel


def test_the_ra2_decision_package_still_records_pending_selections() -> None:
    package = read(
        "docs/contracts/66c4-reminder-expiry-controlled-resume/"
        "be3-ra2-identity-secret-provisioning-decision-package.md"
    )
    assert "PENDING" in package
    assert "PRODUCT_OWNER_DECISION_REQUIRED" in package
    assert "RESOLVED / BINDING" not in package


# --- the live artifacts are still truthful --------------------------------------------------------


def test_the_route_inventory_covers_every_route_in_current_source() -> None:
    app = read("apps/admin-console/src/App.tsx")
    evidence = read("docs/test/step66sync1-codex-frontend-reconciliation-evidence.md")
    routes = re.findall(r'<Route\s+path="([^"]+)"', app)
    assert routes
    assert [route for route in routes if f"| `{route}` |" not in evidence] == []


def test_the_amended_ra2_guard_asks_the_shared_mechanism_not_a_literal_range() -> None:
    """The amendment substituted one call for one literal. It removed no check."""
    guard = read("scripts/verify_step66c4_be3_ra2_identity_secret_decision.py")
    assert "successor_window_end(BASELINE_MAIN)" in guard
    assert '_git("diff", "--name-only", BASELINE_MAIN, "HEAD")' not in guard

    # The stage's own commits are still inside the window: the boundary is a descendant of the
    # baseline and an ancestor of HEAD, so nothing the stage did was exempted by the amendment.
    window = lifecycle.successor_window_end("c1db4cc")
    assert window != "HEAD"
    assert lifecycle.is_ancestor("c1db4cc", window)
    assert lifecycle.is_ancestor(window, "HEAD")

    # Every check the guard performed before the amendment is still performed.
    historical = blob_text(
        SOURCE_COMMIT["scripts/verify_step66c4_be3_ra2_identity_secret_decision.py"],
        "scripts/verify_step66c4_be3_ra2_identity_secret_decision.py",
    )
    for check in re.findall(r'bad\(f?"(check\d+[a-z]?)', historical):
        assert check in guard, f"the amendment dropped {check}"


# --- AT-D12 grants nothing --------------------------------------------------------------------------


def test_the_decision_authorizes_no_milestone_and_no_production() -> None:
    snapshot = read(SNAPSHOT)
    assert re.search(r"AT_M3_TO_AT_M8:\s*NOT AUTHORIZED", snapshot)
    assert re.search(r"PRODUCTION_AUTHORIZATION:\s*NOT GRANTED", snapshot)
    assert re.search(r"PRODUCTION_EXECUTED_TRUE_COUNT:\s*0\b", snapshot)

    record = read(RECORD)
    assert "production_executed_true_count: 0" in record
    assert "Does NOT authorize AT-M3 .. AT-M8" in record
    assert "Does NOT register any failure as historical debt" in record


def test_the_decision_leaks_no_internal_identifier() -> None:
    forbidden = re.compile(r"10\.0\.1\.(31|32)|aiagent-swd|itadmin|stpadmin", re.IGNORECASE)
    assert forbidden.search(read(RECORD)) is None


def test_a_marked_line_cannot_launder_a_net_deletion() -> None:
    """Replacing many historical lines with one marked line is a deletion, not an amendment."""
    rel = "tests/test_step66c4_be3_ra2_identity_secret_decision.py"
    historical = "alpha\nbeta\ngamma\ndelta\n"
    current = f"alpha\nreplacement  {lifecycle.DECLARED_LINE_MARKER}\n"
    allowed, why = lifecycle.frozen_artifact_is_authorized(rel, historical, current)
    assert not allowed
    assert "only" in why


def test_the_line_comparison_does_not_use_a_readability_heuristic() -> None:
    """difflib's autojunk drops common lines from matching -- fine for diffs, not for integrity."""
    module = (REPO / "scripts" / "successor_lifecycle.py").read_text(encoding="utf-8")
    assert "autojunk=False" in module


# --- the shared current-state helper ---------------------------------------------------------------
#
# Cross-stage meta-guards require that a stage's runtime denylist keeps scanning current state.
# They were written against the literal spelling of the range, so sharing one call broke them
# each time the call's spelling changed. The helper restates the property; these probes check it
# did not become a rubber stamp.


@pytest.mark.parametrize(
    "body",
    [
        '_git("diff", "--name-only", RUNTIME_GUARD_ANCHOR, "HEAD")',
        'git("diff", "--name-only", CANONICAL_MAIN).splitlines()',
        'CURRENT = f"{RUNTIME_GUARD_ANCHOR}...HEAD"',
        "changed = live_guard_changed_paths(RUNTIME_GUARD_ANCHOR)",
    ],
)
def test_current_state_spellings_are_accepted(body: str) -> None:
    anchor = "CANONICAL_MAIN" if "CANONICAL_MAIN" in body else "RUNTIME_GUARD_ANCHOR"
    assert lifecycle.scans_current_state(body, anchor)


@pytest.mark.parametrize(
    "body",
    [
        # the failure these meta-guards exist to catch: a denylist pinned to a frozen stage head
        '_git("diff", "--name-only", RUNTIME_GUARD_ANCHOR, ALIGN1_STAGE_HEAD)',
        'CURRENT = f"{RUNTIME_GUARD_ANCHOR}...{ARCH1_STAGE_HEAD}"',
        '_git("diff", "--name-only", SOME_OTHER_ANCHOR, "HEAD")',
        "there is no rejection range here at all",
        # the exact failure this rebaseline found live: this spelling reduces to a FROZEN boundary,
        # not HEAD, the moment any successor is authorized -- so it must never be accepted again.
        "changed = successor_window_end(RUNTIME_GUARD_ANCHOR)",
        'git("diff", "--name-only", RUNTIME_GUARD_ANCHOR, successor_window_end(RUNTIME_GUARD_ANCHOR))',
    ],
)
def test_a_frozen_or_absent_range_is_still_rejected(body: str) -> None:
    assert not lifecycle.scans_current_state(body, "RUNTIME_GUARD_ANCHOR")


# --- live guards actually reach HEAD, not just spell it -----------------------------------------
#
# scans_current_state above is still a syntax check: it looks at source text, not behaviour. What
# actually matters is whether live_guard_end/live_guard_changed_paths reach real current HEAD when
# a successor genuinely IS authorized -- the exact condition this repository is in right now, with
# AT-M2 authorized and its boundary behind HEAD. These probes call the mechanism, not its spelling.


def test_live_guard_end_is_unconditionally_head() -> None:
    """No argument, no PM-state read -- there is nothing in the signature that could cap this."""
    assert lifecycle.live_guard_end() == "HEAD"


def test_live_guard_ignores_the_authorized_successor_boundary_right_now() -> None:
    """AT-M2 is authorized and its boundary is behind HEAD in THIS repository, right now.

    window_end (historical) is capped at the boundary for an ancestor baseline, exactly as
    designed. live_guard_end is not capped by the same live authorization state -- that is the
    entire property this rebaseline exists to restore.
    """
    milestone, boundary, _why = lifecycle.authorized_successor()
    assert milestone, "this test requires AT-M2 to be the live authorized successor"
    assert lifecycle.is_ancestor(boundary, "HEAD")

    ancestor_of_boundary = "c1db4cc"  # a real, old commit; ancestor of the boundary
    historical_end, _why = lifecycle.window_end(ancestor_of_boundary)
    assert historical_end == boundary, "the historical path must still be capped at the boundary"
    assert lifecycle.live_guard_end() == "HEAD", "the live path must never be capped"


def test_authorized_changeset_end_reads_its_own_field() -> None:
    """Distinct field from the boundary: this is where AT-M2's own reviewed work stops."""
    end, why = lifecycle.authorized_changeset_end()
    assert end, why
    assert lifecycle._git("cat-file", "-t", end) == "commit"
    _milestone, boundary, _why = lifecycle.authorized_successor()
    assert lifecycle.is_ancestor(boundary, end)
    assert lifecycle.is_ancestor(end, "HEAD")


def test_authorized_changeset_end_fails_closed_with_no_field(redact) -> None:
    redact(
        SNAPSHOT,
        lambda text: "\n".join(
            line
            for line in text.splitlines()
            if lifecycle.AUTHORIZED_CHANGESET_END_FIELD not in line
        ),
    )
    assert lifecycle.authorized_changeset_end()[0] == ""


def test_authorized_changeset_end_fails_closed_with_an_unreachable_commit(redact) -> None:
    redact(
        SNAPSHOT,
        lambda text: re.sub(
            rf"{lifecycle.AUTHORIZED_CHANGESET_END_FIELD}:\s*\S+",
            f"{lifecycle.AUTHORIZED_CHANGESET_END_FIELD}: 0000000000000000000000000000000000000000",
            text,
        ),
    )
    assert lifecycle.authorized_changeset_end()[0] == ""


def test_authorized_changeset_end_fails_closed_with_an_end_predating_the_boundary(redact) -> None:
    """An end older than the boundary would exempt commits nobody authorized -- refused."""
    redact(
        SNAPSHOT,
        lambda text: re.sub(
            rf"{lifecycle.AUTHORIZED_CHANGESET_END_FIELD}:\s*\S+",
            f"{lifecycle.AUTHORIZED_CHANGESET_END_FIELD}: c1db4ccbfd88fa775e4761c932835896b9b980ed",
            text,
        ),
    )
    end, why = lifecycle.authorized_changeset_end()
    assert end == "", f"an end predating the boundary must fail closed, got {end!r}: {why}"


def test_authorized_changeset_end_fails_closed_with_no_authorized_successor(redact) -> None:
    """AT-D12's own pattern: the mechanism cannot stand on AT-D11's authorization alone."""
    redact(
        SNAPSHOT,
        lambda text: "\n".join(
            line for line in text.splitlines() if lifecycle.MILESTONE_FIELD not in line
        ),
    )
    assert lifecycle.authorized_successor()[0] == ""
    assert lifecycle.authorized_changeset_end()[0] == ""


def test_live_guard_does_not_misfire_on_at_m2s_own_authorized_work() -> None:
    """The exact property acceptance requires: AT-M2's own changes must not trip a live guard.

    RUNTIME_GUARD_ANCHOR predates AT-M2 and AT-M2 genuinely touches apps/, agents/, shared/ and
    migrations/ -- exactly what a runtime denylist forbids. Without the content-identical
    exclusion this would misfire on every AT-M2 candidate run; with it, AT-M2's own reviewed work
    is recognised and excluded, and the offender list is empty.
    """
    changed = lifecycle.live_guard_changed_paths("c1db4cc")
    offenders = [
        p for p in changed if p.startswith(("apps/", "agents/", "shared/", "migrations/", "infra/"))
    ]
    assert offenders == [], f"AT-M2's own authorized work was not excluded: {offenders}"


def test_live_guard_would_catch_drift_beyond_a_stale_authorized_end(redact) -> None:
    """A path is excluded by CONTENT at the recorded end, not by membership in some window.

    Pointing the recorded end at an OLD real commit -- standing in for "the end was never moved
    forward, or was reused from an earlier milestone" -- must make AT-M2's own real runtime paths
    show up as offenders again: their content at HEAD no longer matches their content at that
    stale end. This is the fail-closed direction: understating the end never hides anything,
    it can only ever widen what a live guard rejects.
    """
    redact(
        SNAPSHOT,
        lambda text: re.sub(
            rf"{lifecycle.AUTHORIZED_CHANGESET_END_FIELD}:\s*\S+",
            f"{lifecycle.AUTHORIZED_CHANGESET_END_FIELD}: 192ebb74ba600f7a53ddf5967a7254a1f7a72fb8",
            text,
        ),
    )
    changed = lifecycle.live_guard_changed_paths("c1db4cc")
    offenders = [
        p for p in changed if p.startswith(("apps/", "agents/", "shared/", "migrations/", "infra/"))
    ]
    assert offenders, "with the recorded end pinned before AT-M2, its own paths must reappear"


def test_the_helper_is_shared_not_reimplemented() -> None:
    """One mechanism, not nine hand-written variants of the same regex."""
    imported = "from successor_lifecycle import scans_current_state"
    callers = [
        path
        for path in list((REPO / "scripts").glob("*.py")) + list((REPO / "tests").glob("*.py"))
        if imported in path.read_text(encoding="utf-8")
    ]
    assert len(callers) >= 10, [p.name for p in callers]

    # every caller carries the same fail-closed fallback, so an isolated copy of the tree without
    # scripts/ degrades to the strict literal test rather than to "anything goes"
    for path in callers:
        body = path.read_text(encoding="utf-8")
        assert "Strictest fallback" in body, path.name
