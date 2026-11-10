"""Aligning a Graham strategy's filing inputs to the shared anchor filing.

Graham Number and Graham Growth Value resolve their own EPS and book value per share. Each filing input must end at the
anchor filing's fiscal year-end, by actual dates and with no tolerance, exactly as the shared year-end share count and
FCF Growth's yield do. An input that ends on another day is unavailable: a Graham strategy never steps back to an older
year. An overridden input has no year and is exempt.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from investment_analysis_engine.analysis.shared.metric_evidence import InputUnavailable
from investment_analysis_engine.analysis.shared.metric_inputs import MetricInputsFailure, resolve_at_anchor_year
from investment_analysis_engine.core.analysis_status import CalculationStatus
from investment_analysis_engine.core.provider_failure_kind import ProviderFailureRecord
from investment_analysis_engine.data.financial.provenance import SourceKind
from investment_analysis_engine.data.financial.resolver import InputResolutionResult, InputResolver
from investment_analysis_engine.data.sec_edgar.financial_facts import AnchorYearEnd


class GrahamFilingInput(StrEnum):
    """A filing input of a Graham strategy, with the words its year message uses."""

    EPS = "eps"
    BVPS = "bvps"

    @property
    def newest_year(self) -> str:
        """Return the phrase that names the newest year of the input."""
        if self is GrahamFilingInput.EPS:
            return "The newest fiscal year of diluted EPS ends"
        return "The newest book value per common share is for the fiscal year ended"


@dataclass(frozen=True)
class AnchorYearRule:
    """What a strategy's year messages name.

    Attributes:
        method_name: The method's name as the message states it, such as ``Graham Number``.
    """

    method_name: str


def year_mismatch_reason(
    rule: AnchorYearRule, which: GrahamFilingInput, *, newest_end: date | None, anchor_year_end: date
) -> str:
    """Return the reason for an input whose newest year does not end at the anchor filing's fiscal year-end."""
    anchor = f"the anchor filing's fiscal year-end {anchor_year_end.isoformat()}"
    never = f"the {rule.method_name} is never calculated from an older year."
    if newest_end is None:
        return f"The newest {which.value.upper()} carries no period end, so it is not {anchor}; {never}"
    return f"{which.newest_year} {newest_end.isoformat()}, not {anchor}; {never}"


def resolve_aligned(  # noqa: PLR0913
    resolver: InputResolver,
    resolve: Callable[[], InputResolutionResult],
    *,
    anchor: AnchorYearEnd | None,
    rule: AnchorYearRule,
    which: GrahamFilingInput,
    overridden: bool,
) -> InputResolutionResult:
    """Resolve one filing input at the anchor's fiscal year, or return why it is not for that year.

    A cached entry of another fiscal year is set aside and the provider asked once (see ``resolve_at_anchor_year``). An
    overridden input is returned as it is. Any other status is returned as it is, so a provider failure stays one.

    Raises:
        ValueError: If an input to be taken from a filing is resolved without an anchor.
    """
    if overridden:
        return resolve()
    if anchor is None:
        raise ValueError("A filing input is never resolved without the anchor filing.")
    result = resolve_at_anchor_year(resolver, resolve, year_end=anchor.year_end)
    held = result.resolved_input
    if result.status is not CalculationStatus.OK or held is None or held.source_kind is SourceKind.OVERRIDE:
        return result
    newest_end = None if held.observation_period_end is None else held.observation_period_end.date()
    if newest_end == anchor.year_end:
        return result
    return InputResolutionResult(
        status=CalculationStatus.INPUT_UNAVAILABLE,
        reason=year_mismatch_reason(rule, which, newest_end=newest_end, anchor_year_end=anchor.year_end),
        resolution_trace=result.resolution_trace,
        specific_reason=True,
    )


@dataclass(frozen=True)
class AnchorStop:
    """Why a Graham run stopped before it read any filing input: the anchor filing could not be resolved.

    Attributes:
        status: ``provider_error`` for a provider failure, ``input_unavailable`` when there is no anchor.
        reason: The explanation; the anchor's own message when there is no anchor.
        provider_failure: The failure recorded against ``anchor_year_end``; ``None`` for an unclassified failure and
            when there is no failure.
        specific_reason: Whether ``reason`` is shown to an investor as it is: the anchor's message is, a provider
            failure's is not.
    """

    status: CalculationStatus
    reason: str
    provider_failure: ProviderFailureRecord | None
    specific_reason: bool


def anchor_stop(anchor: InputUnavailable | MetricInputsFailure) -> AnchorStop:
    """Return the outcome of an anchor that is not an ``AnchorYearEnd``.

    A provider failure is ``provider_error`` with the failure recorded against ``anchor_year_end``. No anchor, for any
    reason, is ``input_unavailable`` with the anchor's message: the newest facts are never used in its place.
    """
    if isinstance(anchor, MetricInputsFailure):
        return AnchorStop(
            CalculationStatus.PROVIDER_ERROR, f"{anchor.input_name}: {anchor.reason}", anchor.provider_failure, False
        )
    return AnchorStop(CalculationStatus.INPUT_UNAVAILABLE, anchor.reason, None, True)
