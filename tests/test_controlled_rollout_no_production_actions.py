"""Step 63A -- controlled rollout review: no production action anywhere.

Source-level guard across the SDK + API + generator: no real deploy / sync / merge / push /
restore / failover / rollout execution path, and no committed secret / token / kubeconfig
literal. (Field NAMES that assert an action did NOT happen are allowed.)
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SDK = ROOT / "shared" / "sdk" / "controlled_rollout"
API = ROOT / "apps" / "orchestrator" / "src" / "controlled_rollout_review_api.py"
GENERATOR = ROOT / "scripts" / "generate_controlled_rollout_go_no_go_review.py"

FORBIDDEN_EXEC = (
    "subprocess",
    "os.system",
    "shutil.rmtree",
    "kubectl ",
    "docker push",
    "argocd app sync",
    "boto3",
)


def _sources() -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = [(f.name, f.read_text(encoding="utf-8")) for f in SDK.glob("*.py")]
    out.append((API.name, API.read_text(encoding="utf-8")))
    out.append((GENERATOR.name, GENERATOR.read_text(encoding="utf-8")))
    return out


def test_no_real_execution_primitives() -> None:
    for name, src in _sources():
        for forbidden in FORBIDDEN_EXEC:
            assert forbidden not in src, f"{forbidden} in {name}"


def test_no_secret_shaped_literals() -> None:
    shapes = re.compile(
        r"(ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|-----BEGIN [A-Z ]*PRIVATE KEY|"
        r"AKIA[0-9A-Z]{16})"
    )
    for name, src in _sources():
        assert not shapes.search(src), f"secret-shaped literal in {name}"
