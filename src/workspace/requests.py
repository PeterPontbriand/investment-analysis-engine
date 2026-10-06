"""Analysis requests and selection parsing for the local research workspace.

An :class:`AnalysisRequest` binds a normalized ticker to one immutable per-method selection. The
selection classes live in each strategy's ``selection`` module, their shared base and the provider
vocabulary in :mod:`src.workspace.selection_base`, and the closed selection union in
:mod:`src.workspace.strategy_types`. Selection variants freeze one method's effective configuration at
creation time: defaults are materialized from the current configured policy or explicit caller inputs,
unknown fields are rejected, non-finite financial values are rejected, and later changes to settings or
caller-owned containers cannot alter an existing snapshot. Conversions return the existing analyzer config
types with their original semantics; they never construct data providers, fetch metadata, or perform
analysis work.

Provider choices are restricted at the selection boundary to those supported by the current CLI composition
(see the strategies' ``cli.py`` provider resolution): the security-fact provider must be SEC EDGAR (``sec_edgar``) or
Massive (``massive``), even though the base analyzer configs permit arbitrary identifiers for dependency
injection. The quote provider resolves from the security provider using the existing Graham semantics.

The canonical analysis/method identifiers and ``config_schema_version`` are fixed to the contract matrix
values and cannot be overridden or made to disagree with one another; an unsupported version is rejected at
validation time.
"""

import json
import math
from collections.abc import Callable, Mapping
from typing import cast

from pydantic import field_validator

from src.core.strategy_errors import find
from src.workspace.selection_base import FrozenSelection
from src.workspace.strategy_types import AnalysisSelection, SelectionMember


class AnalysisRequest(FrozenSelection):
    """Bind a normalized ticker to one fully specified immutable method selection."""

    ticker: str
    selection: AnalysisSelection

    @field_validator("ticker")
    @classmethod
    def _normalize_ticker(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("ticker must not be empty.")
        return normalized


def _unique_json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    """Decode each JSON object without silently overwriting duplicate keys."""
    values: dict[str, object] = {}
    for key, value in pairs:
        if key in values:
            raise ValueError(f"Duplicate configuration key: {key!r}.")
        values[key] = value
    return values


def _finite_json_float(text: str) -> float:
    """Reject exponent overflow as well as explicitly nonfinite JSON constants."""
    value = float(text)
    if not math.isfinite(value):
        raise ValueError("Configuration numbers must be finite.")
    return value


def _reject_json_constant(text: str) -> object:
    raise ValueError(f"Nonfinite JSON constant is not allowed: {text}.")


type SelectionParser = Callable[[dict[str, object]], SelectionMember]


def parse_selection(alias: str, config_json: str, parsers: Mapping[str, SelectionParser]) -> AnalysisSelection:
    """Parse one exact CLI alias and its method-specific JSON configuration.

    The JSON decoding rules are shared here; the alias's own parser, injected by the caller, validates the
    decoded object. Omitted defaults are resolved once; explicit null does not mean omission for required
    scalar fields or configuration objects.

    Args:
        alias: A declared analysis alias.
        config_json: A JSON object containing request configuration only.
        parsers: The selection parser of each declared alias.

    Returns:
        A validated immutable selection with canonical identifiers.

    Raises:
        ValueError: The alias, JSON representation or configuration is invalid.
    """
    parser = find(parsers, alias)
    if parser is None:
        raise ValueError(f"Unknown analysis alias: {alias!r}.")
    decoded: object = json.loads(
        config_json,
        object_pairs_hook=_unique_json_object,
        parse_float=_finite_json_float,
        parse_constant=_reject_json_constant,
    )
    if not isinstance(decoded, dict):
        raise ValueError("Configuration must be a JSON object.")
    return parser(cast(dict[str, object], decoded))
