"""The Piotroski F-Score calculation: nine pass/fail tests over three fiscal year-ends.

This module is the pure calculation of the Piotroski F-Score. It moves into the strategy's package when the strategy
is generated.

The function takes a frozen ``PiotroskiInputs`` and does no I/O and no clock, provider or cache access. Every operand
is a resolved input with its provenance, or the reason it is unavailable. Comparisons are strict and exact: each
float operand is converted to a ``Fraction`` without rounding, so a ratio is compared on its unrounded value with no
tolerance. A reported ratio is the float nearest that exact value; a ratio that does not fit the finite double range
makes its test unavailable, so no ``NaN`` or ``Inf`` is ever produced.

Rules per test:

- an operand that is unavailable makes the test unavailable with the operand's own reason code, and an unavailable test
  is never a fail;
- the monetary operands of one test share one currency (``incompatible_currency``) and every operand of one test
  shares one taxonomy, us-gaap or ifrs-full (``incompatible_scope``);
- total assets, sales and current liabilities must be positive wherever they are a denominator
  (``nonpositive_denominator``);
- test 5 passes when long-term debt is zero in both years, whatever the assets;
- test 7 compares the two share counts only when both come from the same filing and the same path.

A score is available from six available tests: complete at nine, partial from six to eight.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from fractions import Fraction
from typing import Final

from investment_analysis_engine.analysis.shared.metric_evidence import InputUnavailable, MetricEvidence, Operand
from investment_analysis_engine.core.metric_result import MetricResult, MetricStatus, ReasonCode
from investment_analysis_engine.data.financial.provenance import ResolvedInput

TEST_COUNT: Final = 9
"""The number of tests, and the number available for a complete score."""

MINIMUM_AVAILABLE_TESTS: Final = 6
"""The fewest available tests that give a score. Below it the score is unavailable."""

SUPPORTED_TAXONOMIES: Final = frozenset({"us-gaap", "ifrs-full"})
"""The taxonomy prefixes a provider field name may carry; an operand with any other prefix has no known taxonomy."""

_TEST_NAMES: Final = (
    ("Positive ROA", "Profitability"),
    ("Positive CFO", "Profitability"),
    ("Improving ROA", "Profitability"),
    ("Cash exceeds income", "Profitability"),
    ("Falling leverage", "Leverage and liquidity"),
    ("Improving liquidity", "Leverage and liquidity"),
    ("No dilution", "Leverage and liquidity"),
    ("Improving margin", "Efficiency"),
    ("Improving turnover", "Efficiency"),
)
"""Each test's name and group, in the fixed order of the specification."""

Value = ResolvedInput | InputUnavailable
"""An input value with provenance, or the reason it is unavailable."""


class CheckOutcome(StrEnum):
    """Outcome of one test. An unavailable test is never a fail."""

    PASS = "pass"
    FAIL = "fail"
    UNAVAILABLE = "unavailable"


class Completeness(StrEnum):
    """Whether a score rests on all nine tests or on six to eight."""

    COMPLETE = "complete"
    PARTIAL = "partial"


class ShareCountPath(StrEnum):
    """How a year-end share count was obtained."""

    DIRECT = "direct"
    ISSUED_LESS_TREASURY = "issued_less_treasury"


@dataclass(frozen=True)
class ShareCount:
    """A year-end common share count with the filing and the path it came from.

    Attributes:
        input: The resolved count, with its provenance.
        accession: The accession of the one filing the count was taken from.
        path: Whether the count is reported directly or is issued shares less treasury shares.
    """

    input: ResolvedInput
    accession: str
    path: ShareCountPath

    def __post_init__(self) -> None:
        """Require an accession."""
        if not self.accession.strip():
            raise ValueError("A share count requires the accession of the filing it came from.")


