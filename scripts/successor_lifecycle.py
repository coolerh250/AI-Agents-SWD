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


__all__ = [
    "AUTHORIZATION_RECORD_FIELD",
    "BOUNDARY_FIELD",
    "MILESTONE_FIELD",
    "SUPERSESSION_RECORD",
    "authorized_successor",
    "changed_paths",
    "is_ancestor",
    "rejection_range",
    "window_end",
]
