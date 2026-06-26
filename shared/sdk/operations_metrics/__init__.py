"""Step 58 -- Admin Console v2 operational metrics (read-only aggregation)."""

from shared.sdk.operations_metrics.aggregator import build_snapshot
from shared.sdk.operations_metrics.safety import operational_metrics_safety_fields

__all__ = ["build_snapshot", "operational_metrics_safety_fields"]
