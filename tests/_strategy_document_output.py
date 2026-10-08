"""Capture each strategy's ``--json`` document, direct and replayed, for every reachable shape.

Shared by ``tests/test_strategy_document_output.py`` and the regeneration entry point::

    uv run python -m tests._strategy_document_output

Every case runs one direct command against deterministic fixtures with ``--json``, and again with ``--save-run`` into
a temporary migrated database, then replays the saved run with ``runs show --json``. A few shapes the commands cannot
reach with fixtures (a stored result that is invalid while its inputs are fine, a Graham quote failure) are built as
stored runs by the replay tests and replayed the same way. The stored files are the check that the typed documents
write the same bytes the hand-written builders wrote.

Regeneration rewrites ``tests/expected_output/strategy_documents/`` from the current code, so an intended output
change shows up as a reviewed diff to those files. Exactly the normalization of ``tests/_direct_command_output.py``
applies.
"""

from __future__ import annotations

import json
import tempfile
from collections.abc import Callable, Iterator
from contextlib import ExitStack
from dataclasses import dataclass, fields, replace
from pathlib import Path
from types import ModuleType
from typing import cast
from unittest.mock import patch

from alembic.config import Config
from typer.testing import CliRunner

from alembic import command
from src.cli import app
from src.config import ProjectSettings
from src.config import settings as real_settings
from src.core.analysis_status import CalculationStatus
from src.data.financial.facts import FinancialField, ProviderFact
from src.data.financial.production import ProductionFinancialFactsProvider
from src.data.financial.provenance import ResolvedInput
from src.data.instrument_profile import (
    InstrumentKind,
    InstrumentKindEvidence,
    InstrumentKindRequest,
)
from src.data.repositories.analysis_runs import SQLiteAnalysisRunRepository
from src.data.repositories.sqlite import SQLiteDatabase
from src.data.sec_edgar import SEC_PROVIDER_ID
from src.data.security_identity import SecurityIdentity, SecurityIdentityRequest
from src.data.yfinance import YFinanceFinancialFactsAdapter
from src.data.yfinance.client import YFinanceClient
from src.evaluation.fixtures.fcf_earnings_growth import FixtureAnnualFinancialFactsProvider, annual_series
from src.evaluation.fixtures.graham import PROVIDER_ID, SECURITY_ID
from src.evaluation.fixtures.instrument_profiles import FIXTURE_PROFILE_RESOLVED_AT, fixture_known_etf_profile
from src.evaluation.fixtures.market_data import FixtureMarketDataProvider, momentum_boundary_frame
from src.strategies.fcf_growth.input_resolver import _failure_metric
from src.strategies.fcf_growth.models import Classification, FCFEarningsGrowthResult, ReasonCode, TrendClassification
from src.strategies.graham_growth.service import GrahamGrowthAnalysis
from src.strategies.graham_number.service import GrahamNumberAnalysis
from src.workspace.runs import AnalysisRun, RunQuery
from tests._direct_command_output import (
    _COMMANDS,
    CommandOutput,
    _FixtureYahoo,
    enter_fixture_providers,
    normalize,
)

EXPECTED_DIRECTORY = Path(__file__).resolve().parent / "expected_output" / "strategy_documents"
_REPOSITORY_ROOT = Path(__file__).resolve().parent.parent

_FCF_YEARS = range(2020, 2026)


class _ProfiledYahoo(_FixtureYahoo):
    """The fixture Yahoo client, answering identity and instrument-kind requests with fixed evidence."""

    kind = InstrumentKind.EQUITY
    provider_value = "EQUITY"

    def resolve_security_identity(self, request: SecurityIdentityRequest) -> SecurityIdentity:  # type: ignore[override]
        return SecurityIdentity(
            ticker=request.ticker,
            provider_id=request.provider_id,
            resolved_at=FIXTURE_PROFILE_RESOLVED_AT,
            instrument_name="Fixture Holdings Inc.",
            listing_venue="NYSE",
            issuer_identifier="0000000001",
            instrument_identifier="FIX-0001",
        )

    def resolve_instrument_kind(self, request: InstrumentKindRequest) -> InstrumentKindEvidence:  # type: ignore[override]
        return InstrumentKindEvidence(
            ticker=request.ticker,
            kind=self.kind,
            provider_value=self.provider_value,
            provider_id=request.provider_id,
            resolved_at=FIXTURE_PROFILE_RESOLVED_AT,
        )


