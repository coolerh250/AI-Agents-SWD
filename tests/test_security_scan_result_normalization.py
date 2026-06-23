"""Step 54.2 -- normalize script + SDK produce a redacted unified summary."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _norm_script():
    spec = importlib.util.spec_from_file_location(
        "_normalize", ROOT / "scripts" / "normalize_security_scan_results.py"
    )
    assert spec and spec.loader
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_normalize_writes_redacted_summary(tmp_path: Path) -> None:
    import sys

    m = _norm_script()
    out = tmp_path / "summary.json"
    argv = sys.argv
    sys.argv = ["normalize", "--runtime-dir", str(tmp_path), "--summary", str(out), "--run"]
    try:
        rc = m.main()
    finally:
        sys.argv = argv
    assert rc == 0
    assert out.is_file()
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["production_ready"] is False
    assert set(data["scan_types"]) == {"secret", "sast", "dependency"}
    # all three scans ran (custom baselines available)
    for st in ("secret", "sast", "dependency"):
        assert data["per_type"][st]["status"] != "not_run"


def test_summary_has_no_raw_credential(tmp_path: Path) -> None:
    import re
    import sys

    m = _norm_script()
    out = tmp_path / "summary.json"
    argv = sys.argv
    sys.argv = ["normalize", "--runtime-dir", str(tmp_path), "--summary", str(out), "--run"]
    try:
        m.main()
    finally:
        sys.argv = argv
    text = out.read_text(encoding="utf-8")
    assert not re.search(r"(ghp_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|BEGIN [A-Z ]*PRIVATE KEY)", text)
