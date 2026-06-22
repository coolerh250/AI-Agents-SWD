"""Step 51.4 -- read-only Kubernetes / Helm / GitOps runtime baseline aggregation.

Pure, read-only, secret-free. Aggregates the COMMITTED Step 51 static baseline
(inventories, catalogs, chart values, GitOps manifests) into a redacted summary
for the read-only operations API + /operations/safety + the Admin Console runtime
view. It NEVER connects to a cluster, runs a verifier, or applies a manifest.
"""

from __future__ import annotations

from shared.sdk.runtime_baseline.collector import (
    RUNTIME_BASELINE_MARKERS,
    build_runtime_baseline_summary,
    collect_runtime_baseline,
    load_runtime_baseline_summary,
)
from shared.sdk.runtime_baseline.safety import runtime_baseline_safety_fields

__all__ = [
    "RUNTIME_BASELINE_MARKERS",
    "build_runtime_baseline_summary",
    "collect_runtime_baseline",
    "load_runtime_baseline_summary",
    "runtime_baseline_safety_fields",
]
