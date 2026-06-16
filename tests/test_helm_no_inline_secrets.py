"""Step 51.1 -- chart sources contain no inline secret values."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHART = ROOT / "infra" / "kubernetes" / "charts" / "ai-agents-platform"

# Patterns that would indicate an inline secret VALUE (not a reference).
SECRET_VALUE_PATTERNS = [
    re.compile(r"password\s*:\s*['\"]?\S{4,}", re.IGNORECASE),
    re.compile(r"passwd\s*:\s*['\"]?\S{4,}", re.IGNORECASE),
    re.compile(r"api[_-]?key\s*:\s*['\"]?\S{4,}", re.IGNORECASE),
    re.compile(r"secret[_-]?key\s*:\s*['\"]?\S{4,}", re.IGNORECASE),
    re.compile(r"BEGIN [A-Z ]*PRIVATE KEY"),
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]+"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
]

# secretKeyRef references are allowed; they expose a KEY name, never a value.
ALLOWED_SUBSTRINGS = ("secretKeyRef", "existingSecret", "secretRefs", "commonSecretRefs")


def _chart_files() -> list[Path]:
    files: list[Path] = []
    for ext in ("*.yaml", "*.yml", "*.json", "*.tpl"):
        files.extend(CHART.rglob(ext))
    return files


def test_no_inline_secret_values_in_chart() -> None:
    for path in _chart_files():
        text = path.read_text(encoding="utf-8")
        for line in text.splitlines():
            if any(tok in line for tok in ALLOWED_SUBSTRINGS):
                continue
            for pat in SECRET_VALUE_PATTERNS:
                assert not pat.search(line), f"{path.name}: {line.strip()!r}"


def test_chart_never_creates_secret_resource() -> None:
    for path in CHART.rglob("*.yaml"):
        text = path.read_text(encoding="utf-8")
        # template/manifest level: no `kind: Secret`
        assert not re.search(r"kind:\s*Secret\b", text), path.name
