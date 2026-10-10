"""Analysis requests for the local research workspace.

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
(see the strategies' ``cli.py`` provider resolution): the security-fact provider must be SEC EDGAR (``sec_edgar``),
even though the base analyzer configs permit arbitrary identifiers for dependency injection. The quote provider
resolves from the security provider using the existing Graham semantics.

The canonical analysis/method identifiers and ``config_schema_version`` are fixed to the contract matrix
values and cannot be overridden or made to disagree with one another; an unsupported version is rejected at
validation time.
"""

from pydantic import field_validator

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
