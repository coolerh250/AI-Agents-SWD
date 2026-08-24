#!/usr/bin/env python3
"""Shared successor-milestone lifecycle for stage implementation guards.

Many completed stages carry a guard of the same shape: "this stage introduced no
implementation", asked as a diff from the stage's frozen baseline to HEAD. HEAD-relative is
correct while the stage is live -- freezing it would blind the guard to implementation added
after review under that stage's name.

It is not correct forever. Every one of those guards also asserts, implicitly, that NO LATER
MILESTONE may add implementation either, because the diff keeps growing as main advances. Taken
together they make the first authorized implementation milestone after them unbuildable by
construction. AT-M2 tripped fifteen of them at once.

This module closes those windows -- all of them, through ONE mechanism rather than fifteen
individual relaxations -- at the commit where a Product Owner authorized the successor milestone.
It answers exactly one question: WHERE does a stage's rejection window end? It changes no other
assertion in any guard, and it never widens a positive scope.

Fail-closed in every direction. The window closes only when:

  1. the canonical PM snapshot names an authorized successor implementation milestone,
  2. the snapshot names the lifecycle boundary commit,
  3. the snapshot records that milestone as AUTHORIZED and names its authorizing decision,
  4. that decision record exists, is RESOLVED / BINDING, and names the SAME boundary commit,
  5. the boundary commit exists and is an ancestor of HEAD,
  6. the boundary is a DESCENDANT of the calling guard's own baseline.

If any of those does not hold the window stays HEAD-relative at full strength. (6) is per-caller
and is what stops a boundary being walked backwards over a stage's own commits.

Everything above is for a HISTORICAL claim -- "this closed stage added no implementation" -- and
closing its window at the boundary is correct: the claim is about a period that ended before the
successor existed. A runtime denylist is a different claim: "no protected path is ever changed
except by an explicitly authorized milestone", and that must keep holding after the boundary too,
forever, not just up to it. Routing a denylist through ``successor_window_end`` blinded it exactly
like the guards above -- except a denylist is never supposed to stop looking. See
``live_guard_changed_paths`` below, which a stage's runtime denylist should call instead.
"""

from __future__ import annotations

import difflib
import pathlib
import re
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]

SUPERSESSION_RECORD = "docs/governance/AI_AGENTS_PM_STATE.md"

# The successor milestone's own authorization decision. Named by the snapshot; read from disk so
# a snapshot alone can never open a window.
AUTHORIZATION_RECORD_FIELD = "SUCCESSOR_AUTHORIZATION_RECORD"
MILESTONE_FIELD = "SUCCESSOR_IMPLEMENTATION_MILESTONE"
BOUNDARY_FIELD = "SUCCESSOR_LIFECYCLE_BOUNDARY"

OPEN_REASON = "no authorized successor milestone; the window is HEAD-relative"

# --- AT-D12 freeze amendment -------------------------------------------------------------------
#
# A few artifacts are historical stage evidence AND live machinery at the same time: a frozen
# verifier that still has to scan current state, a frozen inventory that still has to describe
# current source. Freezing them stops them working; editing them freely dissolves the freeze
# contract for every stage at once. AT-D12 resolves that with an exhaustive per-path amendable
# set and two amendment shapes that keep the historical content provable.
#
# Fail-closed: with no binding AT-D12 record, no authorized successor, or a path the record does
# not name, ANY divergence from the historical blob is a rewrite.

FREEZE_AMENDMENT_DECISION_FIELD = "SUCCESSOR_FREEZE_AMENDMENT_DECISION"
FREEZE_AMENDMENT_RECORD_FIELD = "SUCCESSOR_FREEZE_AMENDMENT_RECORD"

# Every divergent line of an executable guard declares itself with this marker.
DECLARED_LINE_MARKER = "# AT-D12-AMENDED"

# An evidence document keeps its historical bytes as a prefix; the successor appends after this.
APPENDED_NOTE_MARKER = "<!-- SUCCESSOR-NOTE-BEGIN: AT-D12 -->"

