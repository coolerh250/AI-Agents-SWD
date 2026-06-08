"""SHA-256 helpers for the audit hash-chain.

Two distinct hashes are computed per audit_logs row:

* ``canonical_payload_hash`` -- SHA-256 over the canonical-JSON of the
  business payload. Lets a future reader prove the row's contents have
  not been altered.
* ``row_hash`` -- SHA-256 over an envelope that includes the previous
  row's ``row_hash``. This is the chain: any tamper between rows --
  reordering, deletion, insertion of a forged row -- breaks the chain
  at that point and the verifier reports the failure coordinates.
"""

from __future__ import annotations

import hashlib

from .canonical import canonical_json

GENESIS_PREV_HASH = "GENESIS"


def compute_payload_hash(canonical_payload: dict | str) -> str:
    """Return SHA-256 hex digest of the canonical payload.

    Accepts either the canonical dict or its already-serialised JSON
    string. The dict path delegates to :func:`canonical_json` so the
    hash is identical regardless of input shape.
    """
    if isinstance(canonical_payload, dict):
        text = canonical_json(canonical_payload)
    else:
        text = str(canonical_payload)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def compute_row_hash(
    *,
    chain_version: int,
    sequence_number: int,
    audit_log_id: str,
    prev_hash: str | None,
    canonical_payload_hash: str,
) -> str:
    """Return SHA-256 hex digest of the chain envelope.

    The envelope is deterministic newline-separated text -- a future
    operator can re-derive it from the integrity record without
    running this code.
    """
    envelope_lines = [
        f"chain_version={int(chain_version)}",
        f"sequence_number={int(sequence_number)}",
        f"audit_log_id={audit_log_id or ''}",
        f"prev_hash={prev_hash or GENESIS_PREV_HASH}",
        f"canonical_payload_hash={canonical_payload_hash or ''}",
    ]
    envelope = "\n".join(envelope_lines)
    return hashlib.sha256(envelope.encode("utf-8")).hexdigest()


__all__ = [
    "GENESIS_PREV_HASH",
    "compute_payload_hash",
    "compute_row_hash",
]
