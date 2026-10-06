"""Graham Growth's CLI-layer functions: the watchlist selection builder and the refresh executor.

The CLI tier pairs these with the Graham Growth core bundle; nothing here registers itself.
"""

import typer

from src.cli_composition import build_graham_resolver, growth_assumptions
from src.cli_support import _canonical_provider_id, _parse_as_of, _production_financial_cache, config_usage_errors
from src.cli_watchlist_flags import WatchlistFlags
from src.core.clock import utc_now
from src.data.financial.providers import SEC_PROVIDER_ID
from src.data.instrument_profile_cache import InstrumentProfileResolver
from src.data.yfinance import YFinanceClient
from src.strategies.graham_growth.calculation import GrahamGrowthInputResolver
from src.strategies.graham_growth.execution import execute_graham_growth, from_graham_growth_capture
from src.strategies.graham_growth.selection import GrahamGrowthSelection
from src.workspace.capture import ExecutionCapture


def build_selection(flags: WatchlistFlags) -> GrahamGrowthSelection:
    """Build one validated Graham Growth selection from watchlist CLI flags.

    Mirrors the direct ``graham-growth`` command's own flags and validation exactly, so a watchlist entry
    behaves identically to running the method directly.
    """
    boundary = _parse_as_of(flags.as_of)
    provider_id = _canonical_provider_id(flags.data_provider) or SEC_PROVIDER_ID
    with config_usage_errors():
        if flags.expected_growth is None:
            raise typer.BadParameter("Required when --analysis is graham-growth.", param_hint="--expected-growth")
        if flags.aaa_yield is None:
            raise typer.BadParameter("Required when --analysis is graham-growth.", param_hint="--aaa-yield")
        return GrahamGrowthSelection.model_validate(
            {
                "security_provider_id": provider_id,
                "eps_basis": flags.eps_basis,
                "eps_override": flags.eps,
                "quote_override": flags.current_price,
                "as_of": boundary,
                "use_cache": not flags.no_cache,
                "expected_growth": flags.expected_growth,
                "aaa_yield_override": flags.aaa_yield,
            }
        )


def refresh(
    ticker: str, selection: GrahamGrowthSelection, *, profile_cache: InstrumentProfileResolver | None
) -> ExecutionCapture:
    """Execute one Graham Growth refresh job with freshly composed, job-scoped dependencies."""
    config = selection.to_graham_growth_config()
    policy = growth_assumptions()
    executed_at = utc_now()
    with _production_financial_cache(use_cache=selection.use_cache, clock=lambda: executed_at) as cache:
        resolver = build_graham_resolver(
            resolver_type=GrahamGrowthInputResolver,
            data_provider=config.security_provider_id,
            cache=cache,
            clock=lambda: executed_at,
        )
        capture = execute_graham_growth(
            resolver,
            ticker,
            config,
            policy,
            YFinanceClient(),
            as_of=selection.as_of,
            executed_at=executed_at,
            use_cache=selection.use_cache,
            profile_cache=profile_cache,
        )
    return from_graham_growth_capture(capture)
