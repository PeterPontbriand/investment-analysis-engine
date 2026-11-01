"""The Piotroski F-Score strategy's result and analyzer.

The analyzer assembles the operands of the nine tests through ``analysis/shared/metric_inputs.py`` and
``analysis/shared/enterprise_value.py`` and passes them to the pure calculation. It takes no configuration: the tests,
their operands and the score's rule are fixed by the method, so it runs on the ticker and the ``AnalysisContext`` alone.

Each of the three fiscal year-ends (*t*, *t-1*, *t-2*) is either known or carries the reason it is unavailable, and an
unavailable year gives every operand of that year its reason, so a result that ran always holds the nine tests. A
provider failure stops the assembly: the result then holds the failure and no tests.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Final

from investment_analysis_engine.analysis.base_analyzer import AnalysisContext, ConfigFreeAnalyzer, require_ticker
from investment_analysis_engine.analysis.shared.applicability import (
    Applicability,
    IndustryClass,
    SectorGate,
    applicability_of,
)
from investment_analysis_engine.analysis.shared.enterprise_value import compute_long_term_debt
from investment_analysis_engine.analysis.shared.financial_resolution import is_known_etf, validate_profile_ticker
from investment_analysis_engine.analysis.shared.metric_evidence import (
    AnnualValue,
    BalanceSheetValue,
    InputUnavailable,
    MetricEvidence,
    absence_reason_code,
)
from investment_analysis_engine.analysis.shared.metric_inputs import (
    AsFiledSicSource,
    IndustryClassResolution,
    MetricInputsFailure,
    YearEndShareCount,
    anchor_year_end_scope,
    resolve_annual_values_at,
    resolve_balance_sheet_values_at,
    resolve_industry_class,
    resolve_share_count_series,
    resolve_year_ends,
)
from investment_analysis_engine.analysis.shared.operating_metrics import compute_gross_profit
from investment_analysis_engine.core.analysis_status import CalculationStatus
from investment_analysis_engine.core.metric_result import ReasonCode
from investment_analysis_engine.core.provider_failure_kind import ProviderFailureRecord
from investment_analysis_engine.data.financial.facts import FinancialField, InstantAbsence
from investment_analysis_engine.data.financial.provenance import ResolvedInput
from investment_analysis_engine.data.financial.resolver import InputResolver
from investment_analysis_engine.data.instrument_profile import InstrumentProfile
from investment_analysis_engine.data.sec_edgar.financial_facts import AnchorYearEnd
from investment_analysis_engine.strategies.piotroski.calculation import (
    PiotroskiInputs,
    PiotroskiScoreResult,
    Value,
    calculate_f_score,
    taxonomy_of_input,
)
from investment_analysis_engine.strategies.piotroski.vocabulary import (
    ANALYSIS_ID,
    METHOD_ID,
    METHOD_VERSION,
    RESULT_SCHEMA_VERSION,
    AnalysisId,
    MethodId,
)

PIOTROSKI_SECTOR_GATE: Final = SectorGate(gated=False, warn=frozenset({IndustryClass.FINANCIAL}))
"""The strategy's row of the applicability matrix: a financial issuer is applicable with a warning, none is refused."""

_FINANCIAL_WARNING: Final = (
    "The F-Score was designed for non-financial firms; the gross-margin and current-ratio tests are typically "
    "unavailable for a financial issuer."
)

_BALANCE_FIELDS: Final = (
    FinancialField.TOTAL_ASSETS,
    FinancialField.CURRENT_ASSETS,
    FinancialField.CURRENT_LIABILITIES,
    FinancialField.SHORT_TERM_BORROWINGS,
    FinancialField.CURRENT_PORTION_OF_LONG_TERM_DEBT,
    FinancialField.NONCURRENT_LONG_TERM_DEBT,
    FinancialField.LEASE_LIABILITIES_AS_DEBT,
    FinancialField.LONG_TERM_DEBT_TOTAL,
)
"""The balance-sheet fields read at the year-ends: three operands and the five concepts of long-term debt."""

_DEBT_FIELDS: Final = _BALANCE_FIELDS[3:]
"""The five concepts that long-term debt is decided from."""

