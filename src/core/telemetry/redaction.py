"""Security-conscious serialization and redaction helpers for telemetry."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import BaseModel

_REDACTED = "[REDACTED]"
_SECRET_KEY_RE = re.compile(
    r"(?:api[_-]?key|access[_-]?key|secret|password|passwd|authorization|cookie|session[_-]?token|refresh[_-]?token|client[_-]?secret|private[_-]?key)$",
    re.IGNORECASE,
)
_BEARER_RE = re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]+", re.IGNORECASE)
_GENERIC_SECRET_RE = re.compile(r"\b(?:sk-[A-Za-z0-9_-]{16,}|AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9_]{20,})\b")
_SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)([\"\']?(?:api[_-]?key|access[_-]?key|secret|password|passwd|authorization|cookie|session[_-]?token|refresh[_-]?token|client[_-]?secret|private[_-]?key)[\"\']?\s*[:=]\s*)([^,;\s}]+)"
)


def redact_value(value: Any) -> Any:
    """Return a JSON-safe value with common secret-bearing fields and tokens redacted."""
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")

    if isinstance(value, Mapping):
        return {
            str(key): _REDACTED if _SECRET_KEY_RE.search(str(key)) else redact_value(item)
            for key, item in value.items()
        }

    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [redact_value(item) for item in value]

    if isinstance(value, bytes):
        return f"<bytes:{len(value)}>"

    if isinstance(value, str):
        value = _BEARER_RE.sub(_REDACTED, value)
        value = _SECRET_ASSIGNMENT_RE.sub(r"\1" + _REDACTED, value)
        return _GENERIC_SECRET_RE.sub(_REDACTED, value)

    if value is None or isinstance(value, (bool, int, float)):
        return value

    return str(value)


def sanitize_exception_message(message: str) -> str:
    """Remove common credential forms from an exception message."""
    return str(redact_value(message))
