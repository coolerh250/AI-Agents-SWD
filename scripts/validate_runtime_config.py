#!/usr/bin/env python3
"""Stage 24 runtime config validator.

Reads the live process environment (or a ``--env-file``) and applies the
per-mode rules pinned in ``infra/runtime/runtime-config.schema.json``.

Modes:

* ``local``  — current local/test cluster. Trust-auth, Vault dev mode,
  null-receiver tolerated. Real GitHub / Discord tests must be off by
  default.
* ``staging`` — no trust-auth, no placeholder secrets in required
  fields, Vault dev mode only with explicit
  ``ALLOW_VAULT_DEV_MODE_FOR_STAGING=true`` escape hatch.
* ``production-check`` — read-only audit pass. No trust-auth, no Vault
  dev mode, no null-receiver, and (when DB credentials are available)
  ``production_executed=true`` count must be ``0``. The validator never
  writes; it only reports.

The validator NEVER prints secret values. Findings reference variable
names only; the boolean ``present`` flag tells the operator whether a
secret is configured. Exit code is 0 (PASS) or 1 (FAIL).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "infra" / "runtime" / "runtime-config.schema.json"

# Mirror the placeholder marker the secrets SDK uses. Imported lazily so
# the script remains usable without the in-repo SDK on sys.path.
PLACEHOLDER_MARKER = "PLACEHOLDER_DO_NOT_COMMIT_REAL_VALUE"

SECRET_FIELDS = (
    "POSTGRES_PASSWORD",
    "VAULT_TOKEN",
    "GITHUB_TOKEN",
    "DISCORD_BOT_TOKEN",
    "ALERTMANAGER_WEBHOOK_URL",
)


@dataclass
class Finding:
    code: str
    message: str
    severity: str = "fail"  # fail | warn | info
    field: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity,
            "field": self.field,
        }


@dataclass
class Report:
    mode: str
    env_keys_present: list[str] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)

    def add(self, finding: Finding) -> None:
        self.findings.append(finding)

    @property
    def passed(self) -> bool:
        return not any(f.severity == "fail" for f in self.findings)

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "passed": self.passed,
            "findings": [f.to_dict() for f in self.findings],
            "env_keys_observed": sorted(set(self.env_keys_present)),
        }


# ---------------------------------------------------------------------------
# env loading
# ---------------------------------------------------------------------------


def _load_env_file(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        out[key.strip()] = value.strip()
    return out


def _gather_env(env_file: Path | None) -> dict[str, str]:
    snapshot = dict(os.environ)
    if env_file is not None:
        # Values from --env-file take precedence so tests can pin a
        # deterministic shape without exporting variables first.
        snapshot.update(_load_env_file(env_file))
    return snapshot


# ---------------------------------------------------------------------------
# rules
# ---------------------------------------------------------------------------


def _is_truthy(value: str | None) -> bool:
    return (value or "").strip().lower() == "true"


def _is_placeholder(value: str | None) -> bool:
    if not value:
        return False
    return PLACEHOLDER_MARKER in value


def _looks_like_local_docker_vault(addr: str) -> bool:
    addr = (addr or "").strip()
    return addr in ("", "http://vault:8200", "http://localhost:8200")


def _check_real_test_defaults(env: dict[str, str], report: Report) -> None:
    # Both opt-in switches must default to false. Setting them to true
    # is an explicit escape hatch — the validator only flags it at
    # production-check.
    if _is_truthy(env.get("RUN_REAL_GITHUB_TEST")):
        report.add(
            Finding(
                code="real_github_test_opt_in",
                message=(
                    "RUN_REAL_GITHUB_TEST=true — the Stage 23 controlled-real GitHub "
                    "flow is enabled. Confirm GITHUB_TEST_REPO is set and the operator "
                    "is opted in deliberately."
                ),
                severity="info",
                field="RUN_REAL_GITHUB_TEST",
            )
        )
    if _is_truthy(env.get("RUN_REAL_DISCORD_TEST")):
        report.add(
            Finding(
                code="real_discord_test_opt_in",
                message=(
                    "RUN_REAL_DISCORD_TEST=true — the Stage 22 controlled-real "
                    "Discord delivery is enabled. Confirm DISCORD_TEST_CHANNEL_ID is set "
                    "and the operator is opted in deliberately."
                ),
                severity="info",
                field="RUN_REAL_DISCORD_TEST",
            )
        )


def _check_real_github_guard_consistency(env: dict[str, str], report: Report) -> None:
    real_on = _is_truthy(env.get("RUN_REAL_GITHUB_TEST"))
    if real_on and not env.get("GITHUB_TEST_REPO", "").strip():
        report.add(
            Finding(
                code="real_github_test_missing_repo",
                message=(
                    "RUN_REAL_GITHUB_TEST=true but GITHUB_TEST_REPO is empty. The Stage "
                    "23 safety guard will refuse every call until GITHUB_TEST_REPO is "
                    "set to the pinned sandbox repository."
                ),
                severity="fail",
                field="GITHUB_TEST_REPO",
            )
        )
    if real_on and not env.get("GITHUB_TOKEN", "").strip():
        report.add(
            Finding(
                code="real_github_test_missing_token",
                message=(
                    "RUN_REAL_GITHUB_TEST=true but GITHUB_TOKEN is empty. The Stage 23 "
                    "safety guard will refuse with reason=missing_github_token."
                ),
                severity="fail",
                field="GITHUB_TOKEN",
            )
        )


def _check_real_discord_guard_consistency(env: dict[str, str], report: Report) -> None:
    real_on = _is_truthy(env.get("RUN_REAL_DISCORD_TEST"))
    if real_on and not env.get("DISCORD_TEST_CHANNEL_ID", "").strip():
        report.add(
            Finding(
                code="real_discord_missing_channel",
                message=(
                    "RUN_REAL_DISCORD_TEST=true but DISCORD_TEST_CHANNEL_ID is empty. "
                    "The Stage 22 notification-worker will refuse every call."
                ),
                severity="fail",
                field="DISCORD_TEST_CHANNEL_ID",
            )
        )
    if real_on and not env.get("DISCORD_BOT_TOKEN", "").strip():
        report.add(
            Finding(
                code="real_discord_missing_token",
                message=(
                    "RUN_REAL_DISCORD_TEST=true but DISCORD_BOT_TOKEN is empty. "
                    "The Stage 22 notification-worker will refuse every call."
                ),
                severity="fail",
                field="DISCORD_BOT_TOKEN",
            )
        )


def _check_placeholders(env: dict[str, str], report: Report, *, fields: Iterable[str]) -> None:
    for key in fields:
        value = env.get(key)
        if _is_placeholder(value):
            report.add(
                Finding(
                    code="placeholder_secret",
                    message=(
                        f"{key} still carries the literal placeholder marker — "
                        "this is unsafe outside local mode."
                    ),
                    severity="fail",
                    field=key,
                )
            )


def _check_postgres_auth(env: dict[str, str], report: Report, *, mode: str) -> None:
    method = (env.get("POSTGRES_HOST_AUTH_METHOD") or "").strip().lower()
    if mode == "local":
        # trust is allowed (this is the existing docker-compose.yml).
        return
    if method == "trust":
        report.add(
            Finding(
                code="postgres_trust_auth_forbidden",
                message=(
                    "POSTGRES_HOST_AUTH_METHOD=trust is allowed only in local mode. "
                    "Staging / production-check require real auth."
                ),
                severity="fail",
                field="POSTGRES_HOST_AUTH_METHOD",
            )
        )
    password = (env.get("POSTGRES_PASSWORD") or "").strip()
    if not password or _is_placeholder(password):
        report.add(
            Finding(
                code="postgres_password_missing",
                message=(
                    "POSTGRES_PASSWORD must be set to a real value in "
                    f"{mode} mode (placeholder values are rejected)."
                ),
                severity="fail",
                field="POSTGRES_PASSWORD",
            )
        )


def _check_vault_mode(env: dict[str, str], report: Report, *, mode: str) -> None:
    vault_addr = (env.get("VAULT_ADDR") or "").strip()
    dev_addr = _looks_like_local_docker_vault(vault_addr)
    if mode == "local":
        return
    if dev_addr:
        allow = _is_truthy(env.get("ALLOW_VAULT_DEV_MODE_FOR_STAGING"))
        if mode == "staging" and allow:
            report.add(
                Finding(
                    code="vault_dev_mode_in_staging",
                    message=(
                        "Vault dev-mode is enabled in staging because "
                        "ALLOW_VAULT_DEV_MODE_FOR_STAGING=true. This is an "
                        "escape hatch — flip back to a real Vault server."
                    ),
                    severity="warn",
                    field="VAULT_ADDR",
                )
            )
        else:
            report.add(
                Finding(
                    code="vault_dev_mode_forbidden",
                    message=(
                        f"Vault address {vault_addr!r} points at the local dev "
                        "container. " + mode + " mode requires a real Vault server."
                    ),
                    severity="fail",
                    field="VAULT_ADDR",
                )
            )


def _check_alertmanager_receiver(env: dict[str, str], report: Report, *, mode: str) -> None:
    url = (env.get("ALERTMANAGER_WEBHOOK_URL") or "").strip()
    if mode == "production-check":
        # production-check: a null receiver is not enough — operators
        # are expected to wire a real webhook by this point.
        if not url or _is_placeholder(url):
            report.add(
                Finding(
                    code="alertmanager_receiver_missing",
                    message=(
                        "ALERTMANAGER_WEBHOOK_URL is empty/placeholder. The "
                        "production-check mode expects a configured webhook."
                    ),
                    severity="fail",
                    field="ALERTMANAGER_WEBHOOK_URL",
                )
            )
    # local / staging: null-receiver is the platform default. Nothing
    # to flag — Alertmanager config lives in
    # infra/observability/alertmanager/alertmanager.yml.


def _check_production_executed(env: dict[str, str], report: Report) -> None:
    """Cheap, deferred check the validator can run when DATABASE_URL is
    reachable. Only invoked for ``production-check`` mode. We don't
    actually open a connection here — that's the production_safety
    gate's job — but we look at a sentinel env var the gate writes.
    """
    sentinel = (env.get("PRODUCTION_EXECUTED_TRUE_COUNT") or "").strip()
    if sentinel and sentinel != "0":
        report.add(
            Finding(
                code="production_executed_true",
                message=(
                    f"PRODUCTION_EXECUTED_TRUE_COUNT={sentinel} — at least one "
                    "row reports production_executed=true. The platform must "
                    "stay at 0 unless a real production deploy was authorised."
                ),
                severity="fail",
                field="PRODUCTION_EXECUTED_TRUE_COUNT",
            )
        )


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------


def evaluate(mode: str, env: dict[str, str]) -> Report:
    report = Report(mode=mode, env_keys_present=list(env.keys()))
    if mode not in ("local", "staging", "production-check"):
        report.add(
            Finding(
                code="invalid_mode",
                message=f"unsupported mode {mode!r}",
                severity="fail",
            )
        )
        return report

    _check_real_test_defaults(env, report)
    _check_real_github_guard_consistency(env, report)
    _check_real_discord_guard_consistency(env, report)

    if mode == "local":
        # local mode tolerates dev-mode Vault / trust-auth / null-receiver.
        # Only the real-test guard consistency checks above run.
        return report

    if mode == "staging":
        _check_placeholders(env, report, fields=("POSTGRES_PASSWORD",))
        _check_postgres_auth(env, report, mode=mode)
        _check_vault_mode(env, report, mode=mode)
        _check_alertmanager_receiver(env, report, mode=mode)
        return report

    if mode == "production-check":
        _check_placeholders(env, report, fields=SECRET_FIELDS)
        _check_postgres_auth(env, report, mode=mode)
        _check_vault_mode(env, report, mode=mode)
        _check_alertmanager_receiver(env, report, mode=mode)
        _check_production_executed(env, report)
        return report

    return report


def _render_text(report: Report) -> str:
    lines = [f"RUNTIME_CONFIG_VALIDATION_MODE={report.mode}"]
    for finding in report.findings:
        marker = {"fail": "FAIL", "warn": "WARN", "info": "INFO"}[finding.severity]
        field_part = f" field={finding.field}" if finding.field else ""
        lines.append(f"  {marker} [{finding.code}]{field_part}: {finding.message}")
    lines.append("")
    lines.append(
        "RUNTIME_CONFIG_VALIDATION: PASS" if report.passed else "RUNTIME_CONFIG_VALIDATION: FAIL"
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Stage 24 runtime config validator")
    parser.add_argument("--mode", required=True, choices=["local", "staging", "production-check"])
    parser.add_argument(
        "--env-file",
        type=Path,
        default=None,
        help="Optional path to a `.env` file whose values override os.environ.",
    )
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default text).",
    )
    args = parser.parse_args(argv)

    env = _gather_env(args.env_file)
    report = evaluate(args.mode, env)

    if args.format == "json":
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(_render_text(report))

    return 0 if report.passed else 1


if __name__ == "__main__":
    sys.exit(main())