class _EtfYahoo(_ProfiledYahoo):
    """The profiled client reporting an exchange-traded fund."""

    kind = InstrumentKind.ETF
    provider_value = "ETF"


class _ShortYahoo(_FixtureYahoo):
    """The fixture Yahoo client serving a series one observation too short for the long SMA."""

    def __init__(self) -> None:
        super().__init__()
        self._provider = FixtureMarketDataProvider(momentum_boundary_frame())


@dataclass(frozen=True)
class Case:
    """One stored document: a command line and fixture setup, with the exit codes it must produce."""

    name: str
    command: str
    arguments: tuple[str, ...]
    exit_code: int
    yahoo: type[_FixtureYahoo] = _FixtureYahoo
    fcf_facts: Callable[[], tuple[ProviderFact, ...]] | None = None
    fcf_error_field: FinancialField | None = None


def _fcf_success_facts() -> tuple[ProviderFact, ...]:
    return annual_series(_FCF_YEARS)


def _fcf_short_facts() -> tuple[ProviderFact, ...]:
    return annual_series(range(2022, 2026))


def _fcf_nonmeaningful_facts() -> tuple[ProviderFact, ...]:
    return annual_series(_FCF_YEARS, fcf_values=(80.0, 90.0, -5.0, 110.0, 120.0, 130.0))


def _fcf_declining_facts() -> tuple[ProviderFact, ...]:
    return annual_series(_FCF_YEARS, fcf_values=(130.0, 120.0, 110.0, 100.0, 90.0, 80.0))


def _fcf_no_facts() -> tuple[ProviderFact, ...]:
    return ()


def _arguments(command_name: str, *extra: str) -> tuple[str, ...]:
    """Return the fixed arguments of a direct command with ``extra`` appended."""
    return (*_COMMANDS[command_name], *extra)


def _with_ticker(command_name: str, ticker: str, *extra: str) -> tuple[str, ...]:
    """Return a Graham command line for another fixture subject."""
    return tuple(ticker if item == SECURITY_ID else item for item in _COMMANDS[command_name]) + extra


