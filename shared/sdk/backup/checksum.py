"""Stage 36 -- SHA-256 helpers for backup artifacts."""

from __future__ import annotations

import hashlib
from pathlib import Path

_CHUNK_BYTES = 1024 * 1024


def compute_sha256(path: str | Path) -> str:
    """Streamed SHA-256 over a file path.

    Returned as a lower-case hex digest. Streamed so an encrypted
    backup that runs into GB doesn't load into memory.
    """

    target = Path(path)
    if not target.is_file():
        raise FileNotFoundError(f"backup artifact not found: {target}")
    h = hashlib.sha256()
    with target.open("rb") as fh:
        while True:
            chunk = fh.read(_CHUNK_BYTES)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def verify_sha256(path: str | Path, expected: str) -> bool:
    """Recompute the artifact's checksum and compare to ``expected``."""

    if not expected:
        return False
    actual = compute_sha256(path)
    return actual.lower() == expected.lower()
