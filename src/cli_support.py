"""Shared CLI parsing, resource ownership, and execution-error translation."""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime, time, timedelta

import typer
from pydantic import ValidationError
from typer._click.exceptions import UsageError

from src.config import settings
from src.core.telemetry.quality import record_cli_quality
from src.data.base_client import DataFetchError
from src.data.cached_client import CachedHistoricalDataClient
from src.data.financial.cache import InMemoryResolvedInputCache, ResolvedInputSeriesCacheProtocol
from src.data.quality import HistoricalQualityPolicy
from src.data.repositories import SQLiteDatabase, SQLiteMarketDataRepository, SQLiteResolvedInputCache
from src.data.yfinance import YFinanceClient
from src.data.yfinance.client import YFINANCE_HISTORICAL_INTERVAL, YFINANCE_PRICE_ADJUSTMENT
from src.reporting.presentation import PresentationMode


@contextmanager
def _production_historical_client(provider: YFinanceClient) -> Iterator[CachedHistoricalDataClient]:
    """Borrow the Yahoo client and own historical storage for one analysis.

    Daily adjusted request identity matches the provider's download configuration.
    Reuse age comes from settings; table migrations remain an operator action.
    """
    database = SQLiteDatabase(settings)
    try:
        seconds = settings.historical_cache_ttl_seconds
        yield CachedHistoricalDataClient(
            provider,
            SQLiteMarketDataRepository(database),
            request_variant=f"{YFINANCE_HISTORICAL_INTERVAL}:{YFINANCE_PRICE_ADJUSTMENT}",
            ttl=None if seconds is None else timedelta(seconds=seconds),
            quality_policy=HistoricalQualityPolicy(expected_adjustment=YFINANCE_PRICE_ADJUSTMENT),
        )
    finally:
        database.close()


@contextmanager
def _production_financial_cache(*, enabled: bool) -> Iterator[ResolvedInputSeriesCacheProtocol]:
    """Own one invocation's durable cache; schema upgrades remain explicit.

    Financial facts use configured residence age (unlimited by default) and
    temporal quality checks. Disabling caching avoids opening SQLite altogether.
    """
    if not enabled:
        yield InMemoryResolvedInputCache()
        return
    database = SQLiteDatabase(settings)
    try:
        seconds = settings.financial_cache_ttl_seconds
        yield SQLiteResolvedInputCache(database, ttl=None if seconds is None else timedelta(seconds=seconds))
    finally:
        database.close()


def _presentation_mode(*, details: bool, diagnostics: bool, json_output: bool) -> PresentationMode:
    """Resolve the mutually exclusive progressive-disclosure flags."""
    selected_count = sum((details, diagnostics, json_output))
    if selected_count > 1:
        raise typer.BadParameter("Choose only one of --details, --diagnostics, or --json.")
    if json_output:
        return PresentationMode.JSON
    if diagnostics:
        return PresentationMode.DIAGNOSTICS
    if details:
        return PresentationMode.DETAILS
    return PresentationMode.CONCISE


def _resolve_ticker(positional: str | None, option: str | None, *, required: bool, command: str) -> str | None:
    """Resolve positional ticker with a transitional --ticker compatibility alias."""
    if positional is not None and option is not None and positional.strip().upper() != option.strip().upper():
        raise typer.BadParameter("Positional TICKER and --ticker refer to different symbols.")
    selected = positional if positional is not None else option
    if selected is None:
        if required:
            raise typer.BadParameter(f"TICKER is required. Use 'financial-agents {command} TICKER'.")
        return None
    normalized = selected.strip().upper()
    if not normalized:
        raise typer.BadParameter("Ticker must be a non-empty symbol.")
    return normalized


def _canonical_provider_id(value: str | None) -> str | None:
    """Normalize an optional provider identifier."""
    if value is None:
        return None
    normalized = value.strip().lower()
    if not normalized:
        raise typer.BadParameter("--data-provider must be non-empty when supplied.")
    return normalized


def _parse_as_of(value: str | None) -> datetime | None:
    """Parse a CLI as-of boundary without silently assuming a timestamp timezone."""
    if value is None:
        return None
    text = value.strip()
    if not text:
        raise typer.BadParameter("--as-of must be non-empty when supplied.")

    try:
        if len(text) == 10:
            parsed_date = date.fromisoformat(text)
            return datetime.combine(parsed_date, time.max, tzinfo=UTC)

        normalized = f"{text[:-1]}+00:00" if text.endswith(("Z", "z")) else text
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise typer.BadParameter("--as-of must be YYYY-MM-DD or a valid timezone-aware ISO-8601 timestamp.") from exc

    if parsed.tzinfo is None or parsed.tzinfo.utcoffset(parsed) is None:
        raise typer.BadParameter("Timestamp --as-of values must include an explicit timezone offset.")
    return parsed


@contextmanager
def execution_errors(
    *,
    unexpected: Callable[[Exception], str],
    invalid: Callable[[ValueError], str] | None = None,
    data_error: Callable[[DataFetchError], str] | None = None,
) -> Iterator[None]:
    """Translate execution failures while preserving deliberate CLI exits."""
    try:
        with record_cli_quality():
            yield
    except (typer.Exit, UsageError):
        raise
    except Exception as exc:
        if isinstance(exc, DataFetchError) and data_error is not None:
            message = data_error(exc)
        elif isinstance(exc, ValueError) and invalid is not None:
            message = invalid(exc)
        else:
            message = unexpected(exc)
        typer.echo(message, err=True)
        raise typer.Exit(code=1) from exc


@contextmanager
def config_usage_errors() -> Iterator[None]:
    """Expose concise option names without dumping configuration input values."""
    try:
        yield
    except ValidationError as exc:
        error = exc.errors(include_input=False, include_url=False)[0]
        location = error["loc"]
        names = {
            "security_provider_id": "--data-provider",
            "eps_basis": "--eps-basis",
            "eps_override": "--eps",
            "bvps_override": "--bvps",
            "quote_override": "--current-price",
            "expected_growth": "--expected-growth",
            "aaa_yield_override": "--aaa-yield",
            "as_of": "--as-of",
        }
        if location:
            option = names.get(str(location[0]), "Graham options")
            message = f"Invalid {option}: {error['msg']}"
        else:
            message = error["msg"].removeprefix("Value error, ")
            for field, option in names.items():
                message = message.replace(field, option)
        raise typer.BadParameter(message) from exc
