"""The test helper that asks each wiring surface whether it covers each descriptor, for T10 and the T12 control.

A surface is a function of a closed tuple of descriptors that returns the gaps one table or file has for them. The
helper asks every surface about one descriptor at a time and writes one diagnostic per uncovered strategy, naming
each surface that does not cover it.
"""

from collections.abc import Callable, Mapping
from pathlib import Path

from investment_analysis_engine.cli_strategy_wiring import CLI_STRATEGIES, CliStrategy
from investment_analysis_engine.evaluation.strategy_fixtures import EVALUATION_STRATEGIES, EvaluationStrategy
from investment_analysis_engine.strategy_wiring import StrategyDescriptor
from scripts import strategy_conformance as conformance
from scripts.generate_schemas import SCHEMA_DIRECTORY

type Surface = Callable[[tuple[StrategyDescriptor, ...]], list[str]]
"""One wiring surface: the gaps a table or a file has for the descriptors it is asked about."""


def wiring_surfaces(
    cli_tier: tuple[CliStrategy, ...] = CLI_STRATEGIES,
    evaluation_tier: tuple[EvaluationStrategy, ...] = EVALUATION_STRATEGIES,
    schema_directory_of: Callable[[StrategyDescriptor], Path] = lambda _item: SCHEMA_DIRECTORY,
) -> dict[str, Surface]:
    """Return the surfaces that are still a table or a file, over the supplied tiers.

    The published schemas are looked up in the folder ``schema_directory_of`` names for each descriptor, the
    repository's ``schemas`` folder by default.
    """
    return {
        "CLI tier": lambda descriptors: conformance.cli_tier_gaps(descriptors, cli_tier),
        "evaluation tier": lambda descriptors: conformance.evaluation_tier_gaps(descriptors, evaluation_tier),
        "published schemas": lambda descriptors: conformance.published_schema_gaps(
            descriptors, schema_directory_of(descriptors[0])
        ),
    }


def find_wiring_gaps(descriptors: tuple[StrategyDescriptor, ...], surfaces: Mapping[str, Surface]) -> list[str]:
    """Return ``strategy <key> is not wired in: <surface>; <surface>`` for each descriptor a surface does not cover."""
    gaps = []
    for item in descriptors:
        key = conformance.label(item)
        uncovered = [name for name, surface in surfaces.items() if any(key in gap for gap in surface((item,)))]
        if uncovered:
            gaps.append(f"strategy {key} is not wired in: {'; '.join(uncovered)}")
    return gaps


def assert_wired(descriptors: tuple[StrategyDescriptor, ...], surfaces: Mapping[str, Surface]) -> None:
    """Fail with every diagnostic of :func:`find_wiring_gaps`, or return when every surface covers every descriptor."""
    gaps = find_wiring_gaps(descriptors, surfaces)
    assert not gaps, "\n".join(gaps)