AMENDMENT_MODES = ("declared-line", "appended-note")

NO_AMENDMENT_REASON = "no binding freeze-amendment authority; frozen artifacts are immutable"


def _read(relpath: str) -> str:
    path = ROOT / relpath
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def _field(text: str, name: str) -> str:
    match = re.search(rf"^{re.escape(name)}:\s*(\S.*?)\s*$", text, re.M)
    return match.group(1) if match else ""


def _git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=False
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def is_ancestor(earlier: str, later: str) -> bool:
    if not earlier or not later:
        return False
    return (
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", earlier, later],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        ).returncode
        == 0
    )


def authorized_successor() -> tuple[str, str, str]:
    """(milestone, boundary_commit, why) for the authorized successor, or ('', '', why)."""
    snapshot = _read(SUPERSESSION_RECORD)
    if not snapshot:
        return "", "", OPEN_REASON

    milestone = _field(snapshot, MILESTONE_FIELD)
    boundary = _field(snapshot, BOUNDARY_FIELD)
    record = _field(snapshot, AUTHORIZATION_RECORD_FIELD)
    if not (milestone and boundary and record):
        return "", "", OPEN_REASON

    # The snapshot must record the milestone itself as authorized, under its own key.
    milestone_key = milestone.replace("-", "_").upper()
    if not re.search(rf"^{re.escape(milestone_key)}:\s*AUTHORIZED\b", snapshot, re.M):
        return "", "", OPEN_REASON
    authorized_by = _field(snapshot, f"{milestone_key}_AUTHORIZED_BY")
    decision_id = authorized_by.split("/")[0].strip()
    if not decision_id:
        return "", "", OPEN_REASON

    # The decision record is the authority, not the snapshot. It must be binding AND name the
    # same boundary, so moving the boundary requires amending a Product Owner decision.
    decision = _read(record)
    if not decision:
        return "", "", OPEN_REASON
    if not re.search(rf"^{re.escape(decision_id)}:\s*RESOLVED / BINDING\b", decision, re.M):
        return "", "", OPEN_REASON
    if boundary not in decision:
        return "", "", OPEN_REASON

    if _git("cat-file", "-t", boundary) != "commit":
        return "", "", OPEN_REASON
    if not is_ancestor(boundary, "HEAD"):
        return "", "", OPEN_REASON

    return milestone, boundary, f"{milestone} authorized at {boundary[:7]}"


def window_end(baseline: str = "") -> tuple[str, str]:
    """(commit the rejection window ends at, why).

    ``baseline`` is the calling guard's own frozen anchor. When supplied, the boundary is only
    honoured if it is a DESCENDANT of it: a boundary older than the stage would silently exempt
    the stage's own commits, which is the one direction this mechanism must never move.
    """
    milestone, boundary, why = authorized_successor()
    if not boundary:
        return "HEAD", why
    if baseline and not is_ancestor(baseline, boundary):
        return "HEAD", (
            f"the {milestone} boundary predates this stage's baseline, so the window stays open"
        )
    return boundary, why


def successor_window_end(baseline: str = "") -> str:
    """The commit a stage's rejection window ends at -- ``HEAD`` unless a successor is authorized.

    The single call form every stage guard uses, so the cross-stage meta-checks can pin ONE
    spelling instead of a family of hand-written ranges. Substituting this for a literal ``HEAD``
    is the whole refactor: the guard still scans current state, it just stops claiming authority
    over commits an authorized successor milestone owns.
    """
    return window_end(baseline)[0]


