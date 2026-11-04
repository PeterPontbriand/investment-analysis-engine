"""The documents only the API serves: the engine information, the strategy list and the replay text."""

from importlib.metadata import version
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from investment_analysis_engine.reporting.replay_inputs import TextPresentationMode
from investment_analysis_engine.strategy_wiring import STRATEGIES

API_VERSIONS: tuple[str, ...] = ("v1",)
"""The API versions this engine serves, as the first path segment of their endpoints."""

ENGINE_DISTRIBUTION = "investment-analysis-engine"
"""The name of the installed distribution whose version the information document reports."""


def installed_engine_version() -> str:
    """Return the installed version of the engine distribution.

    Raises:
        importlib.metadata.PackageNotFoundError: If the distribution is not installed.
    """
    return version(ENGINE_DISTRIBUTION)


class InfoDocument(BaseModel):
    """What a client may learn about the engine it is talking to; it never holds a credential's value."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal[1] = 1
    api_versions: tuple[str, ...] = Field(description="The API versions this engine serves, such as v1.")
    engine_version: str = Field(description="The version of the engine package.")
    sec_identity_configured: bool = Field(
        description="Whether an SEC identity is configured; its value is never shown."
    )


class StrategyItem(BaseModel):
    """One strategy this engine supports."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    analysis: str = Field(description="The analysis identifier, as a strategy document's analysis key names it.")
    method: str = Field(description="The method identifier, as a strategy document's method key and a run's method_id.")
    label: str = Field(description="The name a person sees.")


class StrategiesDocument(BaseModel):
    """The strategies this engine supports, in the order they are declared."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal[1] = 1
    items: tuple[StrategyItem, ...]


class ReplayTextDocument(BaseModel):
    """A saved run replayed as text in one presentation mode."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal[1] = 1
    mode: TextPresentationMode = Field(description="The presentation mode of the text.")
    text: str = Field(description="The text the mode shows, as the command line would print it.")


def build_info_document(*, engine_version: str, sec_identity_configured: bool) -> InfoDocument:
    """Build the information document."""
    return InfoDocument(
        api_versions=API_VERSIONS, engine_version=engine_version, sec_identity_configured=sec_identity_configured
    )


def build_strategies_document() -> StrategiesDocument:
    """Build the strategies document from the declared strategies."""
    return StrategiesDocument(
        items=tuple(
            StrategyItem(analysis=item.analysis_id, method=item.method_id, label=item.label) for item in STRATEGIES
        )
    )


def build_replay_text_document(mode: TextPresentationMode, text: str) -> ReplayTextDocument:
    """Build the replay text document for a text presentation mode."""
    return ReplayTextDocument(mode=mode, text=text)


__all__ = [
    "API_VERSIONS",
    "InfoDocument",
    "ReplayTextDocument",
    "StrategiesDocument",
    "StrategyItem",
    "build_info_document",
    "build_replay_text_document",
    "build_strategies_document",
]
