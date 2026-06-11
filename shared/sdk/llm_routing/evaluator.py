"""Stage 38 -- pure helpers shared by the router + tests.

This module is intentionally free of I/O: it contains the request
builder and a few small predicates the router uses while evaluating
a capability request against a registry entry. The router consumes
these helpers; tests import them directly to pin behaviour.
"""

from __future__ import annotations

from .models import (
    AGENT_DEFAULT_TASK_TYPE,
    LLMCapabilityRequest,
    LLMModelEntry,
)


def build_capability_request(
    *,
    agent_name: str,
    capability: str,
    task_id: str | None = None,
    workflow_id: str | None = None,
    task_type: str = AGENT_DEFAULT_TASK_TYPE,
    execution_mode: str | None = None,
    risk_level: str = "low",
    requested_schema: str | None = None,
    requested_model_alias: str | None = None,
    estimated_input_tokens: int = 0,
    max_output_tokens: int | None = None,
    max_cost_usd: float | None = None,
    allow_real_llm_requested: bool = False,
    allow_patch_generation_requested: bool = False,
    allow_workspace_write_requested: bool = False,
    data_sensitivity: str = "internal",
    metadata: dict | None = None,
) -> LLMCapabilityRequest:
    return LLMCapabilityRequest(
        agent_name=agent_name,
        capability=capability,
        task_id=task_id,
        workflow_id=workflow_id,
        task_type=task_type,
        execution_mode=execution_mode,
        risk_level=risk_level,
        data_sensitivity=data_sensitivity,
        requested_schema=requested_schema,
        requested_model_alias=requested_model_alias,
        estimated_input_tokens=int(estimated_input_tokens or 0),
        max_output_tokens=max_output_tokens,
        max_cost_usd=max_cost_usd,
        allow_real_llm_requested=bool(allow_real_llm_requested),
        allow_patch_generation_requested=bool(allow_patch_generation_requested),
        allow_workspace_write_requested=bool(allow_workspace_write_requested),
        metadata=dict(metadata or {}),
    )


def capability_supported(entry: LLMModelEntry, capability: str) -> bool:
    return capability in (entry.capabilities or ())


def schema_supported(entry: LLMModelEntry, schema: str | None) -> bool:
    """Return True if the schema is missing OR explicitly supported.

    A missing schema is treated as "no schema constraint" so callers
    that don't care about a specific schema still route. Callers
    that need a specific schema pass it explicitly.
    """

    if not schema:
        return True
    return schema in (entry.supported_schemas or ())


def estimate_cost_usd(
    entry: LLMModelEntry,
    *,
    input_tokens: int,
    output_tokens: int,
) -> float:
    input_cost = (max(int(input_tokens or 0), 0) / 1000.0) * float(
        entry.cost_per_1k_input_tokens or 0.0
    )
    output_cost = (max(int(output_tokens or 0), 0) / 1000.0) * float(
        entry.cost_per_1k_output_tokens or 0.0
    )
    return round(input_cost + output_cost, 6)
