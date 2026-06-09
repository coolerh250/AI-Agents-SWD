"""Stage 36 -- streamed sha256 + verify_sha256."""

from __future__ import annotations

from pathlib import Path

import pytest

from shared.sdk.backup import compute_sha256, verify_sha256


def _write(tmp_path: Path, name: str, body: bytes) -> Path:
    p = tmp_path / name
    p.write_bytes(body)
    return p


def test_compute_sha256_matches_known_value(tmp_path):
    p = _write(tmp_path, "a.bin", b"hello")
    # SHA-256("hello") -- precomputed.
    assert compute_sha256(p) == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"


def test_compute_sha256_streams_large_input(tmp_path):
    p = _write(tmp_path, "big.bin", b"x" * (3 * 1024 * 1024 + 7))
    digest = compute_sha256(p)
    assert len(digest) == 64
    assert digest == digest.lower()


def test_verify_sha256_detects_tamper(tmp_path):
    p = _write(tmp_path, "ok.bin", b"backup-bytes")
    digest = compute_sha256(p)
    assert verify_sha256(p, digest) is True
    p.write_bytes(b"backup-bytes-but-modified")
    assert verify_sha256(p, digest) is False


def test_verify_sha256_empty_expected_returns_false(tmp_path):
    p = _write(tmp_path, "a.bin", b"hello")
    assert verify_sha256(p, "") is False


def test_compute_sha256_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        compute_sha256(tmp_path / "missing.bin")