@dataclass(frozen=True)
class PiotroskiInputs:
    """Every operand of the nine tests, each a value with provenance or the reason it is unavailable.

    Year *t* is the selected fiscal year, *t1* the year before it and *t2* the year before that. Long-term debt and
    gross profit are shared-metric evidence, so their own components and reasons are kept.
    """

    total_assets_t: Value
    total_assets_t1: Value
    total_assets_t2: Value
    net_income_t: Value
    net_income_t1: Value
    operating_cash_flow_t: Value
    sales_t: Value
    sales_t1: Value
    gross_profit_t: MetricEvidence | InputUnavailable
    gross_profit_t1: MetricEvidence | InputUnavailable
    long_term_debt_t: MetricEvidence | InputUnavailable
    long_term_debt_t1: MetricEvidence | InputUnavailable
    current_assets_t: Value
    current_assets_t1: Value
    current_liabilities_t: Value
    current_liabilities_t1: Value
    shares_t: ShareCount | InputUnavailable
    shares_t1: ShareCount | InputUnavailable


@dataclass(frozen=True)
class NamedMetric:
    """A ratio a test compared, as a ``MetricResult`` under the name the test gives it."""

    name: str
    result: MetricResult


@dataclass(frozen=True)
class PiotroskiTestResult:
    """The outcome of one test with the ratios and operands behind it.

    Attributes:
        number: The test's number, 1 to 9.
        name: The test's name.
        group: The test's group.
        outcome: Pass, fail or unavailable.
        ratios: The ratios compared, each finite; empty for an unavailable test and for tests 4 and 7.
        operands: Every resolved input used, under the test's names for them.
        diagnostics: Notes that explain how the outcome was reached.
        reason_code: Why the test is unavailable; ``None`` otherwise.
        reason: A non-empty explanation when unavailable; ``None`` otherwise.
    """

    number: int
    name: str
    group: str
    outcome: CheckOutcome
    ratios: tuple[NamedMetric, ...] = ()
    operands: tuple[Operand, ...] = ()
    diagnostics: tuple[str, ...] = ()
    reason_code: ReasonCode | None = None
    reason: str | None = None

    def __post_init__(self) -> None:
        """Require a reason exactly for an unavailable test and finite ratios only."""
        unavailable = self.outcome is CheckOutcome.UNAVAILABLE
        if unavailable != (self.reason_code is not None and bool(self.reason and self.reason.strip())):
            raise ValueError("Only an unavailable test carries a reason code and a reason.")
        if unavailable and self.ratios:
            raise ValueError("An unavailable test carries no ratios.")
        if any(item.result.status is not MetricStatus.OK for item in self.ratios):
            raise ValueError("A decided test carries only ratios that are ok.")


@dataclass(frozen=True)
class PiotroskiScoreResult:
    """The nine tests in fixed order and the score they give.

    Attributes:
        tests: Exactly nine results, numbered 1 to 9 in order.
        score: The number of tests passed as an ``ok`` metric when at least six tests are available;
            otherwise ``unavailable`` with ``insufficient_tests``.
        completeness: Complete at nine available tests, partial at six to eight, ``None`` below six.
        available_count: The number of tests that are pass or fail.
        unavailable_tests: The numbers of the unavailable tests, ascending.
    """

    tests: tuple[PiotroskiTestResult, ...]
    score: MetricResult
    completeness: Completeness | None
    available_count: int
    unavailable_tests: tuple[int, ...]

    def __post_init__(self) -> None:
        """Require the nine tests in order and a score, completeness and counts consistent with them."""
        if tuple(item.number for item in self.tests) != tuple(range(1, TEST_COUNT + 1)):
            raise ValueError("A result holds exactly the nine tests, numbered 1 to 9 in order.")
        decided = [item for item in self.tests if item.outcome is not CheckOutcome.UNAVAILABLE]
        if self.available_count != len(decided):
            raise ValueError("The available count must equal the number of decided tests.")
        if self.unavailable_tests != tuple(
            item.number for item in self.tests if item.outcome is CheckOutcome.UNAVAILABLE
        ):
            raise ValueError("The unavailable tests must be exactly the unavailable ones, ascending.")
        passed = sum(1 for item in decided if item.outcome is CheckOutcome.PASS)
        if self.available_count >= MINIMUM_AVAILABLE_TESTS:
            expected = Completeness.COMPLETE if self.available_count == TEST_COUNT else Completeness.PARTIAL
            if self.score.status is not MetricStatus.OK or self.score.value != float(passed):
                raise ValueError("The score must equal the number of tests passed.")
            if self.completeness is not expected:
                raise ValueError("Completeness must follow the number of available tests.")
        elif (
            self.score.status is not MetricStatus.UNAVAILABLE
            or self.score.reason_code is not ReasonCode.INSUFFICIENT_TESTS
            or self.completeness is not None
        ):
            raise ValueError("Fewer than six available tests give an unavailable score and no completeness.")


