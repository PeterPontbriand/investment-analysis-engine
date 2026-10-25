"""Capture each strategy's ``--json`` document, direct and replayed, for every reachable shape.

Shared by ``tests/test_strategy_document_output.py`` and the regeneration entry point::

    uv run python -m tests._strategy_document_output

Every case runs one direct command against deterministic fixtures with ``--json --save-run`` into a temporary
migrated database. The document that command writes is the ``.direct`` file; replaying the saved run with
``runs show --json`` writes the ``.replay`` file. Both come from the same run, so they differ only if the stored
evidence or the replay path loses something. A few shapes the commands cannot
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
from datetime import datetime
from functools import cache
from pathlib import Path
from types import ModuleType
from typing import cast
from unittest.mock import patch

from typer.testing import CliRunner

from investment_analysis_engine.cli import app
from investment_analysis_engine.config import ProjectSettings
from investment_analysis_engine.config import settings as real_settings
from investment_analysis_engine.core.analysis_status import CalculationStatus
from investment_analysis_engine.core.metric_result import ReasonCode
from investment_analysis_engine.core.provider_failure_kind import ProviderFailureKind
from investment_analysis_engine.data.base_client import DataFetchError
from investment_analysis_engine.data.financial.facts import (
    FinancialFactRequest,
    FinancialFactsProvider,
    FinancialField,
    FinancialProviderError,
    ProviderFact,
)
from investment_analysis_engine.data.financial.production import ProductionFinancialFactsProvider
from investment_analysis_engine.data.financial.provenance import ResolvedInput
from investment_analysis_engine.data.instrument_profile import (
    InstrumentKind,
    InstrumentKindEvidence,
    InstrumentKindRequest,
)
from investment_analysis_engine.data.market_data import HistoricalMarketData
from investment_analysis_engine.data.repositories.sqlite import SQLiteDatabase
from investment_analysis_engine.data.sec_edgar.financial_facts import SEC_PROVIDER_ID
from investment_analysis_engine.data.security_identity import SecurityIdentity, SecurityIdentityRequest
from investment_analysis_engine.data.yfinance.client import YFinanceClient
from investment_analysis_engine.data.yfinance.financial_facts import YFinanceFinancialFactsAdapter
from investment_analysis_engine.evaluation.fixtures.fcf_earnings_growth import (
    FixtureAnnualFinancialFactsProvider,
    annual_series,
)
from investment_analysis_engine.evaluation.fixtures.graham import NOW, SECURITY_ID
from investment_analysis_engine.evaluation.fixtures.instrument_profiles import (
    FIXTURE_PROFILE_RESOLVED_AT,
    fixture_known_etf_profile,
)
from investment_analysis_engine.evaluation.fixtures.market_data import (
    FixtureMarketDataProvider,
    momentum_boundary_frame,
)
from investment_analysis_engine.strategies.fcf_growth.input_resolver import _failure_metric
from investment_analysis_engine.strategies.fcf_growth.models import FCFEarningsGrowthResult
from investment_analysis_engine.strategies.fcf_growth.vocabulary import Classification, TrendClassification
from investment_analysis_engine.strategies.graham_growth.calculation import GrahamGrowthInputResolver
from investment_analysis_engine.strategies.graham_growth.service import GrahamGrowthAnalysis
from investment_analysis_engine.strategies.graham_number.calculation import GrahamNumberInputResolver
from investment_analysis_engine.strategies.graham_number.service import GrahamNumberAnalysis
from investment_analysis_engine.workspace.repositories.analysis_runs import SQLiteAnalysisRunRepository
from investment_analysis_engine.workspace.runs import AnalysisRun, RunQuery
from tests._direct_command_output import (
    _COMMANDS,
    CommandOutput,
    _FixtureYahoo,
    enter_fixture_providers,
    normalize,
)
from tests._migrated_database import migrated_database_url
from tests._sec_labeled_graham import SecLabeledGrahamProvider

REPLAY_EXCLUDED_KEYS = frozenset({"provider_check"})
"""The one top-level key the direct-equals-replay comparison leaves out, by name.