_ANNUAL_FIELDS: Final = (
    FinancialField.NET_INCOME,
    FinancialField.SALES,
    FinancialField.OPERATING_CASH_FLOW,
    FinancialField.GROSS_PROFIT,
    FinancialField.COST_OF_REVENUE,
    FinancialField.INTEREST_EXPENSE,
)
"""The completed-annual fields read for the years *t* and *t-1*."""


@dataclass(frozen=True)
class AnchorFiling:
    """The anchor annual filing: the fiscal year-end *t* every operand is taken at, and the filing it comes from.

    Attributes:
        year_end: The fiscal year-end *t*.
        accession: The filing's accession.
        form: The filing's form, such as ``10-K``.
        filing_date: The filing date, when the submissions data dates it.
    """

    year_end: date
    accession: str
    form: str
    filing_date: date | None


@dataclass(frozen=True)
class SourceFiling:
    """A filing an operand was taken from and the date it was filed.

    Attributes:
        accession: The filing's accession.
        filing_date: The filing date the submissions data gives.
    """

    accession: str
    filing_date: date


@dataclass(frozen=True, kw_only=True)
class PiotroskiResult:
    """The complete evidence of one Piotroski F-Score run.

    A run that assembled its inputs holds the calculation's nine tests in ``f_score``; a run that did not holds none:
    a provider-confirmed ETF (``not_applicable``) or a provider failure while assembling (``provider_error``, with the
    failure in ``input_failure``). A year-end or a value that is unavailable is not a failure: the calculation ran and
    its tests carry the reasons.

    Attributes:
        ticker: The normalized ticker.
        requested_as_of: The requested point-in-time boundary, or ``None``.
        effective_as_of: The boundary the run applied.
        instrument_profile: The identity evidence the run was given.
        execution_status: ``ok`` for a score of six to nine available tests, ``input_unavailable`` below six,
            ``provider_error`` after a provider failure and ``not_applicable`` for an ETF.
        reason_code: Why the run is not ``ok``; ``None`` for ``ok``.
        reason: A non-empty explanation exactly when ``reason_code`` is set.
        industry_class: The class of the as-filed SIC code, ``None`` when it is unknown or was not resolved.
        industry_class_unknown: Why the class is unknown (``industry_class_unknown``); ``None`` otherwise.
        anchor: The anchor filing, ``None`` when it was not found or the run did not get that far.
        source_filings: The filings the operands were taken from, by accession, each with its filing date when the
            submissions data gives one.
        taxonomy: The taxonomy every resolved operand shares, ``us-gaap`` or ``ifrs-full``; ``None`` when they
            disagree, when an operand states none or when there is no operand.
        f_score: The calculation's nine tests and score; ``None`` for an ETF and for a provider failure.
        input_failure: The provider failure that stopped the assembly; ``None`` otherwise.
        warnings: Warnings about the run, in order.
        diagnostics: Notes on how the inputs were assembled, in order.
    """

    ticker: str
    requested_as_of: datetime | None
    effective_as_of: datetime
    instrument_profile: InstrumentProfile | None
    execution_status: CalculationStatus
    reason_code: ReasonCode | None
    reason: str | None
    industry_class: IndustryClass | None
    industry_class_unknown: InputUnavailable | None
    anchor: AnchorFiling | None
    source_filings: tuple[SourceFiling, ...]
    taxonomy: str | None
    f_score: PiotroskiScoreResult | None
    input_failure: MetricInputsFailure | None
    warnings: tuple[str, ...]
    diagnostics: tuple[str, ...]
    schema_version: int = field(init=False, default=RESULT_SCHEMA_VERSION)
    strategy_id: AnalysisId = field(init=False, default=ANALYSIS_ID)
    method_id: MethodId = field(init=False, default=METHOD_ID)
    method_version: int = field(init=False, default=METHOD_VERSION)

    def __post_init__(self) -> None:
        """Require the fields of each status to agree: a reason exactly when not ok, tests exactly when it ran."""
        status = self.execution_status
        if (status is CalculationStatus.OK) != (self.reason_code is None):
            raise ValueError("A reason code is set exactly when the run is not ok.")
        if (self.reason_code is None) != (self.reason is None):
            raise ValueError("A reason is set exactly when there is a reason code.")
        ran = status in (CalculationStatus.OK, CalculationStatus.INPUT_UNAVAILABLE)
        if ran != (self.f_score is not None):
            raise ValueError("The tests are held exactly when the calculation ran.")
        if (status is CalculationStatus.PROVIDER_ERROR) != (self.input_failure is not None):
            raise ValueError("A provider failure is held exactly when the run is a provider error.")
        if ran and (self.industry_class is None) == (self.industry_class_unknown is None):
            raise ValueError("A run that ran holds exactly one of the industry class and why it is unknown.")

    @property
    def provider_failure(self) -> ProviderFailureRecord | None:
        """Return the record of the provider failure that stopped the run, when it was classified."""
        return None if self.input_failure is None else self.input_failure.provider_failure


