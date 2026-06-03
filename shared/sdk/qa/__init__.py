"""Stage 29 — QA validation + deterministic auto-fix SDK.

Public surface:

* :class:`QAValidationRun`, :class:`QAFinding`, :class:`AutoFixRequest`
  — dataclass snapshots of the three Stage 29 tables.
* :class:`QAStore` — async asyncpg store for all three.
* :func:`apply_qa_rules`, :func:`classify_finding_auto_fixable` —
  deterministic rules (no LLM).
* :data:`MAX_AUTO_FIX_ATTEMPTS_DEFAULT` — the loop guard's default.
"""

from shared.sdk.qa.models import (
    AutoFixRequest,
    QAFinding,
    QAValidationRun,
)
from shared.sdk.qa.rules import (
    MAX_AUTO_FIX_ATTEMPTS_DEFAULT,
    apply_qa_rules,
    classify_finding_auto_fixable,
)
from shared.sdk.qa.store import QAStore

__all__ = [
    "AutoFixRequest",
    "MAX_AUTO_FIX_ATTEMPTS_DEFAULT",
    "QAFinding",
    "QAStore",
    "QAValidationRun",
    "apply_qa_rules",
    "classify_finding_auto_fixable",
]
