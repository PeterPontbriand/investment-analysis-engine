"""Golden-Suite evaluation infrastructure.

This package owns benchmark case contracts, deterministic evaluation,
machine-readable evaluation reporting, and the optional local-model evaluation
harness introduced in Milestone v0.2 Step 2.5. Financial calculations remain
owned by their strategy packages, and benchmark fixtures remain separate from
production cache and persistence data.
"""

from src.evaluation.models import (
    BehaviorConstraints,
    Case,
    ComponentKind,
    ComponentOutcome,
    ComponentResult,
    DomainOutcomeExpectation,
    DomainOutcomeObservation,
    ExecutionMode,
    Expectation,
    GrahamMethod,
    GrahamMethodConstraints,
    GrahamMethodObservation,
    NumericalExpectation,
    NumericalObservation,
    Observation,
    ToolCallObservation,
    ToolConstraints,
    ToolName,
)

__all__ = [
    "BehaviorConstraints",
    "Case",
    "ComponentKind",
    "ComponentOutcome",
    "ComponentResult",
    "DomainOutcomeExpectation",
    "DomainOutcomeObservation",
    "ExecutionMode",
    "Expectation",
    "GrahamMethod",
    "GrahamMethodConstraints",
    "GrahamMethodObservation",
    "NumericalExpectation",
    "NumericalObservation",
    "Observation",
    "ToolCallObservation",
    "ToolConstraints",
    "ToolName",
]