# ---------------------------------------------------------------------------
# Operands
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _Figure:
    """A usable operand: its exact value, the inputs behind it and whether it is an amount of money."""

    name: str
    value: Fraction
    operands: tuple[Operand, ...]
    monetary: bool
    diagnostics: tuple[str, ...] = ()


@dataclass(frozen=True)
class _Gap:
    """An operand the test cannot use, with the code and the reason the test reports."""

    code: ReasonCode
    reason: str


def _taxonomy_of(item: ResolvedInput) -> str | None:
    """Return the one taxonomy prefix of a resolved input, read from its provider field or its components."""
    if item.provider_field is not None:
        prefix = item.provider_field.partition(":")[0]
        return prefix if prefix in SUPPORTED_TAXONOMIES else None
    if item.lineage is None:
        return None
    found = {_taxonomy_of(component) for component in item.lineage.components}
    return next(iter(found)) if len(found) == 1 else None


def _figure(name: str, value: Value, *, monetary: bool = True) -> _Figure | _Gap:
    """Return the operand ``name`` as a figure, or the gap its unavailability makes."""
    if isinstance(value, InputUnavailable):
        return _Gap(value.reason_code, f"{name} is unavailable: {value.reason}")
    return _Figure(name, Fraction(value.value), (Operand(name, value),), monetary)


def _evidence_figure(name: str, evidence: MetricEvidence | InputUnavailable) -> _Figure | _Gap:
    """Return shared-metric evidence as a figure, keeping its operands and diagnostics, or the gap its outcome makes."""
    if isinstance(evidence, InputUnavailable):
        return _Gap(evidence.reason_code, f"{name} is unavailable: {evidence.reason}")
    result = evidence.result
    if result.status is not MetricStatus.OK or result.value is None:
        return _Gap(result.reason_code or ReasonCode.MISSING_FACT, f"{name} is {result.status.value}: {result.reason}")
    operands = tuple(Operand(f"{name}:{item.name}", item.input) for item in evidence.operands)
    return _Figure(name, Fraction(result.value), operands, True, evidence.diagnostics)


def _first_gap(items: Sequence[_Figure | _Gap]) -> _Gap | None:
    """Return the first operand gap, in the order the test lists its operands."""
    return next((item for item in items if isinstance(item, _Gap)), None)


def _figures(items: Sequence[_Figure | _Gap]) -> list[_Figure]:
    """Return the usable operands; call only after ``_first_gap`` found none."""
    return [item for item in items if isinstance(item, _Figure)]


def _consistency_gap(figures: Sequence[_Figure]) -> _Gap | None:
    """Return the currency or taxonomy conflict among the operands of one test, or ``None`` when they agree."""
    currencies = {inner.input.currency for figure in figures if figure.monetary for inner in figure.operands}
    if None in currencies:
        return _Gap(ReasonCode.INCOMPATIBLE_CURRENCY, "A monetary operand does not state its currency.")
    if len(currencies) > 1:
        return _Gap(
            ReasonCode.INCOMPATIBLE_CURRENCY,
            f"The operands are in different currencies: {sorted(map(str, currencies))}.",
        )
    taxonomies = {_taxonomy_of(inner.input) for figure in figures for inner in figure.operands}
    if None in taxonomies:
        return _Gap(ReasonCode.INCOMPATIBLE_SCOPE, "An operand does not state a supported taxonomy.")
    if len(taxonomies) > 1:
        return _Gap(ReasonCode.INCOMPATIBLE_SCOPE, f"The operands mix taxonomies: {sorted(map(str, taxonomies))}.")
    return None


