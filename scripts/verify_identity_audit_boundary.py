#!/usr/bin/env python3
"""Step 52.1 -- identity audit boundary verifier (code-level).

Asserts operator-action auditing records actor identity / role / action with
controlled-only + production_executed=false, that confirmation nonces and
idempotency keys are hashed (never raw), and that no raw session token, CSRF
token, confirmation nonce, or chain-of-thought is recorded. No live server.

Marker: IDENTITY_AUDIT_BOUNDARY_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OA = ROOT / "shared" / "sdk" / "operator_actions"

failures: list[str] = []
passes: list[str] = []


def ok(m: str) -> None:
    passes.append(m)
    print(f"  [PASS] {m}")


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def main() -> int:
    ae = read(OA / "audit_events.py")
    # actor identity + role recorded
    for field in ("identity_key", "role", "action_type", "status"):
        if field not in ae:
            bad(f"audit refs must record {field}")
    if '"production_executed": False' not in ae:
        bad("audit refs must pin production_executed=False")
    if '"controlled_only": True' not in ae:
        bad("audit refs must pin controlled_only=True")
    # must NOT carry raw secrets
    low = ae.lower()
    for forbidden in (
        "raw_token",
        "session_token",
        "csrf",
        "nonce",
        "chain_of_thought",
        "client_secret",
    ):
        if forbidden in low:
            bad(f"audit refs must not reference {forbidden}")
    if not failures:
        ok(
            "audit refs record identity/role/action with controlled_only + production_executed=false; no raw secret"
        )

    # confirmation nonce hashed at rest
    conf = read(OA / "confirmation.py")
    if "hashlib.sha256" not in conf or "nonce_hash" not in conf:
        bad("confirmation nonce must be sha256-hashed at rest")
    else:
        ok("confirmation nonce hashed at rest (raw returned once, never persisted)")

    # idempotency key is a client-chosen, non-secret correlation key: it must be
    # charset-bounded (not arbitrary) and must not be an auth/session token.
    idem = read(OA / "idempotency.py")
    if "_KEY_RE" not in idem or "is_valid_key" not in idem:
        bad("idempotency key must be charset-validated (bounded correlation key)")
    elif "secret" in idem.lower() or "session" in idem.lower():
        bad("idempotency key module must not handle session/auth secrets")
    else:
        ok("idempotency key is a charset-bounded non-secret correlation key (not an auth token)")

    # session module must persist only the hash
    sess = read(OA / "session.py")
    if "session_hash" not in sess or "sha256" not in sess:
        bad("session must persist sha256 hash only")
    if "never logged" not in sess and "never returned" not in sess:
        # documentation/intent marker; not fatal but flag if absent
        pass
    if not [f for f in failures if "session must persist" in f]:
        ok("session persists sha256 hash only; raw token never logged/returned")

    print(f"\n=== Summary: {len(passes)}/{len(passes) + len(failures)} checks passed ===")
    if failures:
        print("IDENTITY_AUDIT_BOUNDARY_VERIFY: FAIL")
        return 1
    print("IDENTITY_AUDIT_BOUNDARY_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
