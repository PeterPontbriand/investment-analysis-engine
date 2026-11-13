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
from investment_analysis_engine.core.metric_result import ReasonCode
from investment_analysis_engine.core.provider_failure_kind import ProviderFailureRecord
from investment_analysis_engine.data.financial.provenance import SourceKind
from investment_analysis_engine.data.financial.resolver import InputResolutionResult, InputResolver
from investment_analysis_engine.data.sec_edgar.financial_facts import AnchorYearEnd
from investment_analysis_engine.strategies._graham.outcome import provider_error_message


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


def year_mismatch_reason(
    method_name: str, which: GrahamFilingInput, *, newest_end: date | None, anchor_year_end: date
) -> str:
    """Return the reason for an input whose newest year does not end at the anchor filing's fiscal year-end."""
    anchor = f"the anchor filing's fiscal year-end {anchor_year_end.isoformat()}"
    never = f"the {method_name} is never calculated from an older year."
    if newest_end is None:
        return f"The newest {which.value.upper()} carries no period end, so it is not {anchor}; {never}"
    return f"{which.newest_year} {newest_end.isoformat()}, not {anchor}; {never}"


def resolve_aligned(  # noqa: PLR0913
    resolver: InputResolver,
    resolve: Callable[[], InputResolutionResult],
    *,
    anchor: AnchorYearEnd | None,
    method_name: str,
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
        reason=year_mismatch_reason(method_name, which, newest_end=newest_end, anchor_year_end=anchor.year_end),
        resolution_trace=result.resolution_trace,
        reason_code=ReasonCode.INCOMPATIBLE_PERIOD,
    )


@dataclass(frozen=True)
class AnchorStop:
    """Why a Graham run stopped before it read any filing input: the anchor filing could not be resolved.

    Attributes:
        status: ``provider_error`` for a provider failure, ``input_unavailable`` when there is no anchor.
        reason: The explanation; the provider-error message for a provider failure, and the anchor's own message when
            there is no anchor.
        provider_failure: The failure recorded against ``anchor_year_end``; ``None`` for an unclassified failure and
            when there is no failure.
        reason_code: ``provider_error`` for a provider failure, and the anchor's own reason code when there is no
            anchor.
    """

    status: CalculationStatus
    reason: str
    provider_failure: ProviderFailureRecord | None
    reason_code: ReasonCode


def anchor_stop(anchor: InputUnavailable | MetricInputsFailure, security_subject_id: str) -> AnchorStop:
    """Return the outcome of an anchor that is not an ``AnchorYearEnd``.

    A provider failure is ``provider_error``, with its code and message, and the failure recorded against
    ``anchor_year_end``. No anchor, for any reason, is ``input_unavailable`` with the anchor's message: the newest facts
    are never used in its place.
    """
    if isinstance(anchor, MetricInputsFailure):
        return AnchorStop(
            CalculationStatus.PROVIDER_ERROR,
            provider_error_message(security_subject_id),
            anchor.provider_failure,
            ReasonCode.PROVIDER_ERROR,
        )
    return AnchorStop(CalculationStatus.INPUT_UNAVAILABLE, anchor.reason, None, anchor.reason_code)