def _positive_gap(figures: Sequence[_Figure]) -> _Gap | None:
    """Return the first denominator that is not positive, or ``None``."""
    for figure in figures:
        if figure.value <= 0:
            return _Gap(
                ReasonCode.NONPOSITIVE_DENOMINATOR,
                f"{figure.name} is {float(figure.value)} and must be positive as a denominator.",
            )
    return None


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------


def _unavailable(number: int, gap: _Gap) -> PiotroskiTestResult:
    """Return test ``number`` as unavailable for ``gap``."""
    name, group = _TEST_NAMES[number - 1]
    return PiotroskiTestResult(number, name, group, CheckOutcome.UNAVAILABLE, reason_code=gap.code, reason=gap.reason)


def _decided(
    number: int,
    passed: bool,
    figures: Sequence[_Figure],
    ratios: Sequence[tuple[str, Fraction]] = (),
    notes: Sequence[str] = (),
) -> PiotroskiTestResult:
    """Return test ``number`` as pass or fail with its ratios, or as unavailable when a ratio overflows a float."""
    metrics: list[NamedMetric] = []
    for label, exact in ratios:
        try:
            approximate = float(exact)
        except OverflowError:
            return _unavailable(number, _Gap(ReasonCode.INVALID_REQUEST, f"{label} overflows the finite double range."))
        metrics.append(NamedMetric(label, MetricResult.ok(approximate)))
    name, group = _TEST_NAMES[number - 1]
    return PiotroskiTestResult(
        number,
        name,
        group,
        CheckOutcome.PASS if passed else CheckOutcome.FAIL,
        ratios=tuple(metrics),
        operands=tuple(inner for figure in figures for inner in figure.operands),
        diagnostics=(*(note for figure in figures for note in figure.diagnostics), *notes),
    )


def _usable(
    number: int, items: Sequence[_Figure | _Gap], denominators: Sequence[str] = ()
) -> list[_Figure] | PiotroskiTestResult:
    """Return the operands when every rule holds, or the unavailable result of the first rule that fails.

    The rules apply in this order: an unavailable operand, a currency or taxonomy conflict, a denominator that is not
    positive. ``denominators`` names the operands that must be positive.
    """
    gap = _first_gap(items)
    if gap is not None:
        return _unavailable(number, gap)
    figures = _figures(items)
    conflict = _consistency_gap(figures)
    if conflict is not None:
        return _unavailable(number, conflict)
    gap = _positive_gap([figure for figure in figures if figure.name in denominators])
    return figures if gap is None else _unavailable(number, gap)


def _ratio(numerator: _Figure, denominator: _Figure) -> Fraction:
    """Return the exact quotient; the denominator is positive."""
    return numerator.value / denominator.value


# ---------------------------------------------------------------------------
# The nine tests
# ---------------------------------------------------------------------------


def _test_positive_roa(inputs: PiotroskiInputs) -> PiotroskiTestResult:
    """Test 1: net income of year *t* over total assets at *t−1* is greater than zero."""
    items = (_figure("net_income_t", inputs.net_income_t), _figure("total_assets_t1", inputs.total_assets_t1))
    used = _usable(1, items, ("total_assets_t1",))
    if isinstance(used, PiotroskiTestResult):
        return used
    roa = _ratio(used[0], used[1])
    return _decided(1, roa > 0, used, (("roa_t", roa),))


def _test_positive_cfo(inputs: PiotroskiInputs) -> PiotroskiTestResult:
    """Test 2: operating cash flow of year *t* over total assets at *t−1* is greater than zero."""
    items = (
        _figure("operating_cash_flow_t", inputs.operating_cash_flow_t),
        _figure("total_assets_t1", inputs.total_assets_t1),
    )
    used = _usable(2, items, ("total_assets_t1",))
    if isinstance(used, PiotroskiTestResult):
        return used
    ratio = _ratio(used[0], used[1])
    return _decided(2, ratio > 0, used, (("cfo_over_assets_t", ratio),))