A replay runs no live check, so it always writes ``provider_check`` null, while a direct command that failed on a
provider writes what the check found. Every other key must agree.
"""

EXPECTED_DIRECTORY = Path(__file__).resolve().parent / "expected_output" / "strategy_documents"

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


class _FailingYahoo(_FixtureYahoo):
    """The fixture Yahoo client whose price history request fails with a classified provider failure."""

    def fetch_historical_data(
        self, ticker: str, start_date: str, end_date: str | None = None, *, use_cache: bool = True
    ) -> HistoricalMarketData:
        del ticker, start_date, end_date, use_cache
        raise DataFetchError("fixture provider failure", kind=ProviderFailureKind.RATE_LIMITED, provider_id="yfinance")


def without_excluded_keys(text: bytes) -> str:
    """Return a document's text with the excluded keys removed, written as a strategy command writes a document."""
    document = json.loads(text)
    for key in REPLAY_EXCLUDED_KEYS:
        del document[key]
    return json.dumps(document, indent=2, ensure_ascii=False, allow_nan=False)


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
    failure_kind: ProviderFailureKind | None = None
    """When set, the fixture provider's failure is raised carrying this kind instead of the fixture's own."""
    unclassified: bool = False
    """The one deliberate no-kind case: the fixture provider's failure is raised with no kind."""
    quote_failure_kind: ProviderFailureKind | None = None
    """When set, only the optional quote fails, with this kind."""


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
    Case("momentum-insufficient-data", "momentum", _arguments("momentum"), 1, yahoo=_ShortYahoo),
    Case("momentum-provider-error", "momentum", _arguments("momentum"), 1, yahoo=_FailingYahoo),
    Case("momentum-no-observation", "momentum", _arguments("momentum", "--as-of", "2020-06-01"), 1),
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
    Case(
        "graham-number-provider-error-unclassified",
        "graham-number",
        _with_ticker("graham-number", "ERROR"),
        1,
        unclassified=True,
    ),
    Case(
        "graham-number-provider-rate-limited",
        "graham-number",
        _with_ticker("graham-number", "ERROR"),
        1,
        failure_kind=ProviderFailureKind.RATE_LIMITED,
    ),
    Case(
        "graham-number-quote-provider-failure",
        "graham-number",
        _arguments("graham-number"),
        0,
        quote_failure_kind=ProviderFailureKind.UNREACHABLE,
    ),
    Case(
        "graham-growth-quote-provider-failure",
        "graham-growth",
        _arguments("graham-growth"),
        0,
        quote_failure_kind=ProviderFailureKind.UNREACHABLE,
    ),
)


class _ClassifyingProvider:
    """Wraps a fixture provider, re-raising its provider failures with a chosen kind, or with none."""

    def __init__(self, delegate: FinancialFactsProvider, kind: ProviderFailureKind | None) -> None:
        self._delegate = delegate
        self._kind = kind

    def fetch_facts(self, request: FinancialFactRequest, *, effective_as_of: datetime) -> tuple[ProviderFact, ...]:
        try:
            return self._delegate.fetch_facts(request, effective_as_of=effective_as_of)
        except FinancialProviderError as error:
            if self._kind is None:
                raise FinancialProviderError(str(error)) from error
            raise FinancialProviderError(str(error), kind=self._kind, provider_id=request.provider_id) from error


class _FailingQuoteProvider:
    """Wraps a fixture provider so that only the current-price request fails, with a kind."""

    def __init__(self, delegate: FinancialFactsProvider, kind: ProviderFailureKind) -> None:
        self._delegate = delegate
        self._kind = kind

    def fetch_facts(self, request: FinancialFactRequest, *, effective_as_of: datetime) -> tuple[ProviderFact, ...]:
        if request.field_name is FinancialField.CURRENT_PRICE:
            raise FinancialProviderError("fixture quote failure", kind=self._kind, provider_id=request.provider_id)
        return self._delegate.fetch_facts(request, effective_as_of=effective_as_of)


def _fcf_provider(case: Case, yahoo: type[_FixtureYahoo]) -> ProductionFinancialFactsProvider:
    """Compose the FCF command's provider from the case's annual facts, relabeled as SEC EDGAR."""
    facts = (case.fcf_facts or _fcf_success_facts)()
    relabeled = tuple(
        replace(fact, provider_id=SEC_PROVIDER_ID, provider_fact_id=f"fy-{fact.fiscal_year}:{fact.field_name.value}")
        for fact in facts
    )
    sec_edgar: FinancialFactsProvider = FixtureAnnualFinancialFactsProvider(relabeled, error_field=case.fcf_error_field)
    if case.failure_kind is not None:
        sec_edgar = _ClassifyingProvider(sec_edgar, case.failure_kind)
    return ProductionFinancialFactsProvider(
        sec_edgar=sec_edgar,
        yfinance=YFinanceFinancialFactsAdapter(client=cast(YFinanceClient, yahoo())),
    )


