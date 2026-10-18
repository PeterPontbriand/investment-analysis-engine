"""The specimen's site context: what the conformance checks look at to find it done.

The checks that run for a production strategy run here unchanged, over the specimen's descriptor, tiers, command
application, files and stored run. Two sites are type-level and closed to the specimen: the ``ToolName`` member
and the two production unions. The context lists them as covered by the generator's end-to-end test, which adds a
strategy to a temporary copy of the repository through the real declarations.
"""

import asyncio
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Final, cast

import typer

from investment_analysis_engine.analysis.run_models import RunOutcome
from investment_analysis_engine.cli_strategy_wiring import add_strategy_commands
from investment_analysis_engine.evaluation.fixture_context import FixtureContext
from investment_analysis_engine.orchestrator.dispatcher import AsyncToolDispatcher
from investment_analysis_engine.orchestrator.tool_runtime import ToolRuntime
from investment_analysis_engine.orchestrator.types import ToolCallRequest
from investment_analysis_engine.reporting.replay_inputs import ReplayOptions, ReplayProjector
from investment_analysis_engine.strategy_wiring import StrategyDescriptor, build_indexes, tool_for_arguments
from investment_analysis_engine.workspace.codecs import EvidenceCodec
from investment_analysis_engine.workspace.strategy_types import NativeEvidence
from scripts import generate_strategy_docs
from scripts.repository_root import REPOSITORY_ROOT
from scripts.strategy_conformance import PRODUCTION, SiteContext, StoredRun
from scripts.strategy_sites import Gap, StrategyNames, strategy_names
from tests.specimen.analyzer import SpecimenAnalyzer
from tests.specimen.cases import SPECIMEN_CASES
from tests.specimen.cli_tier import SPECIMEN_CLI_STRATEGIES
from tests.specimen.evaluation import GOLDEN_MULTIPLIER, SAMPLE_SELECTION
from tests.specimen.evaluation_tier import SPECIMEN_EVALUATION, SPECIMEN_EVALUATION_STRATEGIES
from tests.specimen.execution import SpecimenExecution
from tests.specimen.runs import build_specimen_run, decode_specimen_run, project_specimen_run
from tests.specimen.vocabulary import ALIAS
from tests.specimen.wiring import SPECIMEN, SPECIMEN_STRATEGIES

SPECIMEN_NAMES: Final[StrategyNames] = strategy_names("specimen", ALIAS)
"""The package name and command alias of the specimen."""

COVERED_BY_GENERATOR: Final = "covered by T28 (generator end-to-end)"
"""Where the two type-level sites are checked, since the specimen cannot be named in the closed declarations."""

SPECIMEN_FOLDER: Final = Path(__file__).resolve().parent
CATALOG_TEST: Final = REPOSITORY_ROOT / "tests" / "test_specimen_strategy.py"
_FOLDER = SPECIMEN_FOLDER.relative_to(REPOSITORY_ROOT).as_posix()
_CLOCK = datetime(2026, 8, 31, 18, 30, tzinfo=UTC)
_FILE_SITES: Final = (
    "vocabulary",
    "analyzer",
    "tool",
    "selection",
    "codec",
    "execution",
    "cli",
    "presenter",
    "envelope",
    "replay",
    "evaluation",
    "cases",
    "catalog",
)
_PATHS: Final = {
    **{site_id: f"{_FOLDER}/{site_id}.py" for site_id in _FILE_SITES},
    "settings": f"{_FOLDER}/settings.toml",
    "descriptor": f"{_FOLDER}/wiring.py",
    "cli-tier": f"{_FOLDER}/cli_tier.py",
    "evaluation-tier": f"{_FOLDER}/evaluation_tier.py",
    "guide": f"{_FOLDER}/{{guide}}.md",
    "schema": f"{_FOLDER}/{{alias}}.schema.json",
}


def specimen_app() -> typer.Typer:
    """Build a command application holding the production strategy commands and the specimen's, and nothing else."""
    application = typer.Typer()

    @application.callback()
    def root() -> None:
        """Hold the commands."""

    add_strategy_commands(application, SPECIMEN_STRATEGIES, SPECIMEN_CLI_STRATEGIES)
    return application


