"""FCF Growth's CLI-layer functions: the watchlist selection builder and the refresh executor.

The CLI tier pairs these with the FCF Growth core bundle; nothing here registers itself.
"""

import typer

from src.cli_composition import build_sec_production_provider
from src.cli_support import _canonical_provider_id, _parse_as_of, _production_financial_cache
from src.cli_watchlist_flags import WatchlistFlags
from src.core.clock import utc_now
from src.data.instrument_profile_cache import InstrumentProfileResolver
from src.strategies.fcf_growth.execution import execute_fcf_growth, from_fcf_growth_capture
from src.strategies.fcf_growth.input_resolver import ProductionAnnualGrowthSeriesResolver
from src.strategies.fcf_growth.models import (
    FCFClassificationBasis,
    FCFEarningsGrowthPolicy,
    ForwardPolicy,
    HistoricalHorizon,
)
from src.strategies.fcf_growth.selection import FCFGrowthSelection, FCFPolicySnapshot
from src.workspace.capture import ExecutionCapture


def _fcf_historical_horizon(growth_years: int | None) -> HistoricalHorizon:
    """Convert the optional CLI horizon to the typed strict/automatic policy."""
    if growth_years is None:
        return HistoricalHorizon.LONGEST_AVAILABLE
    mapping = {3: HistoricalHorizon.THREE_YEARS, 4: HistoricalHorizon.FOUR_YEARS, 5: HistoricalHorizon.FIVE_YEARS}
    try:
        return mapping[growth_years]
    except KeyError as exc:
        raise typer.BadParameter("--growth-years must be 3, 4, or 5.") from exc


def _fcf_forward_policy(value: str) -> ForwardPolicy:
    """Map the hyphenated investor-facing CLI value to the normative enum."""
    normalized = value.strip().lower().replace("-", "_")
    try:
        return ForwardPolicy(normalized)
    except ValueError as exc:
        raise typer.BadParameter("--forward-policy must be display-only, confirmation, or hard-gate.") from exc


def _fcf_classification_basis(value: str) -> FCFClassificationBasis:
    """Map the investor-facing CLI value to the typed FCF basis policy."""
    normalized = value.strip().lower().replace("-", "_")
    try:
        return FCFClassificationBasis(normalized)
    except ValueError as exc:
        raise typer.BadParameter("--classification-basis must be total-fcf or fcf-per-share.") from exc


def build_selection(flags: WatchlistFlags) -> FCFGrowthSelection:
    """Build one validated FCF Growth selection from watchlist CLI flags.

    Mirrors the direct ``fcf-growth`` command's own flags and validation exactly. The method always executes
    against SEC EDGAR regardless of ``--data-provider``, as the direct command's own persisted selection does;
    the flag is still validated for a consistent error experience.
    """
    boundary = _parse_as_of(flags.as_of)
    _canonical_provider_id(flags.data_provider)
    normalized_currency = flags.currency.strip().upper()
    if len(normalized_currency) != 3 or not normalized_currency.isalpha():
        raise typer.BadParameter("--currency must be a three-letter ISO 4217 code.")
    policy = FCFEarningsGrowthPolicy(
        historical_horizon=_fcf_historical_horizon(flags.growth_years),
        classification_basis=_fcf_classification_basis(flags.classification_basis),
        forward_policy=_fcf_forward_policy(flags.forward_policy),
    )
    return FCFGrowthSelection(
        policy=FCFPolicySnapshot.model_validate(policy),
        currency=normalized_currency,
        provider_id="sec_edgar",
        as_of=boundary,
        use_cache=not flags.no_cache,
    )


def refresh(
    ticker: str, selection: FCFGrowthSelection, *, profile_cache: InstrumentProfileResolver | None
) -> ExecutionCapture:
    """Execute one FCF Growth refresh job with freshly composed, job-scoped dependencies."""
    config = selection.to_fcf_config()
    executed_at = utc_now()
    with _production_financial_cache(use_cache=selection.use_cache, clock=lambda: executed_at) as cache:
        provider = build_sec_production_provider()
        resolver = ProductionAnnualGrowthSeriesResolver(provider, cache=cache, clock=lambda: executed_at)
        capture = execute_fcf_growth(
            resolver,
            ticker,
            config=config,
            as_of=selection.as_of,
            executed_at=executed_at,
            use_cache=selection.use_cache,
            provider=provider,
            profile_cache=profile_cache,
        )
    return from_fcf_growth_capture(capture)