CASES: tuple[Case, ...] = (
    Case("momentum-success", "momentum", _arguments("momentum"), 0),
    Case("momentum-profile", "momentum", _arguments("momentum"), 0, yahoo=_ProfiledYahoo),
    Case("momentum-etf", "momentum", _arguments("momentum"), 0, yahoo=_EtfYahoo),
    Case("momentum-insufficient-data", "momentum", _arguments("momentum"), 0, yahoo=_ShortYahoo),
    Case("graham-number-success", "graham-number", _arguments("graham-number"), 0),
    Case("graham-number-profile", "graham-number", _arguments("graham-number"), 0, yahoo=_ProfiledYahoo),
    Case("graham-number-etf", "graham-number", _arguments("graham-number"), 0, yahoo=_EtfYahoo),
    Case("graham-number-missing-input", "graham-number", _with_ticker("graham-number", "MISSING"), 1),
    Case("graham-number-provider-error", "graham-number", _with_ticker("graham-number", "ERROR"), 1),
    Case("graham-number-incompatible-input", "graham-number", _with_ticker("graham-number", "INCOMPATIBLE"), 1),
    Case("graham-number-missing-quote", "graham-number", _with_ticker("graham-number", "MISSING_QUOTE"), 0),
    Case("graham-number-nonpositive-eps", "graham-number", _arguments("graham-number", "--eps", "-1"), 0),
    Case("graham-growth-success", "graham-growth", _arguments("graham-growth"), 0),
    Case("graham-growth-profile", "graham-growth", _arguments("graham-growth"), 0, yahoo=_ProfiledYahoo),
    Case("graham-growth-etf", "graham-growth", _arguments("graham-growth"), 0, yahoo=_EtfYahoo),
    Case("graham-growth-missing-input", "graham-growth", _with_ticker("graham-growth", "MISSING"), 1),
    Case("graham-growth-provider-error", "graham-growth", _with_ticker("graham-growth", "ERROR"), 1),
    Case("graham-growth-incompatible-input", "graham-growth", _with_ticker("graham-growth", "INCOMPATIBLE"), 1),
    Case("graham-growth-missing-quote", "graham-growth", _with_ticker("graham-growth", "MISSING_QUOTE"), 0),
    Case("graham-growth-negative-growth", "graham-growth", _arguments("graham-growth", "--expected-growth", "-2"), 0),
    Case("fcf-growth-success", "fcf-growth", _arguments("fcf-growth"), 0),
    Case("fcf-growth-profile", "fcf-growth", _arguments("fcf-growth"), 0, yahoo=_ProfiledYahoo),
    Case("fcf-growth-etf", "fcf-growth", _arguments("fcf-growth"), 0, yahoo=_EtfYahoo),
    Case("fcf-growth-fallback-horizon", "fcf-growth", _arguments("fcf-growth"), 0, fcf_facts=_fcf_short_facts),
    Case("fcf-growth-nonmeaningful", "fcf-growth", _arguments("fcf-growth"), 0, fcf_facts=_fcf_nonmeaningful_facts),
    Case("fcf-growth-declining", "fcf-growth", _arguments("fcf-growth"), 0, fcf_facts=_fcf_declining_facts),
    Case(
        "fcf-growth-confirmation-per-share",
        "fcf-growth",
        _arguments("fcf-growth", "--forward-policy", "confirmation", "--classification-basis", "fcf-per-share"),
        0,
    ),
    Case("fcf-growth-three-years", "fcf-growth", _arguments("fcf-growth", "--growth-years", "3"), 0),
    Case("fcf-growth-missing-input", "fcf-growth", _arguments("fcf-growth"), 1, fcf_facts=_fcf_no_facts),
    Case(
        "fcf-growth-provider-error",
        "fcf-growth",
        _arguments("fcf-growth"),
        1,
        fcf_error_field=FinancialField.OPERATING_CASH_FLOW,
    ),
)


def _fcf_provider(case: Case, yahoo: type[_FixtureYahoo]) -> ProductionFinancialFactsProvider:
    """Compose the FCF command's provider from the case's annual facts, relabeled as SEC EDGAR."""
    facts = (case.fcf_facts or _fcf_success_facts)()
    relabeled = tuple(
        replace(fact, provider_id=SEC_PROVIDER_ID, provider_fact_id=f"fy-{fact.fiscal_year}:{fact.field_name.value}")
        for fact in facts
    )
    return ProductionFinancialFactsProvider(
        sec_edgar=FixtureAnnualFinancialFactsProvider(relabeled, error_field=case.fcf_error_field),
        yfinance=YFinanceFinancialFactsAdapter(client=cast(YFinanceClient, yahoo())),
    )


def _enter_providers(stack: ExitStack, case: Case, *, sec_labeled: bool) -> None:
    """Replace the command's providers with the case's deterministic fixtures."""
    enter_fixture_providers(stack, case.command, sec_labeled=sec_labeled)
    for strategy in ("momentum", "graham_number", "graham_growth"):
        stack.enter_context(patch(f"src.strategies.{strategy}.cli.YFinanceClient", case.yahoo))
    stack.enter_context(
        patch(
            "src.strategies.fcf_growth.cli.build_sec_production_provider",
            side_effect=lambda *_a, **_k: _fcf_provider(case, case.yahoo),
        )
    )


def _provider_arguments(arguments: tuple[str, ...]) -> list[str]:
    """Return ``arguments`` naming SEC EDGAR, the one provider a saved run's selection admits."""
    return [SEC_PROVIDER_ID if item == PROVIDER_ID else item for item in arguments]


