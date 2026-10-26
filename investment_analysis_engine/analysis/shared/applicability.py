"""Industry class from an SEC SIC code, and the sector rules of the screening strategies.

The class comes from the SIC code as filed with the anchor annual filing, never from the issuer's current code. The
ranges and the strategy matrix are the ones in the Step 3.5 shared definitions. The functions are pure: they take a
code or a class and return a class or an outcome, with no I/O.
"""

from dataclasses import dataclass
from enum import StrEnum

from investment_analysis_engine.core.metric_result import ReasonCode

_FINANCIAL_RANGE = range(6000, 6800)
_UTILITY_RANGE = range(4900, 5000)
_MANUFACTURER_RANGE = range(2000, 4000)


class IndustryClass(StrEnum):
    """Industry class of an issuer. An unknown class is the absence of a value, never a member."""

    FINANCIAL = "financial"
    UTILITY = "utility"
    MANUFACTURER = "manufacturer"
    OTHER = "other"


class Applicability(StrEnum):
    """How a strategy treats an issuer's industry class."""

    APPLIES = "applies"
    APPLIES_WITH_WARNING = "applies_with_warning"
    NOT_APPLICABLE = "not_applicable"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class SectorGate:
    """The industry classes a strategy refuses or warns about, and whether an unknown class stops it."""

    gated: bool
    not_applicable: frozenset[IndustryClass] = frozenset()
    warn: frozenset[IndustryClass] = frozenset()

    def __post_init__(self) -> None:
        """Reject a class that is both refused and warned about."""
        if self.not_applicable & self.warn:
            raise ValueError("A class cannot be both not applicable and a warning.")


@dataclass(frozen=True)
class ApplicabilityOutcome:
    """A strategy's applicability for one issuer, with the reason code of a non-applying outcome.

    ``NOT_APPLICABLE`` maps to ``MetricStatus.NOT_APPLICABLE`` and ``UNAVAILABLE`` to ``MetricStatus.UNAVAILABLE``
    where a strategy turns the outcome into a metric. ``industry_class`` is ``None`` when the class is unknown.
    """

    outcome: Applicability
    reason_code: ReasonCode | None
    industry_class: IndustryClass | None

    def __post_init__(self) -> None:
        """Require a reason code exactly for the two outcomes that stop a strategy."""
        needs_code = self.outcome in (Applicability.NOT_APPLICABLE, Applicability.UNAVAILABLE)
        if needs_code != (self.reason_code is not None):
            raise ValueError("Only a not-applicable or unavailable outcome carries a reason code.")


PIOTROSKI_GATE = SectorGate(gated=False, warn=frozenset({IndustryClass.FINANCIAL}))
ALTMAN_GATE = SectorGate(gated=True, not_applicable=frozenset({IndustryClass.FINANCIAL}))
BENEISH_GATE = SectorGate(gated=True, not_applicable=frozenset({IndustryClass.FINANCIAL}))
VALUATION_MULTIPLES_GATE = SectorGate(gated=True, not_applicable=frozenset({IndustryClass.FINANCIAL}))
MAGIC_FORMULA_GATE = SectorGate(gated=True, not_applicable=frozenset({IndustryClass.FINANCIAL, IndustryClass.UTILITY}))
INTEREST_COVERAGE_GATE = SectorGate(gated=True, not_applicable=frozenset({IndustryClass.FINANCIAL}))
ROIC_GATE = SectorGate(gated=True, not_applicable=frozenset({IndustryClass.FINANCIAL}))


def industry_class_of_sic(code: int) -> IndustryClass:
    """Return the industry class of a four-digit SIC code.

    A code in none of the three ranges is an ordinary non-financial, non-manufacturing issuer.

    Raises:
        ValueError: *code* is not between 1 and 9999.
    """
    if not 1 <= code <= 9999:
        raise ValueError("A SIC code has four digits and is not 0000.")
    if code in _FINANCIAL_RANGE:
        return IndustryClass.FINANCIAL
    if code in _UTILITY_RANGE:
        return IndustryClass.UTILITY
    if code in _MANUFACTURER_RANGE:
        return IndustryClass.MANUFACTURER
    return IndustryClass.OTHER


def applicability_of(gate: SectorGate, industry_class: IndustryClass | None) -> ApplicabilityOutcome:
    """Decide a strategy's applicability from its gate and the issuer's class, which is ``None`` when unknown.

    An unknown class stops a gated strategy (``UNAVAILABLE``) and leaves an ungated one applying, with the class
    still unknown in the outcome so the strategy can say so.
    """
    if industry_class is None:
        if gate.gated:
            return ApplicabilityOutcome(Applicability.UNAVAILABLE, ReasonCode.INDUSTRY_CLASS_UNKNOWN, None)
        return ApplicabilityOutcome(Applicability.APPLIES, None, None)
    if industry_class in gate.not_applicable:
        return ApplicabilityOutcome(
            Applicability.NOT_APPLICABLE, ReasonCode.INDUSTRY_CLASS_NOT_APPLICABLE, industry_class
        )
    if industry_class in gate.warn:
        return ApplicabilityOutcome(Applicability.APPLIES_WITH_WARNING, None, industry_class)
    return ApplicabilityOutcome(Applicability.APPLIES, None, industry_class)
