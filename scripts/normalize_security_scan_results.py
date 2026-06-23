#!/usr/bin/env python3
"""Step 54.2 -- normalize local scan reports into one redacted summary.

Reads the secret / SAST / dependency runtime reports (if present), runs them
through the SDK normalizer, and writes a unified redacted summary. A missing scan
is recorded as not_run (NEVER clean); tool_unavailable is preserved;
productionReady is always false. Summary is written to a runtime path (NEVER
committed).

Usage: python scripts/normalize_security_scan_results.py [--runtime-dir DIR]
                                                         [--summary PATH] [--run]
"""

from __future__ import annotations

import argparse
import json
import subprocess  # nosec: fixed argv, no shell, local runners only
import sys
from pathlib import Path
from typing import cast

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.sdk.security_findings import ScanResult, normalize, redact_report  # noqa: E402

DEFAULT_RUNTIME = ROOT / ".runtime" / "security"
REPORTS = {
    "secret": "secret-scan-report.json",
    "sast": "sast-scan-report.json",
    "dependency": "dependency-scan-report.json",
}
RUNNERS = {
    "secret": "run_local_secret_scan.py",
    "sast": "run_local_sast_scan.py",
    "dependency": "run_local_dependency_scan.py",
}


def _load(path: Path) -> ScanResult | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return ScanResult.model_validate(data)
    except Exception:  # noqa: BLE001
        return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runtime-dir", default=str(DEFAULT_RUNTIME))
    ap.add_argument("--summary", default="")
    ap.add_argument("--run", action="store_true", help="run the local scanners first")
    args = ap.parse_args()
    runtime = Path(args.runtime_dir)
    runtime.mkdir(parents=True, exist_ok=True)

    if args.run:
        for st, script in RUNNERS.items():
            subprocess.run(  # nosec: fixed argv, no shell
                [
                    sys.executable,
                    str(ROOT / "scripts" / script),
                    "--quiet",
                    "--json-report",
                    str(runtime / REPORTS[st]),
                ],
                check=False,
            )

    results: dict[str, ScanResult | None] = {st: _load(runtime / fn) for st, fn in REPORTS.items()}
    summary = cast(dict, redact_report(normalize(results)))
    out = Path(args.summary) if args.summary else runtime / "security-scan-summary.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    print(
        f"normalized summary -> {out} "
        f"(production_ready={summary['production_ready']}, "
        f"not_ready_reasons={len(summary['not_ready_reasons'])})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
