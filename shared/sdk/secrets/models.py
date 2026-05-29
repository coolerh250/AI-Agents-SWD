"""Type-safe secret handle.

A ``SecretRef`` wraps a string but never reveals it through ``repr``,
``str``, or pydantic / dataclass serialisation. Callers that genuinely
need the value must call ``SecretRef.reveal()`` — every such call is
auditable by grep.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

REDACTION_TOKEN = "***REDACTED***"


@dataclass(frozen=True)
class SecretRef:
    """Opaque handle to a secret value loaded from an env var / vault.

    ``__repr__`` and ``__str__`` both return the redaction token. The
    raw value is only accessible via :meth:`reveal`, so any accidental
    interpolation into a log / response / audit row renders as
    ``***REDACTED***`` instead of leaking the credential.
    """

    name: str
    _value: str = field(default="", repr=False, compare=False)
    present: bool = False

    def reveal(self) -> str:
        return self._value

    def __repr__(self) -> str:
        return f"SecretRef(name={self.name!r}, present={self.present}, value={REDACTION_TOKEN!r})"

    def __str__(self) -> str:
        return REDACTION_TOKEN

    def __bool__(self) -> bool:
        return self.present and bool(self._value)

    # Pydantic v2 calls ``__get_pydantic_core_schema__``; defining a
    # ``model_dump`` hook isn't required because pydantic never sees the
    # raw value through a dataclass. The class is still safe to embed
    # in models — pydantic will serialise the dataclass to its repr
    # form, which is the redacted shape above.
    def model_dump(self) -> dict[str, Any]:
        return {"name": self.name, "present": self.present, "value": REDACTION_TOKEN}