def specimen_stored_run() -> StoredRun:
    """Return the specimen's result stored under the sample selection its evaluation-tier entry declares."""
    result = SpecimenAnalyzer(multiplier=GOLDEN_MULTIPLIER).run_analysis(
        "SPEC", SAMPLE_SELECTION.to_specimen_config(), SAMPLE_SELECTION.to_analysis_context(_CLOCK)
    )
    run = build_specimen_run("SPEC", SAMPLE_SELECTION, SpecimenExecution(result, RunOutcome.COMPLETED))

    def decode(codecs: Mapping[tuple[str, str], EvidenceCodec]) -> NativeEvidence | None:
        return decode_specimen_run(run, codecs)

    def project(
        options: ReplayOptions,
        codecs: Mapping[tuple[str, str], EvidenceCodec],
        replays: Mapping[tuple[str, str], ReplayProjector],
    ) -> str:
        return project_specimen_run(run, options, codecs=codecs, replays=replays)

    return StoredRun(
        SPECIMEN,
        SPECIMEN_EVALUATION.sample_selection,
        cast("NativeEvidence", result),
        run.ticker,
        run,
        decode,
        project,
    )


def _stored_run(item: StrategyDescriptor) -> StoredRun | None:
    return specimen_stored_run() if item is SPECIMEN else PRODUCTION.stored_run(item)


def _case_ids(item: StrategyDescriptor) -> list[str]:
    return [case.case_id for case in SPECIMEN_CASES] if item is SPECIMEN else PRODUCTION.case_ids(item)


def _served(item: StrategyDescriptor) -> list[str]:
    """Dispatch each specimen case through the real dispatcher and compare the result type with the descriptor's."""
    if item is not SPECIMEN:
        return PRODUCTION.served(item)
    if not SPECIMEN_CASES:
        return [f"descriptor {item.alias!r} tool {item.tool.value} is required by no case"]
    gaps = []
    by_arguments = build_indexes(SPECIMEN_STRATEGIES).by_arguments
    for case in SPECIMEN_CASES:
        if tool_for_arguments(case.arguments, by_arguments) is not item.tool:
            gaps.append(f"case {case.case_id}: its arguments do not route to {item.tool.value}")
            continue
        context = FixtureContext(SPECIMEN_EVALUATION.requirement.required_ids, _CLOCK, None)
        handler = item.behavior.bind_handler(SPECIMEN_EVALUATION.compose(context), ToolRuntime(clock=lambda: _CLOCK))
        dispatcher = AsyncToolDispatcher()
        dispatcher.register_tool(item.tool.value, handler)
        request = ToolCallRequest(
            call_id=f"golden:{case.case_id}",
            tool_name=item.tool.value,
            arguments=case.arguments.model_dump(mode="python"),
        )
        outcome = asyncio.run(dispatcher.dispatch(request))
        if not outcome.success:
            gaps.append(f"case {case.case_id}: fixture dispatch failed: {outcome.error_message}")
        elif type(outcome.result) is not item.behavior.result_type:
            gaps.append(f"case {case.case_id}: dispatch returned {type(outcome.result).__name__}")
    return gaps


def _strategy_docs(names: StrategyNames, where: str, descriptors: tuple[StrategyDescriptor, ...]) -> list[Gap]:
    """Render the generated strategy lists over the context's closed tuple and require an entry for the specimen.

    The checked-in lists in the user documents are production-only and never name the specimen, so the specimen
    is done when the generator, given its descriptor, writes its entry.
    """
    renderers = {
        generate_strategy_docs.USAGE_BLOCK_ID: generate_strategy_docs.render_help_commands,
        generate_strategy_docs.WORKSPACE_BLOCK_ID: generate_strategy_docs.render_strategy_table,
    }
    gaps = []
    for block in generate_strategy_docs.strategy_list_blocks():
        rendered = renderers[block.block_id](descriptors)
        if block.lists is None or not block.lists(rendered, names.alias):
            gaps.append(Gap("strategy-docs", where, f"the generated block {block.block_id!r} has no entry for it"))
    return gaps


SPECIMEN_CONTEXT: Final = SiteContext(
    name="specimen",
    descriptors=SPECIMEN_STRATEGIES,
    cli_tier=SPECIMEN_CLI_STRATEGIES,
    evaluation_tier=SPECIMEN_EVALUATION_STRATEGIES,
    app=specimen_app(),
    stored_run=_stored_run,
    case_ids=_case_ids,
    served=_served,
    strategy_docs=_strategy_docs,
    paths=_PATHS,
    selections=(type(SAMPLE_SELECTION),),
    schema_directory=SPECIMEN_FOLDER,
    catalog_test=CATALOG_TEST,
    covered={"tool-name": COVERED_BY_GENERATOR, "unions": COVERED_BY_GENERATOR},
)
"""The context in which the site checks find the specimen done, except the two covered sites."""
