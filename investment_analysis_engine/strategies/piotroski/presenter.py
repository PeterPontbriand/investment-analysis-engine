"""The Piotroski F-Score strategy's presenter.

It renders every presentation mode from the evidence alone. The concise mode is the score, the filing it rests on, the
industry class, the nine tests in their three groups and the source; details add each test's operands with their
year-end and value; diagnostics add where each operand came from and how the inputs were assembled; the JSON mode is
the result as the document model writes it.
"""

from collections.abc import Callable, Iterator
from datetime import date

from investment_analysis_engine.core.analysis_status import CalculationStatus
from investment_analysis_engine.core.failure_classification import provider_failure_of
from investment_analysis_engine.core.provider_check_element import ProviderCheckItem
from investment_analysis_engine.data.financial.provenance import ResolvedInput
from investment_analysis_engine.data.instrument_profile import InstrumentProfile, profile_identity_resolution
from investment_analysis_engine.data.security_identity import SecurityIdentityResolution, security_display_label
from investment_analysis_engine.reporting.documents.shared_parts import (
    DiagnosticPart,
    identity_diagnostic_parts,
    instrument_kind_part_of,
    metric_result_part,
    profile_diagnostic_parts,
    resolved_input_part,
    security_identity_part,
)
from investment_analysis_engine.reporting.documents.strategy_document import strategy_document_json
from investment_analysis_engine.reporting.input_provenance import investor_value
from investment_analysis_engine.reporting.presentation import PresentationMode, format_date, provider_display_name
from investment_analysis_engine.strategies.piotroski.analyzer import PiotroskiResult
from investment_analysis_engine.strategies.piotroski.calculation import PiotroskiTestResult
from investment_analysis_engine.strategies.piotroski.envelope import (
    DOCUMENT_SCHEMA_VERSION,
    PiotroskiAnchorPart,
    PiotroskiDocument,
    PiotroskiInputFailurePart,
    PiotroskiOperandPart,
    PiotroskiRatioPart,
    PiotroskiSourceFilingPart,
    PiotroskiTestPart,
    PiotroskiUnavailablePart,
)
from investment_analysis_engine.strategies.piotroski.vocabulary import (
    ANALYSIS_ID,
    METHOD_ID,
    CheckOutcome,
    Completeness,
)

_LIMITATION = (
    "Follows the Piotroski nine-test structure, with the net change in shares outstanding in place of the paper's "
    "equity-issuance test; not an investment recommendation."
)
_PARTIAL_NOTE = "The usual reading of high and low scores applies to complete scores only."

_BASE_DIGITS = 2
"""The decimals every ratio is shown with."""
_MAX_DIGITS = 12
"""The most decimals added to tell two compared values apart."""
_NAME_GAP = 3
"""The spaces after the longest test name."""
_OUTCOME_GAP = 2
"""The spaces after the longest outcome word."""
_OUTCOME_WIDTH = max(len(outcome.value) for outcome in CheckOutcome) + _OUTCOME_GAP

_Format = Callable[[float, int], str]


def _percent(value: float, digits: int) -> str:
    return f"{value * 100:.{digits}f}%"


def _multiple(value: float, digits: int) -> str:
    return f"{value:.{digits}f}x"


def _pair(left: float, right: float, shown: _Format) -> tuple[str, str]:
    """Return both values with two decimals, or with more until they differ if they differ exactly."""
    digits = _BASE_DIGITS
    while digits < _MAX_DIGITS and left != right and shown(left, digits) == shown(right, digits):
        digits += 1
    return shown(left, digits), shown(right, digits)


def _against_zero(value: float) -> str:
    """Return a ratio compared with zero as a percentage, with more decimals while it would round to zero."""
    return _pair(value, 0.0, _percent)[0]


def _ratios(test: PiotroskiTestResult) -> dict[str, float]:
    """Return the test's ratios by name; a decided test carries only ratios that are ok."""
    return {item.name: item.result.value for item in test.ratios if item.result.value is not None}


def _operands(test: PiotroskiTestResult) -> dict[str, ResolvedInput]:
    """Return the test's operands by name."""
    return {item.name: item.input for item in test.operands}