def scans_current_state(body: str, anchor: str) -> bool:
    """Does a stage guard in ``body`` still resolve its rejection range against current state?

    Several stages carry a cross-stage meta-guard asserting that a LATER stage never froze its
    runtime denylist along with its positive scope. Those meta-guards were written to match the
    literal spelling of the range, so converting the guards to a shared call broke them each time
    the call's spelling changed -- while the property they protect was meant to stay intact.

    ``successor_window_end(<anchor>)`` USED to belong in this list: before AT-M2 it reduced to
    HEAD in every real case, because no successor had ever been authorized. It no longer means
    that -- AT-M2 IS an authorized successor right now, so that spelling resolves to a frozen
    boundary, not HEAD, which is exactly the failure these meta-guards exist to catch. It is
    deliberately absent below. The only accepted current-state forms are the two literal HEAD
    spellings, the bare diff against the working tree, and ``live_guard_changed_paths(<anchor>)``,
    which ignores the PM snapshot entirely and can never be capped by any successor, present or
    future.
    """
    accepted = (
        f'"--name-only", {anchor}, "HEAD"',
        f'"--name-only", {anchor})',
        f'f"{{{anchor}}}...HEAD"',
        f"live_guard_changed_paths({anchor})",
    )
    return any(form in body for form in accepted)


def rejection_range(baseline: str) -> tuple[str, str]:
    """(``baseline...<end>`` range, why) -- the symmetric-difference form guards use."""
    end, why = window_end(baseline)
    return f"{baseline}...{end}", why


def changed_paths(baseline: str) -> list[str]:
    """Repository-relative paths changed inside ``baseline``'s rejection window."""
    end, _why = window_end(baseline)
    return [
        line.strip().replace("\\", "/")
        for line in _git("diff", "--name-only", baseline, end).splitlines()
        if line.strip()
    ]


# --- live guards: never capped at a successor boundary ------------------------------------------
#
# A runtime denylist's whole job is to reject a protected path added by ANY later commit, under
# ANY later stage's name, forever -- unlike a stage's "no implementation" claim, it is not about a
# period that closes. AT-D11 says as much directly: architecture invariants "stay live and
# HEAD-relative"; only the no-implementation window closes. ``live_guard_end`` is the range-end a
# denylist must use instead of ``successor_window_end`` -- it ignores the PM snapshot entirely, so
# no authorized successor can ever cap it.
#
# The one thing a live guard still has to tolerate is the currently authorized milestone's OWN
# already-reviewed work, which necessarily touches the paths the denylist protects -- that is the
# entire content of what AT-D11 authorizes. It is excluded by CONTENT, not by path: a path is
# exempt only where its blob at HEAD is byte-identical to its blob at the milestone's recorded
# changeset end, so a later, unauthorized edit to a path the milestone already touched is a new
# divergence and is caught on its own merits, the same as a path nobody has ever touched before.

AUTHORIZED_CHANGESET_END_FIELD = "SUCCESSOR_AUTHORIZED_CHANGESET_END"

# --- AT-D16 multi-milestone registry -------------------------------------------------------------
#
# AUTHORIZED_CHANGESET_END_FIELD above is AT-M2-only provenance: it was never extended to name a
# second milestone's own reviewed work, because no milestone after AT-M2 had merged new content
# under a live-guarded path until AT-M3.1. AT-D16 registers AT-M3.1's own reviewed content as a
# second, independent entry rather than moving or reinterpreting the AT-M2 scalar.
#
# AT-D16-REMEDIATION-1 (Multi-Milestone Validation 1) found the first cut of this registry trusted
# two things it should not have: an entry's exact field VALUES came from the PM snapshot alone
# (so any ancestry-plausible commit could stand in for the real reviewed one), and a decision's
# authority over a milestone was decided by searching that decision's prose for the milestone's
# name as a substring (so AT-D14's incidental mentions of "AT-M2" satisfied an AT-M2 check it never
# authorized). Both are fixed the same way: AT-D16's OWN structured fields are now the only
# canonical source of an entry's values and of which decision authorizes which milestone; the PM
# snapshot is only a mirror that must match AT-D16 EXACTLY, field for field, to be used at all.

REGISTRY_COUNT_FIELD = "AUTHORIZED_CHANGESET_REGISTRY"
REGISTRY_DECISION_FIELD = "AUTHORIZED_CHANGESET_REGISTRY_DECISION"
REGISTRY_RECORD_FIELD = "AUTHORIZED_CHANGESET_REGISTRY_RECORD"