def _test_improving_roa(inputs: PiotroskiInputs) -> PiotroskiTestResult:
    """Test 3: ROA of year *t* is greater than ROA of year *t−1*."""
    items = (
        _figure("net_income_t", inputs.net_income_t),
        _figure("total_assets_t1", inputs.total_assets_t1),
        _figure("net_income_t1", inputs.net_income_t1),
        _figure("total_assets_t2", inputs.total_assets_t2),
    )
    used = _usable(3, items, ("total_assets_t1", "total_assets_t2"))
    if isinstance(used, PiotroskiTestResult):
        return used
    current, prior = _ratio(used[0], used[1]), _ratio(used[2], used[3])
    return _decided(3, current > prior, used, (("roa_t", current), ("roa_t1", prior)))


def _test_cash_exceeds_income(inputs: PiotroskiInputs) -> PiotroskiTestResult:
    """Test 4: operating cash flow of year *t* is greater than net income of year *t*."""
    items = (
        _figure("operating_cash_flow_t", inputs.operating_cash_flow_t),
        _figure("net_income_t", inputs.net_income_t),
    )
    used = _usable(4, items)
    if isinstance(used, PiotroskiTestResult):
        return used
    return _decided(4, used[0].value > used[1].value, used)


def _test_falling_leverage(inputs: PiotroskiInputs) -> PiotroskiTestResult:
    """Test 5: long-term debt over average total assets fell, or long-term debt is zero in both years."""
    debt = (
        _evidence_figure("long_term_debt_t", inputs.long_term_debt_t),
        _evidence_figure("long_term_debt_t1", inputs.long_term_debt_t1),
    )
    gap = _first_gap(debt)
    if gap is not None:
        return _unavailable(5, gap)
    debts = _figures(debt)
    if all(figure.value == 0 for figure in debts):
        return _decided(
            5, True, debts, notes=("Long-term debt is zero in both years, so leverage cannot fall further.",)
        )
    items = (
        *debt,
        _figure("total_assets_t", inputs.total_assets_t),
        _figure("total_assets_t1", inputs.total_assets_t1),
        _figure("total_assets_t2", inputs.total_assets_t2),
    )
    used = _usable(5, items, ("total_assets_t", "total_assets_t1", "total_assets_t2"))
    if isinstance(used, PiotroskiTestResult):
        return used
    current = used[0].value / ((used[2].value + used[3].value) / 2)
    prior = used[1].value / ((used[3].value + used[4].value) / 2)
    return _decided(5, current < prior, used, (("leverage_t", current), ("leverage_t1", prior)))


def _test_improving_liquidity(inputs: PiotroskiInputs) -> PiotroskiTestResult:
    """Test 6: the current ratio at *t* is greater than the current ratio at *t−1*."""
    items = (
        _figure("current_assets_t", inputs.current_assets_t),
        _figure("current_liabilities_t", inputs.current_liabilities_t),
        _figure("current_assets_t1", inputs.current_assets_t1),
        _figure("current_liabilities_t1", inputs.current_liabilities_t1),
    )
    used = _usable(6, items, ("current_liabilities_t", "current_liabilities_t1"))
    if isinstance(used, PiotroskiTestResult):
        return used
    current, prior = _ratio(used[0], used[1]), _ratio(used[2], used[3])
    return _decided(6, current > prior, used, (("current_ratio_t", current), ("current_ratio_t1", prior)))


def _test_no_dilution(inputs: PiotroskiInputs) -> PiotroskiTestResult:
    """Test 7: shares at *t* are not more than shares at *t−1*, both counts from one filing and one path."""
    counts = (inputs.shares_t, inputs.shares_t1)
    unavailable = next((item for item in counts if isinstance(item, InputUnavailable)), None)
    if unavailable is not None:
        return _unavailable(7, _Gap(unavailable.reason_code, f"A share count is unavailable: {unavailable.reason}"))
    now, before = (item for item in counts if isinstance(item, ShareCount))
    figures = [
        _Figure("shares_t", Fraction(now.input.value), (Operand("shares_t", now.input),), False),
        _Figure("shares_t1", Fraction(before.input.value), (Operand("shares_t1", before.input),), False),
    ]
    conflict = _consistency_gap(figures)
    if conflict is not None:
        return _unavailable(7, conflict)
    if now.accession != before.accession:
        return _unavailable(
            7,
            _Gap(
                ReasonCode.AMBIGUOUS_FACT,
                f"The counts come from different filings ({now.accession}, {before.accession}), so they may be on "
                "different split bases.",
            ),
        )
    if now.path is not before.path:
        return _unavailable(
            7,
            _Gap(ReasonCode.AMBIGUOUS_FACT, f"The counts come by different paths ({now.path}, {before.path})."),
        )
    return _decided(7, figures[0].value <= figures[1].value, figures)


