"""Direct analysis: one ticker under one selection, run now and optionally saved.

:func:`analyze` is the one execution path of a direct analysis. It finds the strategy that owns the selection in the
application tier, runs it through that strategy's own run function, saves the run when asked, runs the provider check
after a failure and returns an :class:`AnalysisOutcome`. Nothing here names a strategy: each strategy's ``application``
module builds the document and the text of its own run, and the outcome carries only what every caller needs.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from investment_analysis_engine.analysis.run_models import RunOutcome
from investment_analysis_engine.application.context import ApplicationContext
from investment_analysis_engine.application.failures import SaveStage, saving_failures
from investment_analysis_engine.application.parameters import ActionParameterError
from investment_analysis_engine.application.provider_check import (
    ProviderCheckChoice,
    ProviderCheckFindings,
    provider_check_findings,
    with_provider_check,
)
from investment_analysis_engine.application.providers import build_provider_probe, production_instrument_profile_cache
from investment_analysis_engine.application.strategy_run import StrategyRun
from investment_analysis_engine.application.tier import analysis_runner_for
from investment_analysis_engine.core.clock import utc_now
from investment_analysis_engine.core.tickers import normalize_ticker
from investment_analysis_engine.data.repositories.readiness import ensure_database_ready
from investment_analysis_engine.data.repositories.sqlite import SQLiteDatabase
from investment_analysis_engine.reporting.replay_inputs import TextPresentationMode
from investment_analysis_engine.strategy_wiring import run_spec_for
from investment_analysis_engine.workspace.capture import ExecutionCapture
from investment_analysis_engine.workspace.execution import execute
from investment_analysis_engine.workspace.repositories.analysis_runs import SQLiteAnalysisRunRepository
from investment_analysis_engine.workspace.requests import AnalysisRequest
from investment_analysis_engine.workspace.runs import AnalysisRun
from investment_analysis_engine.workspace.strategy_types import SelectionMember


def exit_code_of(outcome: RunOutcome) -> int:
    """Return the exit code of a strategy command whose run had ``outcome``: 1 for unavailable and failed, else 0.

    These are also the outcomes after which a direct analysis is a failure and the provider check runs.
    """
    return 1 if outcome in (RunOutcome.UNAVAILABLE, RunOutcome.FAILED) else 0


@dataclass(frozen=True)
class AnalysisOutcome:
    """The result of one direct analysis, which holds no raw execution and no strategy-specific type.

    Attributes:
        document: The strategy's typed document, as ``--json`` writes it, provider-check element included.
        analysis_run_id: The saved run's ID, or ``None`` when the run was not saved.
        outcome: The run's outcome, from which a command sets its exit code.
        text_renderer: Renders the run in a text mode; call it through :meth:`render_text`.
    """

    document: BaseModel
    analysis_run_id: UUID | None
    outcome: RunOutcome
    text_renderer: Callable[[TextPresentationMode], str]

    def render_text(self, mode: TextPresentationMode) -> str:
        """Return the run rendered in a text mode, with the provider-check lines first after a failure."""
        return self.text_renderer(mode)


def _run_and_save(  # noqa: PLR0913
    context: ApplicationContext,
    runner: Callable[..., StrategyRun],
    ticker: str,
    selection: SelectionMember,
    *,
    executed_at: datetime,
    stage: SaveStage,
) -> tuple[StrategyRun, UUID]:
    """Run once and persist the terminal run, checking storage readiness before any provider call.

    The database is opened and checked first, so a storage failure is reported before any provider work. The run is
    inserted before anything is reported saved. Because a database is already open for storage, the run also receives
    a durable instrument-profile cache over that same database.
    """
    request = AnalysisRequest(ticker=ticker, selection=selection)
    database = SQLiteDatabase(context.settings)
    try:
        ensure_database_ready(database)
        repository = SQLiteAnalysisRunRepository(database)
        profile_cache = production_instrument_profile_cache(context, database, clock=lambda: executed_at)
        holder: list[StrategyRun] = []

        def capture() -> ExecutionCapture:
            run = runner(context, ticker, selection, executed_at=executed_at, profile_cache=profile_cache)
            holder.append(run)
            return run.execution

        saved: AnalysisRun = execute(
            request,
            spec=run_spec_for(selection),
            capture=stage.after_analysis(capture),
            repository=repository,
        )
        return holder[0], saved.analysis_run_id
    finally:
        database.close()


def analyze(
    context: ApplicationContext,
    ticker: str,
    selection: SelectionMember,
    *,
    save: bool,
    provider_check: bool,
) -> AnalysisOutcome:
    """Analyze one ticker under one selection, saving the run when asked.

    The ticker is checked first, before any database is opened or provider called, and the results are those of the
    normalized ticker.

    Args:
        context: What the operation needs from its caller; the provider check is built from its settings.
        ticker: The ticker as the caller has it; it is trimmed and upper-cased.
        selection: The selection of the strategy to run; its ``as_of`` reaches the document unchanged.
        save: Whether to persist the run as an Analysis Run.
        provider_check: Whether to send one test request to a provider after it fails; false reports that the
            check was turned off.

    Returns:
        The document, the saved run's ID (``None`` when not saved), the run's outcome and the text renderer.

    Raises:
        ActionParameterError: If ``ticker`` is blank (parameter ``ticker``, rule ``analysis.blank_ticker``).
        UndeclaredStrategyError: If no declared strategy owns the selection.
        SavingFailureError: If the analysis finished but its result could not be saved.
    """
    try:
        ticker = normalize_ticker(ticker)
    except ValueError:
        raise ActionParameterError(
            "{ticker} must be a non-empty symbol.", parameters=("ticker",), rule="analysis.blank_ticker"
        ) from None
    runner = analysis_runner_for(selection)
    executed_at = utc_now()
    stage = SaveStage()
    run_id: UUID | None = None
    with saving_failures(stage):
        if save:
            run, run_id = _run_and_save(context, runner, ticker, selection, executed_at=executed_at, stage=stage)
        else:
            run = runner(context, ticker, selection, executed_at=executed_at, profile_cache=None)
    outcome = run.execution.outcome
    failed = bool(exit_code_of(outcome))
    findings: ProviderCheckFindings = provider_check_findings(
        (run.execution.provider_failure,) if failed else (),
        ProviderCheckChoice(build_provider_probe(context), requested=provider_check),
    )
    element = findings.element()

    def render_text(mode: TextPresentationMode) -> str:
        text = run.render_text(element, mode)
        return with_provider_check(text, findings, mode) if failed else text

    return AnalysisOutcome(
        document=run.document(element), analysis_run_id=run_id, outcome=outcome, text_renderer=render_text
    )


__all__ = ["AnalysisOutcome", "analyze", "exit_code_of"]
