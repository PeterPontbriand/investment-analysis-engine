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
(see ``src/cli.py`` provider resolution): the security-fact provider must be SEC EDGAR (``sec_edgar``) or
Massive (``massive``), even though the base analyzer configs permit arbitrary identifiers for dependency
injection. The quote provider resolves from the security provider using the existing Graham semantics.

The canonical analysis/method identifiers and ``config_schema_version`` are fixed to the contract matrix
values and cannot be overridden or made to disagree with one another; an unsupported version is rejected at
validation time.
"""

import json
import math
from typing import cast

from pydantic import field_validator

from src.config import settings
from src.core.constants import ConfigKeys
from src.strategies.fcf_growth.selection import FCFGrowthSelection
from src.strategies.graham_growth.selection import GrahamGrowthSelection
from src.strategies.graham_number.selection import GrahamNumberSelection
from src.strategies.momentum.selection import MomentumSelection
from src.workspace.selection_base import FrozenSelection
from src.workspace.strategy_types import AnalysisSelection


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


def parse_selection(alias: str, config_json: str) -> AnalysisSelection:
    """Parse one exact CLI alias and its method-specific JSON configuration.

    Momentum and Graham bodies contain only an optional `config` object.
    FCF bodies contain policy, currency, provider, as_of and cache options.
    Omitted defaults are resolved once; explicit null does not mean omission
    for required scalar fields or configuration objects.

    Args:
        alias: One of momentum, graham-number, graham-growth or fcf-growth.
        config_json: A JSON object containing request configuration only.

    Returns:
        A validated immutable selection with canonical identifiers.

    Raises:
        ValueError: The alias, JSON representation or configuration is invalid.
    """
    if alias not in ("momentum", "graham-number", "graham-growth", "fcf-growth"):
        raise ValueError(f"Unknown analysis alias: {alias!r}.")
    decoded: object = json.loads(
        config_json,
        object_pairs_hook=_unique_json_object,
        parse_float=_finite_json_float,
        parse_constant=_reject_json_constant,
    )
    if not isinstance(decoded, dict):
        raise ValueError("Configuration must be a JSON object.")
    body = cast(dict[str, object], decoded)
    if alias == "fcf-growth":
        if body.keys() - {"policy", "currency", "provider_id", "as_of", "use_cache"}:
            raise ValueError("FCF configuration contains unknown or reserved fields.")
        return FCFGrowthSelection.model_validate(body)

    if body.keys() - {"config"}:
        raise ValueError("Configuration body may contain only 'config'.")
    supplied = body.get("config", {})
    if not isinstance(supplied, dict):
        raise ValueError("'config' must be a JSON object.")
    config = cast(dict[str, object], supplied)
    if config.keys() & {"analysis_id", "method_id", "config_schema_version"}:
        raise ValueError("Selection identifiers and version cannot be supplied in configuration.")
    if alias == "graham-number":
        return GrahamNumberSelection.model_validate(config)
    if alias == "graham-growth":
        return GrahamGrowthSelection.model_validate(config)

    values = dict(config)
    if "short_window" not in values or "long_window" not in values:
        windows = settings.get_momentum_analysis()[ConfigKeys.WINDOW_SIZES]
        if "short_window" not in values:
            values["short_window"] = int(windows[ConfigKeys.SHORT_WINDOW])
        if "long_window" not in values:
            values["long_window"] = int(windows[ConfigKeys.LONG_WINDOW])
    return MomentumSelection.model_validate(values)
