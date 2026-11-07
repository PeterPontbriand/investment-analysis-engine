"""The specimen's application functions: its settings and its run function.

The settings path of the composition root is exercised here: the multiplier comes from the specimen's
``settings.toml``, overridden per key by the user's ``strategies/specimen-test.toml`` in the context's settings folder.
"""

from datetime import datetime

from investment_analysis_engine.application.context import ApplicationContext
from investment_analysis_engine.application.strategy_run import StrategyRun
from investment_analysis_engine.config.component_settings import load_component_settings
from investment_analysis_engine.core.provider_check_element import ProviderCheckItem
from investment_analysis_engine.data.instrument_profile_cache import InstrumentProfileResolver
from investment_analysis_engine.reporting.replay_inputs import TextPresentationMode
from investment_analysis_engine.workspace.capture import ExecutionCapture
from tests.specimen.analyzer import SpecimenAnalyzer
from tests.specimen.closed_types import as_native_evidence
from tests.specimen.codec import specimen_native_status
from tests.specimen.presenter import build_specimen_document, render_specimen
from tests.specimen.selection import SpecimenSelection
from tests.specimen.settings import SpecimenSettings
from tests.specimen.vocabulary import ALIAS
from tests.specimen.workspace import execute_specimen, from_specimen_capture


def specimen_settings(context: ApplicationContext) -> SpecimenSettings:
    """Return the specimen's validated settings from the context's settings folder, loaded once per folder."""
    return load_component_settings(ALIAS, SpecimenSettings, context.settings.config_dir)


def specimen_analyzer(context: ApplicationContext) -> SpecimenAnalyzer:
    """Compose the analyzer with the configured multiplier."""
    return SpecimenAnalyzer(multiplier=specimen_settings(context).multiplier)


def run(
    context: ApplicationContext,
    ticker: str,
    selection: SpecimenSelection,
    /,
    *,
    executed_at: datetime,
    profile_cache: InstrumentProfileResolver | None,
) -> StrategyRun:
    """Run the specimen once; the calculation reads no profile, so the cache is unused."""
    del profile_cache
    capture = execute_specimen(specimen_analyzer(context), ticker, selection, executed_at=executed_at)
    execution = from_specimen_capture(capture)
    result = capture.result

    def render_text(element: tuple[ProviderCheckItem, ...] | None, mode: TextPresentationMode) -> str:
        del element
        return render_specimen(result, mode)

    return StrategyRun(
        execution=ExecutionCapture(
            native_evidence=as_native_evidence(execution.native_evidence),
            profile=None,
            native_status=specimen_native_status(execution.native_evidence),
        ),
        document=lambda _element: build_specimen_document(result),
        render_text=render_text,
    )