def _test_improving_margin(inputs: PiotroskiInputs) -> PiotroskiTestResult:
    """Test 8: the gross margin of year *t* is greater than that of year *t−1*."""
    items = (
        _evidence_figure("gross_profit_t", inputs.gross_profit_t),
        _figure("sales_t", inputs.sales_t),
        _evidence_figure("gross_profit_t1", inputs.gross_profit_t1),
        _figure("sales_t1", inputs.sales_t1),
    )
    used = _usable(8, items, ("sales_t", "sales_t1"))
    if isinstance(used, PiotroskiTestResult):
        return used
    current, prior = _ratio(used[0], used[1]), _ratio(used[2], used[3])
    return _decided(8, current > prior, used, (("gross_margin_t", current), ("gross_margin_t1", prior)))


def _test_improving_turnover(inputs: PiotroskiInputs) -> PiotroskiTestResult:
    """Test 9: sales over beginning-of-year total assets of year *t* is greater than that of year *t−1*."""
    items = (
        _figure("sales_t", inputs.sales_t),
        _figure("total_assets_t1", inputs.total_assets_t1),
        _figure("sales_t1", inputs.sales_t1),
        _figure("total_assets_t2", inputs.total_assets_t2),
    )
    used = _usable(9, items, ("total_assets_t1", "total_assets_t2"))
    if isinstance(used, PiotroskiTestResult):
        return used
    current, prior = _ratio(used[0], used[1]), _ratio(used[2], used[3])
    return _decided(9, current > prior, used, (("turnover_t", current), ("turnover_t1", prior)))


def calculate_f_score(inputs: PiotroskiInputs) -> PiotroskiScoreResult:
    """Return the nine test results and the score they give.

    Args:
        inputs: Every operand, each a value with provenance or the reason it is unavailable.

    Returns:
        The nine tests in fixed order. The score is the number of tests passed when at least six tests are available
        (complete at nine, partial from six to eight); otherwise it is ``unavailable`` with ``insufficient_tests``.
        A test whose inputs are missing is unavailable, never a fail, and no older year is ever scored in place of
        year *t*.
    """
    tests = (
        _test_positive_roa(inputs),
        _test_positive_cfo(inputs),
        _test_improving_roa(inputs),
        _test_cash_exceeds_income(inputs),
        _test_falling_leverage(inputs),
        _test_improving_liquidity(inputs),
        _test_no_dilution(inputs),
        _test_improving_margin(inputs),
        _test_improving_turnover(inputs),
    )
    decided = [item for item in tests if item.outcome is not CheckOutcome.UNAVAILABLE]
    unavailable_numbers = tuple(item.number for item in tests if item.outcome is CheckOutcome.UNAVAILABLE)
    if len(decided) < MINIMUM_AVAILABLE_TESTS:
        score = MetricResult.failure(
            MetricStatus.UNAVAILABLE,
            ReasonCode.INSUFFICIENT_TESTS,
            f"{len(decided)} of {TEST_COUNT} tests are available; at least {MINIMUM_AVAILABLE_TESTS} are required.",
        )
        return PiotroskiScoreResult(tests, score, None, len(decided), unavailable_numbers)
    passed = sum(1 for item in decided if item.outcome is CheckOutcome.PASS)
    completeness = Completeness.COMPLETE if len(decided) == TEST_COUNT else Completeness.PARTIAL
    return PiotroskiScoreResult(tests, MetricResult.ok(float(passed)), completeness, len(decided), unavailable_numbers)