@dataclass(frozen=True)
class _Years:
    """The three fiscal year-ends, each a date or the reason it is unavailable."""

    t: date | InputUnavailable
    t1: date | InputUnavailable
    t2: date | InputUnavailable

    def dates(self) -> tuple[date, ...]:
        """Return the years that are dates, newest first."""
        return tuple(item for item in (self.t, self.t1, self.t2) if isinstance(item, date))


@dataclass(frozen=True)
class _Read:
    """What the assembly read for the years: the balance sheet, the annual values and the share counts."""

    balance: Mapping[FinancialField, Mapping[date, BalanceSheetValue]] | InputUnavailable
    annual: Mapping[FinancialField, Mapping[date, AnnualValue | InputUnavailable]] | InputUnavailable
    shares: Mapping[date, YearEndShareCount | InputUnavailable] | InputUnavailable


def _balance(read: _Read, name: FinancialField, year: date | InputUnavailable) -> BalanceSheetValue | InputUnavailable:
    """Return the balance-sheet field at the year, or the reason the field or the year is unavailable."""
    if isinstance(year, InputUnavailable):
        return year
    if isinstance(read.balance, InputUnavailable):
        return read.balance
    return read.balance[name][year]


def _annual(read: _Read, name: FinancialField, year: date | InputUnavailable) -> AnnualValue | InputUnavailable:
    """Return the annual field of the year, or the reason the field or the year is unavailable."""
    if isinstance(year, InputUnavailable):
        return year
    if isinstance(read.annual, InputUnavailable):
        return read.annual
    return read.annual[name][year]


def _shares(read: _Read, year: date | InputUnavailable) -> YearEndShareCount | InputUnavailable:
    """Return the share count at the year, or the reason the series or the year is unavailable."""
    if isinstance(year, InputUnavailable):
        return year
    if isinstance(read.shares, InputUnavailable):
        return read.shares
    return read.shares[year]


def _balance_operand(item: BalanceSheetValue | InputUnavailable) -> Value:
    """Return a balance-sheet operand as a resolved input, or the unavailable input that states why.

    The message names no operand: the calculation prefixes the operand's plain name and year-end.
    """
    if isinstance(item, InstantAbsence):
        return InputUnavailable(
            absence_reason_code(item.reason), f"The balance sheet reports none at {item.period_end}: {item.detail}"
        )
    return item


def _annual_operand(item: AnnualValue | InputUnavailable) -> Value:
    """Return an annual operand as a resolved input, or the unavailable input that states why."""
    if item is None:
        return InputUnavailable(ReasonCode.MISSING_FACT, "The filings report none for that fiscal year.")
    return item


def _gross_profit(read: _Read, year: date | InputUnavailable) -> MetricEvidence | InputUnavailable:
    """Return the year's gross profit by the shared rule, or the first unavailable input it needs."""
    gross_profit = _annual(read, FinancialField.GROSS_PROFIT, year)
    sales = _annual(read, FinancialField.SALES, year)
    cost_of_revenue = _annual(read, FinancialField.COST_OF_REVENUE, year)
    if isinstance(gross_profit, InputUnavailable):
        return gross_profit
    if isinstance(sales, InputUnavailable):
        return sales
    if isinstance(cost_of_revenue, InputUnavailable):
        return cost_of_revenue
    return compute_gross_profit(gross_profit, sales, cost_of_revenue)


