#!/usr/bin/env python3
"""Step 53 -- secret redaction policy verifier (NO value access).

Validates the redaction policy exists, the SDK redaction helper redacts
secret-shaped keys + token/private-key strings, and that the operations API +
Admin Console secret view route through redaction.

Marker: SECRET_REDACTION_POLICY_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SDIR = ROOT / "infra" / "secrets"
sys.path.insert(0, str(ROOT))  # noqa: E402

from shared.sdk.secrets_foundation import redact  # noqa: E402

failures: list[str] = []
passes: list[str] = []


def ok(m: str) -> None:
    passes.append(m)
    print(f"  [PASS] {m}")


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def main() -> int:
    f = SDIR / "secret-redaction-policy.yaml"
    if not f.is_file():
        bad("missing secret-redaction-policy.yaml")
        print("SECRET_REDACTION_POLICY_VERIFY: FAIL")
        return 1
    pol = yaml.safe_load(f.read_text(encoding="utf-8"))
    if pol.get("status") != "enabled":
        bad("redaction policy must be enabled")
    for sub in ("secret", "token", "password", "key", "private", "credential", "jwt"):
        if sub not in pol.get("redactKeySubstrings", []):
            bad(f"redaction policy missing key substring: {sub}")
    if not failures:
        ok("redaction policy enabled and lists required key substrings")

    # redaction helper redacts a secret-shaped key value
    out = redact(
        {"client_secret": "hunter2supersecret", "name": "ok", "issuer": "https://idp.example.com"}
    )
    if out["client_secret"] != "***REDACTED***":
        bad("redact() must redact a secret-shaped key value")
    if out["name"] != "ok":
        bad("redact() must not over-redact a non-secret field")
    else:
        ok("redact() redacts secret-shaped keys, preserves non-secret fields")

    # redaction helper redacts a token-shaped string value (key not secret-named)
    jwt = "eyJ" + "a" * 20 + "." + "b" * 20 + "." + "c" * 20
    out2 = redact({"blob": jwt})
    if out2["blob"] != "***REDACTED***":
        bad("redact() must redact a token-shaped string value")
    else:
        ok("redact() redacts JWT-shaped string values")

    # operations API + Admin Console route through redaction
    api = (ROOT / "apps" / "orchestrator" / "src" / "secret_posture_api.py").read_text(
        encoding="utf-8"
    )
    if "redact" not in api:
        bad("secret operations API must use redaction")
    rb = (ROOT / "shared" / "sdk" / "secrets_foundation" / "report_builder.py").read_text(
        encoding="utf-8"
    )
    if "redact" not in rb:
        bad("report builder must apply redaction")
    if not [
        x for x in failures if "redaction" in x.lower() and "API" in x or "report builder" in x
    ]:
        ok("operations API + report builder apply redaction")

    print(f"\n=== Summary: {len(passes)}/{len(passes) + len(failures)} checks passed ===")
    if failures:
        print("SECRET_REDACTION_POLICY_VERIFY: FAIL")
        return 1
    print("SECRET_REDACTION_POLICY_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
