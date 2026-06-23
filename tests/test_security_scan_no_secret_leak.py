"""Step 54.2 -- scan reports never leak a raw credential value."""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = re.compile(
    r"(ghp_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|"
    r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{6,}|BEGIN [A-Z ]*PRIVATE KEY|"
    r"sk-[A-Za-z0-9]{20,})"
)


def _run(script: str):
    spec = importlib.util.spec_from_file_location(f"_{script}", ROOT / "scripts" / f"{script}.py")
    assert spec and spec.loader
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m.run()


def test_secret_report_no_raw_credential() -> None:
    text = json.dumps(_run("run_local_secret_scan").model_dump(), default=str)
    assert not RAW.search(text)


def test_sast_report_no_raw_credential() -> None:
    text = json.dumps(_run("run_local_sast_scan").model_dump(), default=str)
    assert not RAW.search(text)


def test_dependency_report_no_raw_credential() -> None:
    text = json.dumps(_run("run_local_dependency_scan").model_dump(), default=str)
    assert not RAW.search(text)
