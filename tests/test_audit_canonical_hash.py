"""Stage 34 -- canonical payload + hash determinism tests.

Pure-module tests, no I/O. They lock in the hash invariants that the
verifier relies on: identical payloads => identical hashes regardless
of dict-key order; any payload mutation flips the hash; the row_hash
depends on prev_hash so re-ordering breaks the chain.
"""

from __future__ import annotations

from datetime import datetime, timezone

from shared.sdk.audit_integrity import (
    GENESIS_PREV_HASH,
    build_canonical_payload,
    canonical_json,
    compute_payload_hash,
    compute_row_hash,
)


def _row():
    return {
        "id": "audit-1",
        "task_id": "T-1",
        "agent": "qa-agent",
        "decision_type": "qa_validation",
        "summary": "ok",
        "result": "passed",
        "artifact_refs": {"b": 1, "a": [2, 1]},
        "created_at": datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc),
    }


def test_canonical_payload_sorts_artifact_refs():
    payload = build_canonical_payload(_row())
    refs = payload["artifact_refs"]
    assert list(refs.keys()) == ["a", "b"]
    assert payload["audit_log_id"] == "audit-1"
    assert payload["created_at"].endswith("+00:00")


def test_canonical_json_deterministic_regardless_of_input_order():
    p1 = build_canonical_payload(_row())
    row_b = _row()
    row_b["artifact_refs"] = {"a": [2, 1], "b": 1}  # different insertion order
    p2 = build_canonical_payload(row_b)
    assert canonical_json(p1) == canonical_json(p2)
    assert compute_payload_hash(p1) == compute_payload_hash(p2)


def test_changed_payload_changes_payload_hash():
    base = build_canonical_payload(_row())
    h_base = compute_payload_hash(base)
    mutated = _row()
    mutated["summary"] = "ok (modified)"
    h_mut = compute_payload_hash(build_canonical_payload(mutated))
    assert h_base != h_mut


def test_row_hash_depends_on_prev_hash():
    payload = build_canonical_payload(_row())
    payload_hash = compute_payload_hash(payload)
    h_a = compute_row_hash(
        chain_version=1,
        sequence_number=2,
        audit_log_id="audit-1",
        prev_hash="abcd",
        canonical_payload_hash=payload_hash,
    )
    h_b = compute_row_hash(
        chain_version=1,
        sequence_number=2,
        audit_log_id="audit-1",
        prev_hash="abce",
        canonical_payload_hash=payload_hash,
    )
    assert h_a != h_b


def test_row_hash_first_row_uses_genesis_when_prev_hash_missing():
    payload = build_canonical_payload(_row())
    payload_hash = compute_payload_hash(payload)
    h_genesis = compute_row_hash(
        chain_version=1,
        sequence_number=1,
        audit_log_id="audit-1",
        prev_hash=None,
        canonical_payload_hash=payload_hash,
    )
    h_explicit = compute_row_hash(
        chain_version=1,
        sequence_number=1,
        audit_log_id="audit-1",
        prev_hash=GENESIS_PREV_HASH,
        canonical_payload_hash=payload_hash,
    )
    assert h_genesis == h_explicit


def test_canonical_payload_accepts_json_string_artifact_refs():
    row = _row()
    row["artifact_refs"] = '{"b": 1, "a": [2, 1]}'
    payload = build_canonical_payload(row)
    assert list(payload["artifact_refs"].keys()) == ["a", "b"]


def test_canonical_json_excludes_volatile_integrity_fields():
    # Even if a caller accidentally passes integrity-only fields, they
    # must not influence the canonical payload (we only project the
    # whitelisted CANONICAL_FIELDS).
    row = _row()
    row["integrity_id"] = "should-not-influence"
    row["row_hash"] = "should-not-influence"
    row["hmac_signature"] = "should-not-influence"
    text = canonical_json(build_canonical_payload(row))
    assert "integrity_id" not in text
    assert "row_hash" not in text
    assert "hmac_signature" not in text
