"""Step 55 -- safe non-production cluster detection helper.

Returns a (available, safe, reason) tuple WITHOUT printing any kubeconfig / token /
cert / context name. Used by the runtime smoke verifiers to decide PASS vs
BLOCKED_NO_SAFE_CLUSTER. It never deploys, installs, or mutates anything.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


def detect_cluster() -> tuple[bool, bool, str]:
    """(available, safe, reason). Reason is a fixed, secret-free token."""
    if shutil.which("kubectl") is None:
        return (False, False, "kubectl_not_available")
    if shutil.which("helm") is None:
        return (False, False, "helm_not_available")
    kubeconfig = os.environ.get("KUBECONFIG") or str(Path.home() / ".kube" / "config")
    if not Path(kubeconfig).is_file():
        return (False, False, "no_kubeconfig")
    try:
        ctx = subprocess.run(  # noqa: S603
            ["kubectl", "config", "current-context"],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return (False, False, "kubectl_error")
    if ctx.returncode != 0 or not ctx.stdout.strip():
        return (False, False, "no_current_context")
    name = ctx.stdout.strip().lower()
    if "prod" in name or "production" in name:
        # A production-like context is detected but MUST NOT be used.
        return (True, False, "production_like_context")
    try:
        info = subprocess.run(  # noqa: S603
            ["kubectl", "cluster-info"],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return (False, False, "cluster_unreachable")
    if info.returncode != 0:
        return (False, False, "cluster_unreachable")
    return (True, True, "safe_nonproduction_cluster")
