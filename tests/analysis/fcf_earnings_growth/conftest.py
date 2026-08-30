"""Shared fixtures for the FCF & earnings-growth Slice B tests."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

import pytest

from src.data.financial.provenance import ResolvedInput, SourceKind

RESOLVED_AT = datetime(2025, 12, 31, tzinfo=UTC)


@pytest.fixture
def resolved_input() -> Callable[..., ResolvedInput]:
    """Return a factory that builds a minimal fully-provenanced provider input."""

    def _make(field_name: str, value: float, **kwargs: object) -> ResolvedInput:
        defaults: dict[str, object] = {
            "field_name": field_name,
            "value": value,
            "source_kind": SourceKind.PROVIDER,
            "resolved_at": RESOLVED_AT,
            "provider_id": "fixture",
        }
        defaults.update(kwargs)
        return ResolvedInput(**defaults)  # type: ignore[arg-type]

    return _make