def _amount(item: ResolvedInput) -> str:
    """Return a full amount with thousands separators and its currency."""
    return f"{item.value:,.0f} {item.currency}" if item.currency else f"{item.value:,.0f}"


def _compare(passed: bool) -> str:
    return ">" if passed else "≤"


_PAIRED_TESTS: dict[int, tuple[str, str, _Format]] = {
    3: ("ROA", "roa", _percent),
    5: ("long-term debt / assets", "leverage", _percent),
    6: ("current ratio", "current_ratio", _multiple),
    8: ("gross margin", "gross_margin", _percent),
    9: ("asset turnover", "turnover", _multiple),
}
"""The tests that compare a ratio with the prior year's: the label, the ratios' name stem and the format."""


def _test_figures(test: PiotroskiTestResult) -> str:
    """Return the figures a decided test compared, in the test's own terms."""
    ratios, operands = _ratios(test), _operands(test)
    passed = test.outcome is CheckOutcome.PASS
    if test.number == 1:
        return f"ROA {_against_zero(ratios['roa_t'])} {_compare(passed)} 0"
    if test.number == 2:
        return f"CFO / assets {_against_zero(ratios['cfo_over_assets_t'])} {_compare(passed)} 0"
    if test.number == 4:
        cash, income = operands["operating_cash_flow_t"], operands["net_income_t"]
        return f"CFO {_amount(cash)} {_compare(passed)} net income {_amount(income)}"
    if test.number == 7:
        now, before = operands["shares_t"], operands["shares_t1"]
        return f"shares {now.value:,.0f}, prior {before.value:,.0f}"
    if test.number == 5 and not ratios:
        return "long-term debt is zero in both years"
    label, stem, shown = _PAIRED_TESTS[test.number]
    current, prior = _pair(ratios[f"{stem}_t"], ratios[f"{stem}_t1"], shown)
    return f"{label} {current}, prior {prior}"


def score_text(result: PiotroskiResult) -> str | None:
    """Return the score as ``x of n`` with ``n`` the available tests, or ``None`` when there is no score."""
    score = result.f_score
    if score is None or score.score.value is None:
        return None
    return f"{score.score.value:.0f} of {score.available_count}"


def completeness_text(result: PiotroskiResult) -> str | None:
    """Return ``complete`` or ``partial (<numbers> unavailable)``, or ``None`` when there is no score."""
    score = result.f_score
    if score is None or score.completeness is None:
        return None
    if score.completeness is Completeness.COMPLETE:
        return "complete"
    return f"partial ({', '.join(str(number) for number in score.unavailable_tests)} unavailable)"


def _title(result: PiotroskiResult, label: str) -> str:
    """Return the first line: the label, the score and its completeness, or why there is none."""
    score = result.f_score
    text = score_text(result)
    if score is None or text is None or score.completeness is None:
        word = "not applicable" if result.execution_status is CalculationStatus.NOT_APPLICABLE else "unavailable"
        return f"{label} — Piotroski F-Score: {word}"
    if score.completeness is Completeness.COMPLETE:
        return f"{label} — Piotroski F-Score: {text} (complete)"
    numbers = ", ".join(str(number) for number in score.unavailable_tests)
    return f"{label} — Piotroski F-Score: {text} (partial: tests {numbers} unavailable)"


def _filing_line(result: PiotroskiResult) -> str:
    """Return the fiscal year-end, the filing it comes from and the taxonomy."""
    anchor = result.anchor
    if anchor is None:
        return "Fiscal year-end: unavailable"
    parts = [f"Fiscal year-end: {anchor.year_end.isoformat()}", f"{anchor.form} {anchor.accession}"]
    if result.taxonomy is not None:
        parts.append(result.taxonomy)
    return " · ".join(parts)


def _class_line(result: PiotroskiResult) -> str:
    if result.industry_class is None:
        return "Industry class: unknown"
    return f"Industry class: {result.industry_class.value} (SIC code as filed)"