CANONICAL_CHANGESET_COUNT_FIELD = "AT_D16_CHANGESET_COUNT"
CANONICAL_CHANGESET_PREFIX = "AT_D16_CHANGESET_"
CANONICAL_AUTHORITY_PREFIX = "AT_D16_AUTHORITY_"

_ENTRY_FIELD_NAMES = ("MILESTONE", "AUTHORIZATION_ID", "MERGE_ID", "BASELINE", "IMPLEMENTATION_END")


# Every decision this mechanism can be asked to verify already lives at a fixed, well-known path.
# A registry entry names only the decision's short id (AT-D11 .. AT-D16); this is the one place
# that id is resolved to a file, so a malformed entry can never point the mechanism at an arbitrary
# path supplied elsewhere in the snapshot.
_DECISION_RECORD_PATHS = {
    "AT-D11": "docs/decisions/at-m2-authorization.md",
    "AT-D12": "docs/decisions/at-d12-successor-freeze-amendment.md",
    "AT-D13": "docs/decisions/at-d13-at-m2-merge-authorization.md",
    "AT-D14": "docs/decisions/at-d14-at-m3-live-reasoning-authorization.md",
    "AT-D15": "docs/decisions/at-d15-at-m3-1-acceptance-and-merge-authorization.md",
    "AT-D16": "docs/decisions/at-d16-multi-milestone-changeset-registry.md",
}


def _decision_record_path(decision_id: str) -> str:
    return _DECISION_RECORD_PATHS.get(decision_id, "")


def _decision_is_binding(decision_id: str) -> bool:
    text = _read(_decision_record_path(decision_id))
    if not text:
        return False
    return bool(re.search(rf"^{re.escape(decision_id)}:\s*RESOLVED / BINDING\b", text, re.M))


def _indexed_entries(text: str, count_field: str, prefix: str) -> dict[str, dict[str, str]]:
    """Parse a ``{prefix}{i}_{FIELD}``-style changeset table out of ``text``, keyed by milestone.

    A milestone named by more than one index collapses harmlessly if every field agrees, and is
    dropped entirely -- for every index that named it -- if any field disagrees. Registry
    integrity never resolves a conflict by picking a side, by keeping the first one seen, or by
    unioning the candidates: an ambiguous milestone gets no entry at all.
    """
    try:
        count = int(_field(text, count_field) or "0")
    except ValueError:
        return {}

    raw: list[tuple[str, dict[str, str]]] = []
    for i in range(1, count + 1):
        values = {name: _field(text, f"{prefix}{i}_{name}") for name in _ENTRY_FIELD_NAMES}
        if all(values.values()):
            milestone = values.pop("MILESTONE")
            raw.append((milestone, values))

    entries: dict[str, dict[str, str]] = {}
    conflicted: set[str] = set()
    for milestone, values in raw:
        if milestone in entries and entries[milestone] != values:
            conflicted.add(milestone)
        else:
            entries[milestone] = values
    for milestone in conflicted:
        entries.pop(milestone, None)
    return entries


def _canonical_changesets() -> dict[str, dict[str, str]]:
    """AT-D16's own structured changeset table -- the only canonical source of entry values.

    Empty unless AT-D16 itself exists on disk and reads RESOLVED / BINDING; the PM snapshot is
    never consulted here, so nothing the snapshot claims can manufacture a canonical value.
    """
    text = _read(_decision_record_path("AT-D16"))
    if not text or not re.search(r"^AT-D16:\s*RESOLVED / BINDING\b", text, re.M):
        return {}
    return _indexed_entries(text, CANONICAL_CHANGESET_COUNT_FIELD, CANONICAL_CHANGESET_PREFIX)


