"""Step 63A -- controlled production rollout pilot go/no-go review constants."""

from __future__ import annotations

REC_GO = "go"
REC_CONDITIONAL_GO = "conditional_go"
REC_NO_GO = "no_go"
RECOMMENDATIONS = (REC_GO, REC_CONDITIONAL_GO, REC_NO_GO)

# The hard gates whose absence forces no_go.
HARD_NO_GO_GATES = (
    "production_target",
    "production_credentials",
    "production_gitops",
    "production_approval_channel",
)
