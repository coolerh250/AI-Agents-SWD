#!/usr/bin/env python3
"""Stage 26 secrets inventory lister.

Reads ``infra/runtime/secrets.inventory.yml`` and prints a per-secret
summary. NEVER prints a secret value — the inventory file itself never
contains one; this script only echoes names, providers, and posture
booleans.

Usage:
    ./scripts/list_required_secrets.py
    ./scripts/list_required_secrets.py --json
    ./scripts/list_required_secrets.py --env staging

Exit code is 0 when every required secret has the right shape (a name,
a provider per environment, a leak_risk band). The "value is missing"
check is the validator's job — this script only validates the inventory
file's structure.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
INVENTORY_PATH = REPO_ROOT / "infra" / "runtime" / "secrets.inventory.yml"

REQUIRED_FIELDS = (
    "name",
    "required_for",
    "environments",
    "provider",
    "rotation_policy",
    "allowed_to_be_missing_in_local",
    "allowed_to_be_missing_in_staging",
    "leak_risk",
)

ALLOWED_LEAK_RISK = {"low", "medium", "high", "critical"}
ALLOWED_PROVIDERS = {"env", "vault", "mock-vault"}


def _load(path: Path) -> dict[str, Any]:
    try:
        import yaml  # type: ignore
    except ImportError:  # pragma: no cover
        sys.stderr.write("PyYAML not installed — pip install pyyaml\n")
        raise SystemExit(2)
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _validate_entry(entry: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    for field in REQUIRED_FIELDS:
        if field not in entry:
            failures.append(f"missing field: {field}")
    if "leak_risk" in entry and entry["leak_risk"] not in ALLOWED_LEAK_RISK:
        failures.append(f"leak_risk {entry['leak_risk']!r} not in {sorted(ALLOWED_LEAK_RISK)}")
    provider = entry.get("provider")
    if isinstance(provider, dict):
        for env_name, prov in provider.items():
            if prov not in ALLOWED_PROVIDERS:
                failures.append(f"provider.{env_name}={prov!r} not in {sorted(ALLOWED_PROVIDERS)}")
    elif provider is not None:
        failures.append("provider must be a per-environment mapping")
    return failures


def _format_row(entry: dict[str, Any], env_filter: str | None) -> str:
    name = entry.get("name", "?")
    provider_map = entry.get("provider", {}) or {}
    provider_for_env = provider_map.get(env_filter, "-") if env_filter else "-"
    return (
        f"  {name:<28} "
        f"leak_risk={entry.get('leak_risk', '?'):<8} "
        f"rotation={entry.get('rotation_policy', '?'):<10} "
        f"provider[{env_filter or 'all'}]={provider_for_env}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Stage 26 secrets inventory lister")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of the text table.")
    parser.add_argument(
        "--env",
        choices=["local", "staging", "production"],
        default=None,
        help="Filter the provider column to one environment.",
    )
    args = parser.parse_args(argv)

    doc = _load(INVENTORY_PATH)
    secrets = doc.get("secrets") or []
    if not isinstance(secrets, list):
        sys.stderr.write("inventory missing top-level `secrets` list\n")
        return 1

    failures: list[str] = []
    for entry in secrets:
        if not isinstance(entry, dict):
            failures.append(f"entry not a mapping: {entry!r}")
            continue
        failures.extend(f"{entry.get('name', '?')}: {f}" for f in _validate_entry(entry))

    if args.json:
        out = {
            "inventory_path": str(INVENTORY_PATH.relative_to(REPO_ROOT)),
            "count": len(secrets),
            "secrets": [
                {
                    "name": entry.get("name"),
                    "required_for": entry.get("required_for"),
                    "environments": entry.get("environments"),
                    "provider": entry.get("provider"),
                    "leak_risk": entry.get("leak_risk"),
                    "rotation_policy": entry.get("rotation_policy"),
                    "allowed_to_be_missing_in_local": entry.get("allowed_to_be_missing_in_local"),
                    "allowed_to_be_missing_in_staging": entry.get(
                        "allowed_to_be_missing_in_staging"
                    ),
                }
                for entry in secrets
                if isinstance(entry, dict)
            ],
            "failures": failures,
            "passed": not failures,
        }
        print(json.dumps(out, indent=2))
    else:
        print(f"### secrets inventory ({INVENTORY_PATH.relative_to(REPO_ROOT)})")
        print(f"  total: {len(secrets)} secret(s)")
        for entry in secrets:
            if isinstance(entry, dict):
                print(_format_row(entry, args.env))
        if failures:
            print()
            print("INVENTORY VALIDATION FAILURES:")
            for f in failures:
                print(f"  - {f}")
        print()
        print(
            "REQUIRED_SECRETS_INVENTORY: PASS"
            if not failures
            else "REQUIRED_SECRETS_INVENTORY: FAIL"
        )

    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