def run_direct(case: Case) -> CommandOutput:
    """Run the case's direct command with ``--json`` and no database."""
    with ExitStack() as stack:
        _enter_providers(stack, case, sec_labeled=False)
        result = CliRunner().invoke(app, [*case.arguments, "--json"])
    return CommandOutput(result.exit_code, normalize(result.stdout_bytes), result.stderr_bytes)


def _migrated(directory: Path) -> ProjectSettings:
    """Create a migrated database in ``directory`` and return settings that point at it."""
    url = f"sqlite:///{(directory / 'documents.sqlite3').as_posix()}"
    config = Config(str(_REPOSITORY_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    command.upgrade(config, "head")
    return ProjectSettings(**(real_settings.model_dump() | {"database_url": url}))


def _replay(settings: ProjectSettings, run_id: str) -> CommandOutput:
    """Replay one stored run as JSON."""
    with ExitStack() as stack:
        stack.enter_context(patch("src.cli_workspace.settings", settings))
        stack.enter_context(patch("src.cli_support.settings", settings))
        result = CliRunner().invoke(app, ["runs", "show", run_id, "--json"])
    return CommandOutput(result.exit_code, normalize(result.stdout_bytes), result.stderr_bytes)


def _single_run(settings: ProjectSettings) -> AnalysisRun:
    """Return the one run the database holds."""
    repository = SQLiteAnalysisRunRepository(SQLiteDatabase(settings))
    summaries = repository.list(RunQuery())
    assert len(summaries) == 1, summaries
    run = repository.get(summaries[0].analysis_run_id)
    assert run is not None
    return run


def run_saved(case: Case) -> CommandOutput:
    """Run the case's direct command with ``--save-run`` in a temporary database, then replay the saved run."""
    with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
        settings = _migrated(Path(directory))
        for module in ("src.cli_run_support", "src.strategies.momentum.cli"):
            stack.enter_context(patch(f"{module}.settings", settings))
        _enter_providers(stack, case, sec_labeled=True)
        result = CliRunner().invoke(app, [*_provider_arguments(case.arguments), "--json", "--save-run"])
        assert result.exit_code == case.exit_code, result.output
        run = _single_run(settings)
        return _replay(settings, str(run.analysis_run_id))


def replay_stored_run(run: AnalysisRun) -> CommandOutput:
    """Insert ``run`` into a temporary database and replay it as JSON."""
    with tempfile.TemporaryDirectory() as directory:
        settings = _migrated(Path(directory))
        SQLiteAnalysisRunRepository(SQLiteDatabase(settings)).insert(run)
        return _replay(settings, str(run.analysis_run_id))


def _fcf_invalid_input_result(replay: ModuleType) -> FCFEarningsGrowthResult:
    """A stored FCF result in the shape the analyzer writes for an invalid request, which no command can reach."""
    reason = "subject_id, currency, and providers for OCF, CapEx, and EPS are required."
    metric = _failure_metric(ReasonCode.INVALID_REQUEST, reason)
    result: FCFEarningsGrowthResult = replay._fcf_codec_result()
    return replace(
        result,
        execution_status=CalculationStatus.INVALID_INPUT,
        classification=Classification.INDETERMINATE,
        classification_reason_code=ReasonCode.INVALID_REQUEST,
        classification_reason=reason,
        selected_horizon_years=None,
        selected_observation_count=0,
        used_horizon_fallback=False,
        period_start=None,
        period_end=None,
        annual_observations=(),
        fcf_cagr=metric,
        fcf_per_share_cagr=metric,
        eps_cagr=metric,
        trend_classification=TrendClassification.INSUFFICIENT_OR_NONMEANINGFUL_GROWTH,
        warnings=(),
    )


def _at_boundary[AnalysisT: (GrahamNumberAnalysis, GrahamGrowthAnalysis)](analysis: AnalysisT) -> AnalysisT:
    """Return ``analysis`` with every resolved input stamped with the analysis boundary, which replay requires."""
    assembly = analysis.assembly
    inputs = {
        field.name: replace(value, as_of=analysis.as_of)
        for field in fields(assembly)
        if isinstance(value := getattr(assembly, field.name), ResolvedInput)
    }
    return replace(analysis, assembly=replace(assembly, **inputs))  # type: ignore[arg-type]  # one field name per resolved input


def stored_runs() -> Iterator[tuple[str, Callable[[], AnalysisRun]]]:
    """Yield ``(name, builder)`` for each shape built as a stored run instead of through a command."""
    from tests.reporting import test_analysis_run_replay as replay  # noqa: PLC0415 - test helpers, imported late
    from tests.workspace import test_graham_growth_codec as growth_codec  # noqa: PLC0415
    from tests.workspace import test_graham_number_codec as number_codec  # noqa: PLC0415

    etf = fixture_known_etf_profile
    yield "momentum-stored-spread", replay._build_run
    yield "graham-number-stored-result", replay._graham_run
    yield "graham-number-invalid-input", lambda: replay._graham_run(analysis=replay._graham_invalid_input_analysis())
    yield (
        "graham-number-etf-not-applicable",
        lambda: replay._graham_run(profile=etf(), analysis=replay._graham_etf_not_applicable_analysis()),
    )
    yield "graham-number-quote-failure", lambda: replay._graham_run(analysis=replay._graham_quote_failure_analysis())
    yield "graham-number-full-evidence", lambda: number_codec._run(_at_boundary(number_codec._analysis()))
    yield "graham-growth-stored-result", replay._growth_run
    yield "graham-growth-full-evidence", lambda: growth_codec._run(_at_boundary(growth_codec._analysis()))
    yield "graham-growth-invalid-input", lambda: replay._growth_run(analysis=replay._growth_invalid_input_analysis())
    yield (
        "graham-growth-etf-not-applicable",
        lambda: replay._growth_run(profile=etf(), analysis=replay._growth_etf_not_applicable_analysis()),
    )
    yield "graham-growth-quote-failure", lambda: replay._growth_run(analysis=replay._growth_quote_failure_analysis())
    yield "fcf-growth-stored-result", replay._fcf_run
    yield "fcf-growth-invalid-input", lambda: replay._fcf_run(result=_fcf_invalid_input_result(replay))


def cases() -> Iterator[str]:
    """Yield the stem of every stored file: ``<case>.direct`` or ``<case>.replay``."""
    for case in CASES:
        yield f"{case.name}.direct"
        yield f"{case.name}.replay"
    for name, _builder in stored_runs():
        yield f"{name}.replay"


def expected_path(stem: str) -> Path:
    """Return the stored file of one stem."""
    return EXPECTED_DIRECTORY / f"{stem}.json"


def expected_exit_code(stem: str) -> int:
    """Return the exit code a stored stem must produce: a replay always succeeds."""
    name, kind = stem.rsplit(".", maxsplit=1)
    return 0 if kind == "replay" else next(case.exit_code for case in CASES if case.name == name)


def produce(stem: str) -> CommandOutput:
    """Run the case behind ``stem`` and return its exit code and normalized standard output."""
    name, kind = stem.rsplit(".", maxsplit=1)
    for case in CASES:
        if case.name == name:
            return run_direct(case) if kind == "direct" else run_saved(case)
    for stored_name, builder in stored_runs():
        if stored_name == name:
            return replay_stored_run(builder())
    raise KeyError(stem)


def regenerate() -> None:
    """Rewrite every stored file from the current behavior."""
    EXPECTED_DIRECTORY.mkdir(parents=True, exist_ok=True)
    for stem in cases():
        output = produce(stem)
        if output.exit_code != expected_exit_code(stem):
            raise SystemExit(f"{stem} exited {output.exit_code}; refusing to store its output")
        json.loads(output.stdout)
        expected_path(stem).write_bytes(output.stdout)


if __name__ == "__main__":
    regenerate()
