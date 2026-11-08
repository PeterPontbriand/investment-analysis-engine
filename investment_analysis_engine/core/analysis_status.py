"""Shared status contract for deterministic analysis and input resolution."""

from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType
from typing import Final


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


CALCULATION_STATUS_TERMS: Final[Mapping[str, str]] = MappingProxyType(
    {
        CalculationStatus.OK.value: "status-ok",
        CalculationStatus.NOT_APPLICABLE.value: "not-applicable",
        CalculationStatus.INVALID_INPUT.value: "status-invalid-input",
        CalculationStatus.INPUT_UNAVAILABLE.value: "status-input-unavailable",
        CalculationStatus.PROVIDER_ERROR.value: "status-provider-error",
    }
)
"""The glossary term that explains each calculation status."""