def _long_term_debt(read: _Read, year: date | InputUnavailable) -> MetricEvidence | InputUnavailable:
    """Return the year's long-term debt by the shared rule, or the reason a year or a value is unavailable.

    The interest expense decides only the no-reported-debt row, which applies when none of the debt concepts is
    present, so an unavailable interest expense matters only then.
    """
    debt = {name: _balance(read, name, year) for name in _DEBT_FIELDS}
    parts: dict[FinancialField, BalanceSheetValue] = {}
    for name, item in debt.items():
        if isinstance(item, InputUnavailable):
            return item
        parts[name] = item
    interest = _annual(read, FinancialField.INTEREST_EXPENSE, year)
    if isinstance(interest, InputUnavailable):
        if not any(isinstance(item, ResolvedInput) for item in parts.values()):
            return interest
        interest = None
    return compute_long_term_debt(
        short_term_borrowings=parts[FinancialField.SHORT_TERM_BORROWINGS],
        current_portion_of_long_term_debt=parts[FinancialField.CURRENT_PORTION_OF_LONG_TERM_DEBT],
        noncurrent_long_term_debt=parts[FinancialField.NONCURRENT_LONG_TERM_DEBT],
        lease_liabilities_as_debt=parts[FinancialField.LEASE_LIABILITIES_AS_DEBT],
        long_term_debt_total=parts[FinancialField.LONG_TERM_DEBT_TOTAL],
        interest_expense=interest,
    )


def _date_of(year: date | InputUnavailable) -> date | None:
    """Return the year-end, or ``None`` when the year is unavailable."""
    return year if isinstance(year, date) else None


def _inputs_of(years: _Years, read: _Read) -> PiotroskiInputs:
    """Return the operands of the nine tests, each from its year; an unavailable year gives every operand its reason."""

    def balance(name: FinancialField, year: date | InputUnavailable) -> Value:
        return _balance_operand(_balance(read, name, year))

    def annual(name: FinancialField, year: date | InputUnavailable) -> Value:
        return _annual_operand(_annual(read, name, year))

    return PiotroskiInputs(
        total_assets_t=balance(FinancialField.TOTAL_ASSETS, years.t),
        total_assets_t1=balance(FinancialField.TOTAL_ASSETS, years.t1),
        total_assets_t2=balance(FinancialField.TOTAL_ASSETS, years.t2),
        net_income_t=annual(FinancialField.NET_INCOME, years.t),
        net_income_t1=annual(FinancialField.NET_INCOME, years.t1),
        operating_cash_flow_t=annual(FinancialField.OPERATING_CASH_FLOW, years.t),
        sales_t=annual(FinancialField.SALES, years.t),
        sales_t1=annual(FinancialField.SALES, years.t1),
        gross_profit_t=_gross_profit(read, years.t),
        gross_profit_t1=_gross_profit(read, years.t1),
        long_term_debt_t=_long_term_debt(read, years.t),
        long_term_debt_t1=_long_term_debt(read, years.t1),
        current_assets_t=balance(FinancialField.CURRENT_ASSETS, years.t),
        current_assets_t1=balance(FinancialField.CURRENT_ASSETS, years.t1),
        current_liabilities_t=balance(FinancialField.CURRENT_LIABILITIES, years.t),
        current_liabilities_t1=balance(FinancialField.CURRENT_LIABILITIES, years.t1),
        shares_t=_shares(read, years.t),
        shares_t1=_shares(read, years.t1),
        year_end_t=_date_of(years.t),
        year_end_t1=_date_of(years.t1),
        year_end_t2=_date_of(years.t2),
    )


def _shared_taxonomy(score: PiotroskiScoreResult) -> str | None:
    """Return the taxonomy every resolved operand states; ``None`` if they differ, one states none or there is none."""
    found = {taxonomy_of_input(operand.input) for test in score.tests for operand in test.operands}
    return next(iter(found)) if len(found) == 1 else None


def _source_filings(score: PiotroskiScoreResult, filing_dates: Mapping[str, date]) -> tuple[SourceFiling, ...]:
    """Return the filings the operands came from, by accession, with the filing date of each that is dated."""
    accessions = {
        operand.input.provider_fact_id.split(":", 1)[0]
        for test in score.tests
        for operand in test.operands
        if operand.input.provider_fact_id
    }
    return tuple(SourceFiling(item, filing_dates[item]) for item in sorted(accessions) if item in filing_dates)


