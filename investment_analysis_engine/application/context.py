"""The context every application operation takes as its first argument."""

from dataclasses import dataclass

from investment_analysis_engine.application.provider_check import ProviderCheck
from investment_analysis_engine.config import ProjectSettings


@dataclass(frozen=True)
class ApplicationContext:
    """What an operation needs from its caller.

    The caller builds it at call time, so an operation never reads a module-level settings object.

    Attributes:
        settings: The settings the operation reads, including its database and settings folder.
        provider_probe: The probe an operation that reports a provider failure asks for one test request, or
            ``None`` when the caller offers none, in which case no provider check runs.
    """

    settings: ProjectSettings
    provider_probe: ProviderCheck | None = None


__all__ = ["ApplicationContext"]