def _source_line(result: PiotroskiResult) -> str:
    """Return the providers and the latest availability date of the operands."""
    inputs = [item.input for test in (result.f_score.tests if result.f_score else ()) for item in test.operands]
    providers = sorted({provider_display_name(item.provider_id) for item in inputs if item.provider_id is not None})
    latest = max((item.available_at for item in inputs if item.available_at is not None), default=None)
    names = ", ".join(providers) if providers else "unavailable"
    return f"Source: {names}; latest evidence available {format_date(latest)}"


def _test_lines(result: PiotroskiResult) -> Iterator[str]:
    """Yield the tests under their group headings."""
    assert result.f_score is not None
    tests = result.f_score.tests
    name_width = max(len(test.name) for test in tests) + _NAME_GAP
    group = None
    for test in tests:
        if test.group != group:
            group = test.group
            yield group
        detail = test.reason if test.outcome is CheckOutcome.UNAVAILABLE else _test_figures(test)
        yield f"  {test.number} {test.name:<{name_width}}{test.outcome.value:<{_OUTCOME_WIDTH}}{detail}"


def _concise(result: PiotroskiResult, label: str) -> list[str]:
    lines = [_title(result, label)]
    score = result.f_score
    if score is None:
        return [*lines, f"Reason: {result.reason}", f"Limitation: {_LIMITATION}"]
    lines += [_filing_line(result), _class_line(result)]
    lines += [f"Warning: {warning}" for warning in result.warnings]
    lines += list(_test_lines(result))
    if score.completeness is Completeness.PARTIAL:
        lines.append(f"Note: {_PARTIAL_NOTE}")
    if score.completeness is None:
        lines.append(f"Reason: {result.reason}")
    return [*lines, _source_line(result), f"Limitation: {_LIMITATION}"]


def _operand_value(item: ResolvedInput) -> str:
    """Return an operand's value and its year-end."""
    return f"{investor_value(item)} at {format_date(item.observation_period_end)}"


def _details(result: PiotroskiResult, label: str) -> list[str]:
    lines = [*_concise(result, label), "", "Details — operands of each test", "-------------------------------"]
    for test in result.f_score.tests if result.f_score else ():
        lines.append(f"{test.number} {test.name} — {test.outcome.value}")
        lines += [f"  {item.name}: {_operand_value(item.input)}" for item in test.operands]
        lines += [f"  Note: {note}" for note in test.diagnostics]
    return lines


def _provenance(item: ResolvedInput, filing_dates: dict[str, date]) -> str:
    """Return where an operand came from: the provider field, the accession and the filing date."""
    accession = item.provider_fact_id.split(":", 1)[0] if item.provider_fact_id else None
    filed = filing_dates.get(accession) if accession is not None else None
    return (
        f"provider field {item.provider_field or 'not supplied by provider'}; "
        f"accession {accession or 'unavailable'}; "
        f"filing date {filed.isoformat() if filed is not None else 'unavailable'}"
    )


def _diagnostics(
    result: PiotroskiResult,
    label: str,
    identity_resolution: SecurityIdentityResolution | None,
    profile: InstrumentProfile | None,
) -> list[str]:
    lines = [*_details(result, label), "", "Provenance"]
    dates = {item.accession: item.filing_date for item in result.source_filings}
    for test in result.f_score.tests if result.f_score else ():
        lines += [f"- {test.number} {item.name}: {_provenance(item.input, dates)}" for item in test.operands]
    lines += ["", "Diagnostics", f"Execution status: {result.execution_status.value}"]
    lines += [f"- {note}" for note in result.diagnostics] or ["No assembly notes were retained."]
    if profile is not None:
        lines += [
            f"- {item.capability.value}: {item.provider_id}/{item.status.value} — {item.message}"
            for item in profile.diagnostics
        ]
    elif identity_resolution is not None:
        lines.append(
            f"- security_identity: provider/{identity_resolution.status.value} — {identity_resolution.message}"
        )
    return lines


def _operand_part(name: str, item: ResolvedInput) -> PiotroskiOperandPart:
    part = resolved_input_part(item)
    assert part is not None  # an operand is a resolved input
    return PiotroskiOperandPart(name=name, input=part)


