"""Typed models for the two Graham calculation methods.

Defines the shared method discriminator, calculation status enum, and
method-specific result dataclasses.  Pure calculators return one of the
result types; resolver/provider layers (Slice C) will wrap them with
provenance and may produce the additional `input_unavailable` and
`provider_error` statuses.
"""

from dataclasses import dataclass, field
from enum import StrEnum


class GrahamMethod(StrEnum):
    """Explicit method discriminator for Graham valuation calculations."""

    NUMBER = "graham_number"
    GROWTH_VALUE = "graham_growth_value"


class CalculationStatus(StrEnum):
    """Machine-readable outcome of a calculation attempt.

    Pure calculators (Slice B) may return:

    - ``OK`` — required inputs resolved and calculation completed.
    - ``NOT_APPLICABLE`` — inputs are valid but the selected method is
      inapplicable (e.g. non-positive EPS or BVPS for the Graham Number).
    - ``INVALID_INPUT`` — supplied value, unit, basis, or method/flag
      combination is invalid.

    Resolver/provider layers (Slice C and later) will additionally return:

    - ``INPUT_UNAVAILABLE`` — a required input could not be resolved under
      the requested time boundary.
    - ``PROVIDER_ERROR`` — the configured provider failed in a way that
      should be distinguished from an absent fact.
    """

    OK = "ok"
    NOT_APPLICABLE = "not_applicable"
    INVALID_INPUT = "invalid_input"
    INPUT_UNAVAILABLE = "input_unavailable"
    PROVIDER_ERROR = "provider_error"


@dataclass(frozen=True)
class GrahamNumberResult:
    """Typed result of the Graham Number (sqrt(22.5 * EPS * BVPS)) calculation.

    Attributes:
        status: Calculation outcome.
        maximum_indicated_price: The screening-ceiling price.  ``None`` when
            ``status`` is not ``OK``.
        reason: Human-readable explanation when ``status`` is not ``OK``.
        method: Always ``GrahamMethod.NUMBER`` (set automatically, not
            caller-supplied).
    """

    status: CalculationStatus
    maximum_indicated_price: float | None = None
    reason: str | None = None
    method: GrahamMethod = field(init=False, default=GrahamMethod.NUMBER)

    def __post_init__(self) -> None:
        """Enforce result-state invariants."""
        if self.status is CalculationStatus.OK:
            if self.maximum_indicated_price is None:
                raise ValueError("GrahamNumberResult: status OK requires maximum_indicated_price to be present.")
        else:
            if self.maximum_indicated_price is not None:
                raise ValueError(
                    f"GrahamNumberResult: status {self.status} requires maximum_indicated_price to be None."
                )
            if not self.reason:
                raise ValueError(f"GrahamNumberResult: status {self.status} requires a non-empty reason.")


@dataclass(frozen=True)
class GrahamGrowthValueResult:
    """Typed result of the Graham growth-value calculation.

    Attributes:
        status: Calculation outcome.
        growth_value: The forecast-dependent growth estimate.  ``None`` when
            ``status`` is not ``OK``.
        reason: Human-readable explanation when ``status`` is not ``OK``.
        method: Always ``GrahamMethod.GROWTH_VALUE`` (set automatically, not
            caller-supplied).
    """

    status: CalculationStatus
    growth_value: float | None = None
    reason: str | None = None
    method: GrahamMethod = field(init=False, default=GrahamMethod.GROWTH_VALUE)

    def __post_init__(self) -> None:
        """Enforce result-state invariants."""
        if self.status is CalculationStatus.OK:
            if self.growth_value is None:
                raise ValueError("GrahamGrowthValueResult: status OK requires growth_value to be present.")
        else:
            if self.growth_value is not None:
                raise ValueError(f"GrahamGrowthValueResult: status {self.status} requires growth_value to be None.")
            if not self.reason:
                raise ValueError(f"GrahamGrowthValueResult: status {self.status} requires a non-empty reason.")
