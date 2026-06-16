# Verification Rerun Runbook (Stage 52)

Operators (and platform_admins) may rerun **allowlisted** verifications through
the governed action API. No custom command, path, or argument is ever accepted.

## Allowlisted script keys (static server-side map)

| key                              | script                                          |
| -------------------------------- | ----------------------------------------------- |
| `delivery_package_acceptance_gate` | scripts/verify_delivery_package_acceptance_gate.sh |
| `admin_console_v0`               | scripts/verify_admin_console_v0.sh              |
| `backup_dr_gap_closure`          | scripts/verify_backup_dr_gap_closure.sh         |
| `audit_integrity`                | scripts/verify_tamper_evident_audit.sh          |
| `full_regression`                | scripts/run_full_regression.sh --full --json-report |

## Safety (`shared/sdk/operator_actions/verification_runner.py`)

- `shell=False`, fixed argv (`["bash", <contained script>, <fixed args>]`).
- realpath containment: the resolved script must live under `<repo>/scripts`.
- fixed cwd (repo root), sanitized environment (small allowlist of vars).
- timeout (default 1800s) with child-process group; output captured,
  size-capped, and **redacted** (tokens/secrets/keys → `***REDACTED***`) before
  persistence.
- only summary / marker / report path / exit code are stored
  (`verification_rerun_requests`). No raw secret output. No real external
  delivery. No production action.
- `full_regression` requires a higher confirmation (`high_risk_ack`).

## Limitation

Heavy verifications that need Docker / the full repo (most of the allowlist)
must run on a runner with that access. The orchestrator container ships the
scripts for path-resolution + governance; executing Docker-dependent verifies
from inside the container is a documented non-production limitation — the SDK
runner + verify script exercise them on the host.
