"""The context every application operation takes as its first argument."""

from dataclasses import dataclass

from investment_analysis_engine.config import ProjectSettings


@dataclass(frozen=True)
class ApplicationContext:
    """What an operation needs from its caller.

    The caller builds it at call time, so an operation never reads a module-level settings object.
    """

    settings: ProjectSettings


__all__ = ["ApplicationContext"]
