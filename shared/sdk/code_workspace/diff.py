"""Stage 28 — diff + hashing helpers used by the deterministic generator."""

from __future__ import annotations

import difflib
import hashlib


def compute_unified_diff(
    before: str,
    after: str,
    *,
    file_path: str,
    context: int = 3,
) -> str:
    """Return a unified diff between two text blobs.

    ``before`` is empty for new files. ``file_path`` is used for both the
    ``---`` and ``+++`` headers (with ``a/`` / ``b/`` prefixes) so the
    output renders correctly inside a PR body.
    """
    before_lines = before.splitlines(keepends=True) if before else []
    after_lines = after.splitlines(keepends=True) if after else []
    diff = difflib.unified_diff(
        before_lines,
        after_lines,
        fromfile=f"a/{file_path}",
        tofile=f"b/{file_path}",
        n=context,
    )
    return "".join(diff)


def summarize_diff(diff_text: str) -> dict[str, int | str]:
    """Return ``{added, removed, hunks, summary}`` for a unified diff."""
    if not diff_text:
        return {"added": 0, "removed": 0, "hunks": 0, "summary": "empty_diff"}
    added = 0
    removed = 0
    hunks = 0
    for line in diff_text.splitlines():
        if line.startswith("@@"):
            hunks += 1
        elif line.startswith("+") and not line.startswith("+++"):
            added += 1
        elif line.startswith("-") and not line.startswith("---"):
            removed += 1
    return {
        "added": added,
        "removed": removed,
        "hunks": hunks,
        "summary": f"+{added}/-{removed} across {hunks} hunk(s)",
    }


def hash_content(content: str) -> str:
    """SHA-256 of UTF-8 encoded ``content`` — used for before/after_sha."""
    h = hashlib.sha256()
    h.update((content or "").encode("utf-8"))
    return h.hexdigest()