def _year_diagnostics(years: _Years) -> tuple[str, ...]:
    """Return one note per year: its year-end, or why it is unavailable."""
    notes = []
    for label, year in (("t", years.t), ("t-1", years.t1), ("t-2", years.t2)):
        state = year.isoformat() if isinstance(year, date) else f"unavailable ({year.reason_code.value}: {year.reason})"
        notes.append(f"Fiscal year-end {label}: {state}.")
    return tuple(notes)


class PiotroskiAnalyzer(ConfigFreeAnalyzer[PiotroskiResult]):
    """Assemble the operands of the nine tests and calculate the Piotroski F-Score.

    Args:
        resolver: Resolves the balance-sheet series, the annual series and the share counts through the SEC adapter.
        industry_classes: Gives the as-filed SIC code of the anchor filing, which classifies the issuer.
    """

    def __init__(self, resolver: InputResolver, industry_classes: AsFiledSicSource) -> None:
        """Retain the resolver and the as-filed SIC source."""
        self._resolver = resolver
        self._industry_classes = industry_classes

    def run_analysis(self, ticker: str, context: AnalysisContext) -> PiotroskiResult:
        """Return the evidence of one Piotroski F-Score run for ``ticker``."""
        boundary = context.effective_as_of
        if boundary.utcoffset() is None:
            raise ValueError("Piotroski effective execution time must be timezone-aware.")
        normalized = require_ticker(ticker)
        validate_profile_ticker(
            ticker,
            context.instrument_profile,
            mismatch_message="Instrument profile ticker does not match the Piotroski analysis ticker.",
        )
        if is_known_etf(context.instrument_profile):
            return self._etf_result(normalized, context)
        with anchor_year_end_scope(self._resolver, ticker=normalized, as_of=context.as_of) as anchor:
            return self._at_anchor(anchor, normalized, context)

    def _etf_result(self, ticker: str, context: AnalysisContext) -> PiotroskiResult:
        """Return the outcome for a provider-confirmed ETF: the company-level tests do not apply."""
        return PiotroskiResult(
            ticker=ticker,
            requested_as_of=context.as_of,
            effective_as_of=context.effective_as_of,
            instrument_profile=context.instrument_profile,
            execution_status=CalculationStatus.NOT_APPLICABLE,
            reason_code=ReasonCode.INSTRUMENT_KIND_NOT_APPLICABLE,
            reason=(
                "The Piotroski F-Score is a company-level analysis of reported financial statements and does not "
                "apply to an ETF. No holdings-level analysis was performed."
            ),
            industry_class=None,
            industry_class_unknown=None,
            anchor=None,
            source_filings=(),
            taxonomy=None,
            f_score=None,
            input_failure=None,
            warnings=(),
            diagnostics=(),
        )

    def _failure_result(self, failure: MetricInputsFailure, ticker: str, context: AnalysisContext) -> PiotroskiResult:
        """Return the outcome of a provider failure: the failure and no tests."""
        return PiotroskiResult(
            ticker=ticker,
            requested_as_of=context.as_of,
            effective_as_of=context.effective_as_of,
            instrument_profile=context.instrument_profile,
            execution_status=CalculationStatus.PROVIDER_ERROR,
            reason_code=failure.reason_code,
            reason=failure.reason,
            industry_class=None,
            industry_class_unknown=None,
            anchor=None,
            source_filings=(),
            taxonomy=None,
            f_score=None,
            input_failure=failure,
            warnings=(),
            diagnostics=(f"The assembly stopped at the input {failure.input_name.replace('_', ' ')}.",),
        )

    def _at_anchor(
        self, anchor: AnchorYearEnd | InputUnavailable | MetricInputsFailure, ticker: str, context: AnalysisContext
    ) -> PiotroskiResult:
        """Assemble the inputs at the open scope's anchor, or run the calculation on the anchor's reason."""
        if isinstance(anchor, MetricInputsFailure):
            return self._failure_result(anchor, ticker, context)
        filing: AnchorFiling | None = None
        filing_dates: Mapping[str, date] = {}
        if isinstance(anchor, InputUnavailable):
            years = _Years(anchor, anchor, anchor)
        else:
            year_ends = resolve_year_ends(self._resolver, anchor=anchor, ticker=ticker, as_of=context.as_of)
            if isinstance(year_ends, MetricInputsFailure):
                return self._failure_result(year_ends, ticker, context)
            if isinstance(year_ends, InputUnavailable):
                years = _Years(anchor.year_end, year_ends, year_ends)
            else:
                years = _Years(year_ends.year_end, year_ends.prior, year_ends.second_prior)
            filing = AnchorFiling(anchor.year_end, anchor.accession, anchor.form, anchor.filing_date)
            filing_dates = anchor.filing_dates
        classified = resolve_industry_class(self._industry_classes, ticker=ticker, as_of=context.as_of)
        if isinstance(classified, MetricInputsFailure):
            return self._failure_result(classified, ticker, context)
        read = self._read(ticker, years, context)
        if isinstance(read, MetricInputsFailure):
            return self._failure_result(read, ticker, context)
        score = calculate_f_score(_inputs_of(years, read))
        reason = anchor if isinstance(anchor, InputUnavailable) else None
        return self._result(ticker, context, years, filing, filing_dates, classified, score, reason)

    def _read(self, ticker: str, years: _Years, context: AnalysisContext) -> _Read | MetricInputsFailure:
        """Read the balance sheet at every year-end that is a date, and the annual values and counts at *t*, *t-1*."""
        dates = years.dates()
        if not dates:
            nothing = InputUnavailable(ReasonCode.MISSING_FACT, "No fiscal year-end is available.")
            return _Read(nothing, nothing, nothing)
        balance = resolve_balance_sheet_values_at(
            self._resolver, ticker=ticker, fields=_BALANCE_FIELDS, year_ends=dates, as_of=context.as_of
        )
        if isinstance(balance, MetricInputsFailure):
            return balance
        annual = resolve_annual_values_at(
            self._resolver, ticker=ticker, fields=_ANNUAL_FIELDS, year_ends=dates[:2], as_of=context.as_of
        )
        if isinstance(annual, MetricInputsFailure):
            return annual
        shares = resolve_share_count_series(self._resolver, ticker=ticker, year_ends=dates[:2], as_of=context.as_of)
        if isinstance(shares, MetricInputsFailure):
            return shares
        return _Read(balance, annual, shares)

    def _result(  # noqa: PLR0913, PLR0917
        self,
        ticker: str,
        context: AnalysisContext,
        years: _Years,
        filing: AnchorFiling | None,
        filing_dates: Mapping[str, date],
        classified: IndustryClassResolution,
        score: PiotroskiScoreResult,
        anchor_reason: InputUnavailable | None,
    ) -> PiotroskiResult:
        """Return the result of a calculation that ran, with its class, warnings and notes.

        When the anchor itself was unavailable the run's reason is the anchor's, which says more than the score's.
        """
        applicability = applicability_of(PIOTROSKI_SECTOR_GATE, classified.industry_class)
        warnings: list[str] = []
        if applicability.outcome is Applicability.APPLIES_WITH_WARNING:
            warnings.append(_FINANCIAL_WARNING)
        if classified.unknown is not None:
            warnings.append(classified.unknown.reason)
        reason_code = score.score.reason_code
        reason = score.score.reason
        if reason_code is not None and anchor_reason is not None:
            reason_code, reason = anchor_reason.reason_code, anchor_reason.reason
        status = CalculationStatus.OK if reason_code is None else CalculationStatus.INPUT_UNAVAILABLE
        return PiotroskiResult(
            ticker=ticker,
            requested_as_of=context.as_of,
            effective_as_of=context.effective_as_of,
            instrument_profile=context.instrument_profile,
            execution_status=status,
            reason_code=reason_code,
            reason=reason,
            industry_class=classified.industry_class,
            industry_class_unknown=classified.unknown,
            anchor=filing,
            source_filings=_source_filings(score, filing_dates),
            taxonomy=_shared_taxonomy(score),
            f_score=score,
            input_failure=None,
            warnings=tuple(warnings),
            diagnostics=_year_diagnostics(years),
        )