def _decision_authorizes(decision_id: str, milestone: str) -> bool:
    """Does AT-D16's own authority index say ``decision_id`` authorizes ``milestone``?

    Trust is rooted in AT-D16 itself -- a Product Owner decision, independently RESOLVED /
    BINDING -- which states this directly, as an exact index entry. ``decision_id``'s own document
    is checked only for its OWN RESOLVED / BINDING status, never scanned for an incidental mention
    of the milestone's name: AT-D14's prose mentions "AT-M2" several times without authorizing it,
    which is exactly the false-authorization this check must not reproduce.
    """
    if not _decision_is_binding(decision_id):
        return False
    at_d16_text = _read(_decision_record_path("AT-D16"))
    if not at_d16_text or not re.search(r"^AT-D16:\s*RESOLVED / BINDING\b", at_d16_text, re.M):
        return False
    field = _field(at_d16_text, f"{CANONICAL_AUTHORITY_PREFIX}{decision_id.replace('-', '_')}")
    authorized_milestones = {name.strip() for name in field.split(",") if name.strip()}
    return milestone in authorized_milestones


def authorized_changesets() -> list[dict[str, str]]:
    """Validated ``{milestone, baseline, implementation_end}`` entries for the live-guard registry.

    AT-D16's own structured table is the only canonical source of an entry's values (see
    ``_canonical_changesets``); the PM snapshot must independently mirror those exact values,
    field for field, or that milestone gets no entry -- an ancestry-plausible substitute is not a
    match. Authority is exact-index lookup against AT-D16's own authority table (see
    ``_decision_authorizes``), never a substring search of a decision's prose. AT-M2's entry
    additionally requires the legacy scalar (``AUTHORIZED_CHANGESET_END_FIELD``) to equal its
    canonical end exactly -- the scalar itself never moves, but a mismatch invalidates the
    registry's AT-M2 entry specifically. Any one failure drops only that milestone; it never
    substitutes a wider value and never disturbs another milestone's entry.
    """
    canonical = _canonical_changesets()
    if not canonical:
        return []

    snapshot = _read(SUPERSESSION_RECORD)
    if not snapshot:
        return []
    registry_decision_id = _field(snapshot, REGISTRY_DECISION_FIELD)
    registry_record = _field(snapshot, REGISTRY_RECORD_FIELD)
    if not (registry_decision_id and registry_record):
        return []
    if registry_decision_id != "AT-D16" or registry_record != _decision_record_path("AT-D16"):
        return []

    mirrored = _indexed_entries(snapshot, REGISTRY_COUNT_FIELD, "AUTHORIZED_CHANGESET_")

    entries: list[dict[str, str]] = []
    for milestone, canon in canonical.items():
        if mirrored.get(milestone) != canon:
            continue  # the PM snapshot does not exactly mirror AT-D16's canonical values

        auth_id = canon["AUTHORIZATION_ID"]
        merge_id = canon["MERGE_ID"]
        baseline = canon["BASELINE"]
        end = canon["IMPLEMENTATION_END"]

        if not _decision_authorizes(auth_id, milestone):
            continue
        if not _decision_authorizes(merge_id, milestone):
            continue

        if milestone == "AT-M2" and _field(snapshot, AUTHORIZED_CHANGESET_END_FIELD) != end:
            continue

        if _git("cat-file", "-t", baseline) != "commit":
            continue
        if _git("cat-file", "-t", end) != "commit":
            continue
        if not is_ancestor(baseline, end):
            continue
        if not is_ancestor(end, "HEAD"):
            continue

        entries.append({"milestone": milestone, "baseline": baseline, "implementation_end": end})

    return entries


def live_guard_end() -> str:
    """Where a live guard's scan ends: always current HEAD, never a successor boundary.

    Takes no argument and reads no PM-state field -- there is nothing in the mechanism that could
    cap this, which is the entire point. This is the one call a runtime denylist should make in
    place of ``successor_window_end``.
    """
    return "HEAD"


