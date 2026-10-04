"""Run the four direct analysis commands against fixtures and capture their output.

Shared by ``tests/test_direct_command_output.py`` and the regeneration entry point::

    uv run python -m tests._direct_command_output

Regeneration rewrites the files under ``tests/expected_output/direct_commands/`` from the current code, so an
intended output change shows up as a reviewed diff to those files.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from contextlib import ExitStack, nullcontext
from dataclasses import dataclass, replace
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from src.cli import app
from src.core.clock import utc_now
from src.data.financial.cache import InMemoryResolvedInputCache
from src.data.financial.production import ProductionFinancialFactsProvider
from src.data.market_data import HistoricalMarketData
from src.data.sec_edgar import SEC_PROVIDER_ID
from src.evaluation.fixtures.fcf_earnings_growth import FixtureAnnualFinancialFactsProvider, annual_series
from src.evaluation.fixtures.graham import NOW, PROVIDER_ID, SECURITY_ID, FixtureFinancialFactsProvider
from src.evaluation.fixtures.market_data import FixtureMarketDataProvider, momentum_success_frame
from src.strategies.graham_growth.calculation import GrahamGrowthInputResolver
from src.strategies.graham_number.calculation import GrahamNumberInputResolver

EXPECTED_DIRECTORY = Path(__file__).resolve().parent / "expected_output" / "direct_commands"

_WALL_CLOCK_FIELDS = re.compile(rb'("(?:resolved_at|effective_as_of|analysis_timestamp|retrieved_at)": ")[^"]+')
_COMMANDS = {
    "momentum": ["momentum", "BTC-USD", "--short-window", "2", "--long-window", "3", "--rsi-period", "3", "--no-cache"],
    "graham-number": ["graham-number", SECURITY_ID, "--data-provider", PROVIDER_ID, "--no-cache"],
    "graham-growth": [
        *("graham-growth", SECURITY_ID, "--expected-growth", "5", "--aaa-yield", "4.5"),
        *("--data-provider", PROVIDER_ID, "--no-cache"),
    ],
    "fcf-growth": ["fcf-growth", "ACME", "--no-cache"],
}
_MODES = {"text": [], "json": ["--json"]}


@dataclass(frozen=True)
class CommandOutput:
    """The exit code and standard streams of one command run."""

    exit_code: int
    stdout: bytes
    stderr: bytes


class _FixtureYahoo:
    """Deterministic stand-in for the Yahoo client the Momentum command constructs."""

    provider_id = "fixture_market"

    def __init__(self) -> None:
        self._provider = FixtureMarketDataProvider(momentum_success_frame())

    def fetch_historical_data(
        self, ticker: str, start_date: str, end_date: str | None = None, *, use_cache: bool = True
    ) -> HistoricalMarketData:
        return self._provider.fetch_historical_data(ticker, start_date, end_date, use_cache=use_cache)

    def resolve_security_identity(self, *_arguments: object, **_keywords: object) -> None:
        return None

    def resolve_instrument_kind(self, *_arguments: object, **_keywords: object) -> None:
        return None


def _fcf_provider() -> ProductionFinancialFactsProvider:
    facts = tuple(
        replace(fact, provider_id=SEC_PROVIDER_ID, provider_fact_id=f"fy-{fact.fiscal_year}:{fact.field_name.value}")
        for fact in annual_series(range(2020, 2026))
    )
    return ProductionFinancialFactsProvider(sec_edgar=FixtureAnnualFinancialFactsProvider(facts))


def normalize(stdout: bytes) -> bytes:
    r"""Translate Windows line endings to ``\n`` and replace each wall-clock JSON field value with a marker."""
    return _WALL_CLOCK_FIELDS.sub(rb"\1<wall-clock>", stdout.replace(b"\r\n", b"\n"))


def run_command(command: str, mode: str) -> CommandOutput:
    """Run one direct command in one output mode against its fixtures; no network, provider or model call."""
    resolver_type = GrahamGrowthInputResolver if command == "graham-growth" else GrahamNumberInputResolver
    resolver = resolver_type(FixtureFinancialFactsProvider(), clock=lambda: NOW)
    with ExitStack() as stack:
        stack.enter_context(patch("src.cli.build_graham_resolver", return_value=resolver))
        stack.enter_context(
            patch("src.cli.build_sec_production_provider", side_effect=lambda *_a, **_k: _fcf_provider())
        )
        stack.enter_context(
            patch(
                "src.cli._production_financial_cache",
                side_effect=lambda **_: nullcontext(InMemoryResolvedInputCache(clock=utc_now)),
            )
        )
        stack.enter_context(patch("src.cli.YFinanceClient", _FixtureYahoo))
        result = CliRunner().invoke(app, [*_COMMANDS[command], *_MODES[mode]])
    return CommandOutput(result.exit_code, normalize(result.stdout_bytes), result.stderr_bytes)


def cases() -> Iterator[tuple[str, str]]:
    """Yield every ``(command, mode)`` pair that has stored expected output."""
    for command in _COMMANDS:
        for mode in _MODES:
            yield command, mode


def expected_path(command: str, mode: str) -> Path:
    """Return the stored expected-output file of one command and mode."""
    return EXPECTED_DIRECTORY / f"{command}.{'json' if mode == 'json' else 'txt'}"


def regenerate() -> None:
    """Rewrite every stored expected-output file from the current behavior."""
    EXPECTED_DIRECTORY.mkdir(parents=True, exist_ok=True)
    for command, mode in cases():
        output = run_command(command, mode)
        if output.exit_code != 0 or output.stderr:
            raise SystemExit(f"{command} {mode} did not succeed; refusing to store its output")
        expected_path(command, mode).write_bytes(output.stdout)


if __name__ == "__main__":
    regenerate()