def _enter_providers(stack: ExitStack, case: Case) -> None:
    """Replace the command's providers with the case's deterministic fixtures."""
    enter_fixture_providers(stack, case.command)
    wrapper: FinancialFactsProvider | None = None
    if case.command != "fcf-growth":
        if case.failure_kind is not None or case.unclassified:
            wrapper = _ClassifyingProvider(SecLabeledGrahamProvider(), case.failure_kind)
        elif case.quote_failure_kind is not None:
            wrapper = _FailingQuoteProvider(SecLabeledGrahamProvider(), case.quote_failure_kind)
    if wrapper is not None:
        resolver_type = GrahamGrowthInputResolver if case.command == "graham-growth" else GrahamNumberInputResolver
        resolver = resolver_type(wrapper, clock=lambda: NOW)
        for graham in ("graham_number", "graham_growth"):
            stack.enter_context(
                patch(
                    f"investment_analysis_engine.strategies.{graham}.cli.build_graham_resolver", return_value=resolver
                )
            )
    for strategy in ("momentum", "graham_number", "graham_growth"):
        stack.enter_context(patch(f"investment_analysis_engine.strategies.{strategy}.cli.YFinanceClient", case.yahoo))
    stack.enter_context(
        patch(
            "investment_analysis_engine.strategies.fcf_growth.cli.build_sec_production_provider",
            side_effect=lambda *_a, **_k: _fcf_provider(case, case.yahoo),
        )
    )


def _migrated(directory: Path) -> ProjectSettings:
    """Create a migrated database in ``directory`` and return settings that point at it."""
    url = migrated_database_url(directory)
    return ProjectSettings(**(real_settings.model_dump() | {"database_url": url}))


def _replay(settings: ProjectSettings, run_id: str) -> CommandOutput:
    """Replay one stored run as JSON."""
    with ExitStack() as stack:
        stack.enter_context(patch("investment_analysis_engine.cli_workspace.settings", settings))
        stack.enter_context(patch("investment_analysis_engine.cli_support.settings", settings))
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


@cache
def run_saved(case: Case) -> tuple[CommandOutput, CommandOutput, AnalysisRun]:
    """Run the case's direct command once with ``--json --save-run``, then replay the run it saved.

    Returns the direct command's output, the replay's output and the saved run. All three come from the one run, in
    a temporary database, against the one set of providers; a repeated call for the same case returns the first
    result.
    """
    with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
        settings = _migrated(Path(directory))
        for module in ("investment_analysis_engine.cli_run_support", "investment_analysis_engine.cli_support"):
            stack.enter_context(patch(f"{module}.settings", settings))
        _enter_providers(stack, case)
        result = CliRunner().invoke(app, [*case.arguments, "--json", "--save-run"])
        direct = CommandOutput(result.exit_code, normalize(result.stdout_bytes), result.stderr_bytes)
        assert direct.exit_code == case.exit_code, result.output
        run = _single_run(settings)
        return direct, _replay(settings, str(run.analysis_run_id)), run


def run_pair(case: Case) -> tuple[CommandOutput, CommandOutput]:
    """Return the direct command's output and the replay's output for ``case``; see :func:`run_saved`."""
    direct, replayed, _run = run_saved(case)
    return direct, replayed


def replay_stored_run(run: AnalysisRun) -> CommandOutput:
    """Insert ``run`` into a temporary database and replay it as JSON."""
    with tempfile.TemporaryDirectory() as directory:
        settings = _migrated(Path(directory))
        SQLiteAnalysisRunRepository(SQLiteDatabase(settings)).insert(run)
        return _replay(settings, str(run.analysis_run_id))


def _fcf_invalid_input_result(replay: ModuleType) -> FCFEarningsGrowthResult:
    """A stored FCF result in the shape the analyzer writes for an invalid request, which no command can reach."""
    reason = "subject_id and currency are required."
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
    from tests.workspace import test_graham_growth_codec as growth_codec  # noqa: PLC0415
    from tests.workspace import test_graham_number_codec as number_codec  # noqa: PLC0415
    from tests.workspace_documents import (  # noqa: PLC0415 - test helpers, imported late
        test_analysis_run_replay as replay,
    )

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
            direct, replayed = run_pair(case)
            return direct if kind == "direct" else replayed
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