def authorized_changeset_end() -> tuple[str, str]:
    """(commit, why) the authorized successor milestone's OWN reviewed work ends at.

    Distinct from the successor boundary, which is where a stage's historical window OPENS: this
    is where the CURRENTLY authorized milestone's own already-reviewed commits stop. Read from the
    same snapshot, under its own field, so a live guard can tell "the milestone's reviewed
    commits" from "everything after the boundary, forever".

    Fail-closed in every direction: no authorized successor (see ``authorized_successor``), no
    recorded end, an end that is not a real commit, one that predates the successor boundary, or
    one that is not an ancestor of HEAD -- any of those and nothing is exempt from a live guard.
    """
    _milestone, boundary, _why = authorized_successor()
    if not boundary:
        return "", OPEN_REASON
    snapshot = _read(SUPERSESSION_RECORD)
    end = _field(snapshot, AUTHORIZED_CHANGESET_END_FIELD)
    if not end:
        return "", "no recorded authorized-changeset end"
    if _git("cat-file", "-t", end) != "commit":
        return "", "recorded authorized-changeset end is not a real commit"
    if not is_ancestor(boundary, end):
        return "", "recorded end predates the successor boundary"
    if not is_ancestor(end, "HEAD"):
        return "", "recorded end is not an ancestor of HEAD"
    return end, f"authorized milestone's own reviewed work ends at {end[:7]}"