def _test_part(test: PiotroskiTestResult) -> PiotroskiTestPart:
    return PiotroskiTestPart(
        number=test.number,
        name=test.name,
        group=test.group,
        outcome=test.outcome,
        ratios=tuple(
            PiotroskiRatioPart(name=item.name, result=metric_result_part(item.result)) for item in test.ratios
        ),
        operands=tuple(_operand_part(item.name, item.input) for item in test.operands),
        diagnostics=test.diagnostics,
        reason_code=test.reason_code,
        reason=test.reason,
    )


def _document(
    result: PiotroskiResult,
    identity_resolution: SecurityIdentityResolution | None,
    profile: InstrumentProfile | None,
    provider_check: tuple[ProviderCheckItem, ...] | None,
) -> PiotroskiDocument:
    """Build the typed document; validation of the model is the output boundary."""
    score = result.f_score
    anchor = result.anchor
    unknown = result.industry_class_unknown
    failure = result.input_failure
    return PiotroskiDocument(
        schema_version=DOCUMENT_SCHEMA_VERSION,
        analysis=ANALYSIS_ID,
        method=METHOD_ID,
        ticker=result.ticker,
        status=result.execution_status,
        provider_failure=provider_failure_of((result.provider_failure,)),
        provider_check=provider_check,
        requested_as_of=result.requested_as_of,
        effective_as_of=result.effective_as_of,
        security_identity=security_identity_part(result.ticker, identity_resolution),
        instrument_kind=instrument_kind_part_of(profile),
        result_schema_version=result.schema_version,
        method_version=result.method_version,
        reason_code=result.reason_code,
        reason=result.reason,
        industry_class=result.industry_class,
        industry_class_unknown=(
            None
            if unknown is None
            else PiotroskiUnavailablePart(reason_code=unknown.reason_code, reason=unknown.reason)
        ),
        anchor=(
            None
            if anchor is None
            else PiotroskiAnchorPart(
                year_end=anchor.year_end, accession=anchor.accession, form=anchor.form, filing_date=anchor.filing_date
            )
        ),
        source_filings=tuple(
            PiotroskiSourceFilingPart(accession=item.accession, filing_date=item.filing_date)
            for item in result.source_filings
        ),
        taxonomy=result.taxonomy,
        score=None if score is None else metric_result_part(score.score),
        completeness=None if score is None else score.completeness,
        available_count=None if score is None else score.available_count,
        unavailable_tests=() if score is None else score.unavailable_tests,
        tests=() if score is None else tuple(_test_part(test) for test in score.tests),
        input_failure=(
            None if failure is None else PiotroskiInputFailurePart(input_name=failure.input_name, reason=failure.reason)
        ),
        warnings=result.warnings,
        limitations=(_LIMITATION,),
        diagnostics=(
            *(
                DiagnosticPart(field_name="assembly", stage="inputs", outcome="note", message=note)
                for note in result.diagnostics
            ),
            *profile_diagnostic_parts(profile),
            *identity_diagnostic_parts(profile, identity_resolution),
        ),
    )


def render_piotroski(
    result: PiotroskiResult,
    mode: PresentationMode = PresentationMode.CONCISE,
    identity_resolution: SecurityIdentityResolution | None = None,
    instrument_profile: InstrumentProfile | None = None,
    provider_check: tuple[ProviderCheckItem, ...] | None = None,
) -> str:
    """Render one Piotroski F-Score result in ``mode`` without recalculation.

    ``provider_check`` is what the provider check found; only the JSON document carries it, and a replay passes none.
    """
    profile = instrument_profile or result.instrument_profile
    resolved = (
        identity_resolution
        if identity_resolution is not None or profile is None
        else profile_identity_resolution(profile)
    )
    if mode is PresentationMode.JSON:
        return strategy_document_json(_document(result, resolved, profile, provider_check))
    label = security_display_label(result.ticker, resolved)
    if mode is PresentationMode.DETAILS:
        return "\n".join(_details(result, label))
    if mode is PresentationMode.DIAGNOSTICS:
        return "\n".join(_diagnostics(result, label, resolved, profile))
    return "\n".join(_concise(result, label))
