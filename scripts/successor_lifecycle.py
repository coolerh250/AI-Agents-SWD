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
    "BOUNDARY_FIELD",
    "DECLARED_LINE_MARKER",
    "FREEZE_AMENDMENT_DECISION_FIELD",
    "FREEZE_AMENDMENT_RECORD_FIELD",
    "MILESTONE_FIELD",
    "SUPERSESSION_RECORD",
    "authorized_successor",
    "changed_paths",
    "freeze_amendment_authority",
    "frozen_artifact_is_authorized",
    "is_ancestor",
    "rejection_range",
    "successor_window_end",
    "window_end",
]