def _blob(relpath: str, commit: str) -> str | None:
    result = subprocess.run(
        ["git", "show", f"{commit}:{relpath}"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return result.stdout if result.returncode == 0 else None


def live_guard_changed_paths(baseline: str) -> list[str]:
    """Paths changed since ``baseline``, always through current HEAD -- never a successor boundary.

    A path is excluded only where its content at HEAD is byte-identical to its content at one of
    the reviewed changeset ends this mechanism currently recognises: the legacy AT-M2-only scalar
    (``authorized_changeset_end``) plus every validated AT-D16 registry entry
    (``authorized_changesets``). Content match against ANY one of them is sufficient -- this is
    what lets AT-M2's and AT-M3.1's own reviewed versions of the same path both be recognised
    without either being able to stand in for the other. A further edit to a path past every
    recognised end -- by anyone, under any name -- is a new divergence and stays in the result.
    With no valid end anywhere, nothing is excluded.
    """
    changed = [
        line.strip().replace("\\", "/")
        for line in _git("diff", "--name-only", baseline, live_guard_end()).splitlines()
        if line.strip()
    ]

    ends: list[str] = []
    legacy_end, _why = authorized_changeset_end()
    if legacy_end:
        ends.append(legacy_end)
    for entry in authorized_changesets():
        if entry["implementation_end"] not in ends:
            ends.append(entry["implementation_end"])
    if not ends:
        return changed

    def _reviewed(path: str) -> bool:
        head_blob = _blob(path, "HEAD")
        return any(_blob(path, end) == head_blob for end in ends)

    return [path for path in changed if not _reviewed(path)]


def freeze_amendment_authority() -> tuple[dict[str, str], str]:
    """({repo-relative path: amendment mode}, why) for artifacts AT-D12 makes amendable.

    Empty in every failure direction: no snapshot, no named decision, no record on disk, a record
    that is not binding, or a record whose successor milestone disagrees with the one actually
    authorized. An empty map means every frozen artifact is immutable -- the behaviour that held
    before AT-D12 existed.
    """
    milestone, _boundary, _why = authorized_successor()
    if not milestone:
        return {}, NO_AMENDMENT_REASON

    snapshot = _read(SUPERSESSION_RECORD)
    decision_id = _field(snapshot, FREEZE_AMENDMENT_DECISION_FIELD)
    record = _field(snapshot, FREEZE_AMENDMENT_RECORD_FIELD)
    if not (decision_id and record):
        return {}, NO_AMENDMENT_REASON

    text = _read(record)
    if not text:
        return {}, NO_AMENDMENT_REASON
    if not re.search(rf"^{re.escape(decision_id)}:\s*RESOLVED / BINDING\b", text, re.M):
        return {}, NO_AMENDMENT_REASON

    # The record must be about the milestone that is actually authorized, so an amendment record
    # written for one successor can never be reused to cover a different one.
    if _field(text, "AT_D12_SUCCESSOR_MILESTONE") != milestone:
        return {}, NO_AMENDMENT_REASON

    amendable: dict[str, str] = {}
    for mode, path in re.findall(r"^AMENDABLE_FROZEN_ARTIFACT:\s+(\S+)\s+(\S+)\s*$", text, re.M):
        if mode in AMENDMENT_MODES:
            amendable[path] = mode
    if not amendable:
        return {}, NO_AMENDMENT_REASON
    return amendable, f"{decision_id} names {len(amendable)} amendable artifact(s) for {milestone}"


def _lf(text: str) -> str:
    return text.replace("\r\n", "\n")


def _declared_line_amendment(historical: str, current: str) -> tuple[bool, str]:
    """Every divergent line must declare itself. A historical line may be replaced, not dropped."""
    old = _lf(historical).split("\n")
    new = _lf(current).split("\n")
    # autojunk would treat common lines (blanks, closing brackets) as unmatchable in a file this
    # size, which is a heuristic for readable diffs and wrong for an integrity comparison.
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(
        None, old, new, autojunk=False
    ).get_opcodes():
        if tag == "equal":
            continue
        added = new[j1:j2]
        if not added:
            return False, f"deletes {i2 - i1} historical line(s) without a declared replacement"
        # A marker declares an addition. It must not become a licence to net-delete: replacing
        # fifty historical lines with one marked line would otherwise read as a legal amendment.
        if len(added) < (i2 - i1):
            return False, f"replaces {i2 - i1} historical line(s) with only {len(added)}"
        undeclared = [line for line in added if DECLARED_LINE_MARKER not in line]
        if undeclared:
            return False, f"undeclared divergent line: {undeclared[0].strip()[:70]!r}"
    return True, "every divergent line declares itself"


def _appended_note_amendment(historical: str, current: str) -> tuple[bool, str]:
    """The historical content must survive as a byte-exact prefix, with nothing deleted."""
    old, new = _lf(historical), _lf(current)
    if not new.startswith(old):
        return False, "historical content is no longer a byte-exact prefix of the file"
    if APPENDED_NOTE_MARKER not in new[len(old) :]:
        return False, f"the appended note does not open with {APPENDED_NOTE_MARKER!r}"
    return True, "historical bytes intact; the successor note is append-only"


def frozen_artifact_is_authorized(relpath: str, historical: str, current: str) -> tuple[bool, str]:
    """(is this frozen artifact still legitimate, why).

    Byte-identical always passes. Anything else needs AT-D12 to name this exact path, and the
    divergence must match the shape the record declared for it.
    """
    if _lf(historical) == _lf(current):
        return True, "byte-identical to the historical blob"

    amendable, why = freeze_amendment_authority()
    mode = amendable.get(relpath.replace("\\", "/"))
    if not mode:
        if not amendable:
            return False, why
        return False, "not named as amendable by the freeze-amendment record"

    ok, detail = (
        _declared_line_amendment(historical, current)
        if mode == "declared-line"
        else _appended_note_amendment(historical, current)
    )
    return ok, f"{mode}: {detail}"


__all__ = [
    "APPENDED_NOTE_MARKER",
    "AUTHORIZATION_RECORD_FIELD",
    "AUTHORIZED_CHANGESET_END_FIELD",
    "BOUNDARY_FIELD",
    "DECLARED_LINE_MARKER",
    "FREEZE_AMENDMENT_DECISION_FIELD",
    "FREEZE_AMENDMENT_RECORD_FIELD",
    "MILESTONE_FIELD",
    "REGISTRY_COUNT_FIELD",
    "REGISTRY_DECISION_FIELD",
    "REGISTRY_RECORD_FIELD",
    "SUPERSESSION_RECORD",
    "authorized_changeset_end",
    "authorized_changesets",
    "authorized_successor",
    "changed_paths",
    "freeze_amendment_authority",
    "frozen_artifact_is_authorized",
    "is_ancestor",
    "live_guard_changed_paths",
    "live_guard_end",
    "rejection_range",
    "scans_current_state",
    "successor_window_end",
    "window_end",
]
