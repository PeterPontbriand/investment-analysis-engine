"""The shared industry-class resolver: every outcome of the as-filed SIC, and the failure of the provider."""

from datetime import UTC, date, datetime

import pytest

from investment_analysis_engine.analysis.shared.applicability import IndustryClass
from investment_analysis_engine.analysis.shared.metric_inputs import (
    IndustryClassResolution,
    MetricInputsFailure,
    resolve_industry_class,
)
from investment_analysis_engine.core.metric_result import ReasonCode
from investment_analysis_engine.core.provider_failure_kind import ProviderFailureKind, ProviderFailureRecord
from investment_analysis_engine.data.financial.facts import FinancialProviderError
from investment_analysis_engine.data.sec_edgar.filing_header import (
    AsFiledSic,
    AsFiledSicResolution,
    SicUnavailableReason,
)

_BOUNDARY = datetime(2026, 3, 1, tzinfo=UTC)


class _Source:
    """An as-filed SIC source that answers with one resolution or raises one error, and records its calls."""

    def __init__(self, answer: AsFiledSicResolution | BaseException) -> None:
        self.answer = answer
        self.calls: list[tuple[str, datetime | None]] = []

    def resolve_as_filed_sic_at_anchor(self, ticker: str, as_of: datetime | None) -> AsFiledSicResolution:
        self.calls.append((ticker, as_of))
        if isinstance(self.answer, BaseException):
            raise self.answer
        return self.answer


def _code(code: int) -> AsFiledSicResolution:
    return AsFiledSicResolution(
        sic=AsFiledSic(
            code=code,
            cik="0000019617",
            accession="0001628280-26-008131",
            filing_date=date(2026, 2, 13),
            accepted_at=datetime(2026, 2, 13, 21, 20, tzinfo=UTC),
            source_url="https://www.sec.gov/Archives/edgar/data/19617/x.hdr.sgml",
            retrieved_at=_BOUNDARY,
        )
    )


@pytest.mark.parametrize(
    ("code", "industry_class"),
    [
        (6021, IndustryClass.FINANCIAL),
        (6799, IndustryClass.FINANCIAL),
        (4931, IndustryClass.UTILITY),
        (3523, IndustryClass.MANUFACTURER),
        (2870, IndustryClass.MANUFACTURER),
        (7372, IndustryClass.OTHER),
        (100, IndustryClass.OTHER),
    ],
)
def test_the_class_is_the_class_of_the_as_filed_sic_code(code: int, industry_class: IndustryClass) -> None:
    source = _Source(_code(code))
    assert resolve_industry_class(source, ticker="jpm", as_of=_BOUNDARY) == IndustryClassResolution(
        industry_class, None
    )
    assert source.calls == [("JPM", _BOUNDARY)]


@pytest.mark.parametrize("reason", list(SicUnavailableReason))
def test_every_reason_the_sic_is_unavailable_is_an_unknown_class_naming_that_reason(
    reason: SicUnavailableReason,
) -> None:
    outcome = resolve_industry_class(_Source(AsFiledSicResolution(reason=reason)), ticker="JPM", as_of=None)
    assert isinstance(outcome, IndustryClassResolution)
    assert outcome.industry_class is None
    assert outcome.unknown is not None
    assert outcome.unknown.reason_code is ReasonCode.INDUSTRY_CLASS_UNKNOWN
    assert reason.value in outcome.unknown.reason


def test_no_active_scope_is_an_unknown_class_not_an_error() -> None:
    outcome = resolve_industry_class(
        _Source(AsFiledSicResolution(reason=SicUnavailableReason.NO_ANCHOR_FILING)), ticker="JPM", as_of=None
    )
    assert isinstance(outcome, IndustryClassResolution)
    assert outcome.unknown is not None
    assert "no_anchor_filing" in outcome.unknown.reason


@pytest.mark.parametrize("kind", [ProviderFailureKind.UNREACHABLE, ProviderFailureKind.RATE_LIMITED])
def test_a_provider_failure_is_a_metric_inputs_failure_for_the_industry_class_input(
    kind: ProviderFailureKind,
) -> None:
    source = _Source(FinancialProviderError("down", kind=kind, provider_id="sec_edgar"))
    outcome = resolve_industry_class(source, ticker="JPM", as_of=None)
    assert isinstance(outcome, MetricInputsFailure)
    assert outcome.input_name == "industry_class"
    assert outcome.provider_failure == ProviderFailureRecord(kind, "sec_edgar", "industry_class")
    assert outcome.reason_code is ReasonCode.PROVIDER_ERROR


def test_an_unclassified_provider_failure_is_a_metric_inputs_failure_with_no_record() -> None:
    outcome = resolve_industry_class(_Source(FinancialProviderError("odd")), ticker="JPM", as_of=None)
    assert isinstance(outcome, MetricInputsFailure)
    assert outcome.provider_failure is None


def test_a_resolution_holds_exactly_one_of_the_class_and_the_unknown_reason() -> None:
    with pytest.raises(ValueError, match="exactly one"):
        IndustryClassResolution(None, None)
    unknown = resolve_industry_class(
        _Source(AsFiledSicResolution(reason=SicUnavailableReason.HEADER_MISSING)), ticker="JPM", as_of=None
    )
    assert isinstance(unknown, IndustryClassResolution)
    with pytest.raises(ValueError, match="exactly one"):
        IndustryClassResolution(IndustryClass.OTHER, unknown.unknown)
