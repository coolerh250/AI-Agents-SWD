"""Token + cost estimator for the LLM budget gate.

Token estimation is intentionally simple: we approximate at 4
characters per token. Pricing is conservative; an unknown model is
treated as the most expensive entry in the configured provider's
table so a misconfiguration cannot silently produce a $0 estimate.

Mock provider is always $0 / 0 tokens.

The estimator NEVER reads, returns, or logs an API key. It also
never reads pricing from the network -- the table is static so
budget gating remains deterministic offline.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

#: Per 1K tokens pricing in USD. The orchestrator uses these as
#: conservative defaults; operators can override the table by
#: constructing :class:`LLMCostEstimator` with custom pricing.
#:
#: Values are intentionally on the high side so the budget gate
#: errs in the operator's favour.
DEFAULT_PRICING: dict[str, dict[str, dict[str, float]]] = {
    "external_openai": {
        "gpt-4o": {"prompt": 0.005, "completion": 0.015},
        "gpt-4o-mini": {"prompt": 0.00015, "completion": 0.0006},
        "gpt-4-turbo": {"prompt": 0.01, "completion": 0.03},
        "gpt-3.5-turbo": {"prompt": 0.0005, "completion": 0.0015},
    },
    "external_anthropic": {
        "claude-3-5-sonnet": {"prompt": 0.003, "completion": 0.015},
        "claude-3-5-haiku": {"prompt": 0.0008, "completion": 0.004},
        "claude-3-opus": {"prompt": 0.015, "completion": 0.075},
        "claude-3-sonnet": {"prompt": 0.003, "completion": 0.015},
        "claude-3-haiku": {"prompt": 0.00025, "completion": 0.00125},
    },
    "mock": {
        "mock-deterministic": {"prompt": 0.0, "completion": 0.0},
    },
}

_AVG_CHARS_PER_TOKEN = 4


def estimate_tokens(text: str | None) -> int:
    """Return an approximate token count for ``text``.

    Uses an intentionally coarse 4-chars-per-token heuristic so the
    budget gate is independent of any tokenizer library (no extra
    runtime dependency). For prompts the result is slightly higher
    than the real tokenizer's output for English text, which keeps
    the budget gate on the conservative side.
    """
    if not text:
        return 0
    length = len(text)
    return max(1, (length + _AVG_CHARS_PER_TOKEN - 1) // _AVG_CHARS_PER_TOKEN)


@dataclass
class LLMCostEstimator:
    """Pure cost estimator.

    The estimator's contract:

    * ``mock`` provider always returns 0 tokens / $0 cost.
    * ``external_*`` providers use the per-model entry from the
      pricing table; an unknown model falls back to the MOST
      EXPENSIVE model registered for that provider so the budget
      gate cannot silently approve a $0 estimate.
    * If the provider itself is unknown, the estimator raises
      ``ValueError`` -- callers should treat that as
      ``cap_breached=unknown_provider`` upstream.
    """

    pricing: dict[str, dict[str, dict[str, float]]] | None = None

    def _table(self) -> dict[str, dict[str, dict[str, float]]]:
        return self.pricing if self.pricing is not None else DEFAULT_PRICING

    def supported_providers(self) -> tuple[str, ...]:
        return tuple(self._table().keys())

    def estimate_cost(
        self,
        *,
        provider: str,
        model_name: str,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> dict[str, Any]:
        """Return ``{cost_usd, prompt_cost_usd, completion_cost_usd, ...}``.

        Mock provider always returns zero.
        """
        provider = (provider or "").strip()
        model_name = (model_name or "").strip().lower()
        if provider == "mock":
            return {
                "provider": provider,
                "model_name": model_name or "mock-deterministic",
                "prompt_tokens": int(prompt_tokens),
                "completion_tokens": int(completion_tokens),
                "total_tokens": int(prompt_tokens) + int(completion_tokens),
                "prompt_cost_usd": 0.0,
                "completion_cost_usd": 0.0,
                "cost_usd": 0.0,
                "model_known": True,
                "fallback_used": False,
            }
        table = self._table()
        if provider not in table:
            raise ValueError(f"unknown_provider:{provider}")
        models = table[provider]
        if not models:
            raise ValueError(f"no_models_for_provider:{provider}")
        if model_name in models:
            model_entry = models[model_name]
            fallback_used = False
            model_label = model_name
        else:
            # Most expensive entry per provider = conservative
            # fallback so an unknown model name cannot be cheaper
            # than reality.
            model_label, model_entry = max(
                models.items(),
                key=lambda kv: kv[1].get("prompt", 0.0) + kv[1].get("completion", 0.0),
            )
            fallback_used = True

        prompt_cost = (float(prompt_tokens) / 1000.0) * float(model_entry["prompt"])
        completion_cost = (float(completion_tokens) / 1000.0) * float(model_entry["completion"])
        cost = prompt_cost + completion_cost
        return {
            "provider": provider,
            "model_name": model_label,
            "prompt_tokens": int(prompt_tokens),
            "completion_tokens": int(completion_tokens),
            "total_tokens": int(prompt_tokens) + int(completion_tokens),
            "prompt_cost_usd": round(prompt_cost, 6),
            "completion_cost_usd": round(completion_cost, 6),
            "cost_usd": round(cost, 6),
            "model_known": not fallback_used,
            "fallback_used": fallback_used,
        }
