"""Invested capital."""

import math
from typing import Any

import pytest

from investment_analysis_engine.analysis.shared.invested_capital import compute_invested_capital
from investment_analysis_engine.analysis.shared.metric_evidence import MetricEvidence
from investment_analysis_engine.core.metric_result import MetricStatus, ReasonCode
from investment_analysis_engine.data.financial.facts import FinancialField as F
from investment_analysis_engine.data.financial.facts import InstantAbsenceReason as R
from tests.analysis.shared._issuer_inputs import absent, balance, synthetic


def _issuer(ticker: str) -> MetricEvidence:
    return compute_invested_capital(
        current_assets=balance(ticker, F.CURRENT_ASSETS),
        current_liabilities=balance(ticker, F.CURRENT_LIABILITIES),
        net_ppe=balance(ticker, F.NET_PPE),
        cash_and_equivalents=balance(ticker, F.CASH_AND_EQUIVALENTS),
        short_term_investments=balance(ticker, F.SHORT_TERM_INVESTMENTS),
        short_term_borrowings=balance(ticker, F.SHORT_TERM_BORROWINGS),
        current_portion_of_long_term_debt=balance(ticker, F.CURRENT_PORTION_OF_LONG_TERM_DEBT),
    )


def _synthetic(**changes: Any) -> MetricEvidence:
    arguments: dict[str, Any] = {
        "current_assets": synthetic("ca", 500.0),
        "current_liabilities": synthetic("cl", 300.0),
        "net_ppe": synthetic("ppe", 400.0),
        "cash_and_equivalents": synthetic("cash", 100.0),
        "short_term_investments": synthetic("sti", 50.0),
        "short_term_borrowings": synthetic("stb", 20.0),
        "current_portion_of_long_term_debt": synthetic("cp", 10.0),
    }
    arguments.update(changes)
    return compute_invested_capital(**arguments)


def _ok(evidence: MetricEvidence) -> float:
    assert evidence.result.status is MetricStatus.OK
    assert evidence.result.value is not None
    assert math.isfinite(evidence.result.value)
    assert evidence.result.reason_code is None
    assert evidence.result.reason is None
    return evidence.result.value


def _unavailable(evidence: MetricEvidence, code: ReasonCode) -> None:
    assert evidence.result.status is MetricStatus.UNAVAILABLE
    assert evidence.result.value is None
    assert evidence.result.reason_code is code
    assert evidence.result.reason is not None
    assert evidence.result.reason.strip()


def test_the_formula_is_working_capital_less_cash_and_investments_plus_net_ppe() -> None:
    # (500 - 100 - 50) - (300 - 20 - 10) + 400 = 350 - 270 + 400
    evidence = _synthetic()
    assert _ok(evidence) == 480.0
    assert [operand.name for operand in evidence.operands] == [
        "current_assets",
        "current_liabilities",
        "net_ppe",
        "cash_and_equivalents",
        "short_term_investments",
        "short_term_borrowings",
        "current_portion_of_long_term_debt",
    ]
    assert evidence.zero_components == ()


def test_walmart_takes_short_term_investments_as_zero_on_its_classified_balance_sheet() -> None:
    evidence = _issuer("WMT")
    # (84,874 - 10,727 - 0) - (107,469 - 6,596 - 3,542) + 136,083 million
    assert _ok(evidence) == 112_899_000_000.0
    assert evidence.zero_components == ("short_term_investments",)


def test_alphabet_subtracts_its_marketable_securities_and_adds_back_its_current_debt() -> None:
    # (206,038 - 30,708 - 96,135) - (102,745 - 0 - 1,996) + 246,597 million
    assert _ok(_issuer("GOOGL")) == 225_043_000_000.0


def test_honeywells_current_portion_is_in_a_related_concept_so_it_is_debt_not_visible() -> None:
    _unavailable(_issuer("HON"), ReasonCode.DEBT_NOT_VISIBLE)


def test_deere_has_no_classified_balance_sheet_so_invested_capital_is_unavailable() -> None:
    _unavailable(_issuer("DE"), ReasonCode.MISSING_FACT)


def test_nutriens_ifrs_short_term_investments_are_unsupported() -> None:
    _unavailable(_issuer("NTR"), ReasonCode.UNSUPPORTED_MAPPING)


def test_invested_capital_at_or_below_zero_is_an_ok_value() -> None:
    # Working capital after removing cash, investments and debt is 80, so net PP&E decides the sign.
    assert _ok(_synthetic(net_ppe=synthetic("ppe", -270.0))) == -190.0
    assert _ok(_synthetic(net_ppe=synthetic("ppe", -80.0))) == 0.0


@pytest.mark.parametrize("name", ["current_assets", "current_liabilities", "net_ppe", "cash_and_equivalents"])
@pytest.mark.parametrize(
    ("reason", "code"),
    [
        (R.NOT_TAGGED, ReasonCode.MISSING_FACT),
        (R.CONFLICT, ReasonCode.AMBIGUOUS_FACT),
        (R.UNSUPPORTED, ReasonCode.UNSUPPORTED_MAPPING),
    ],
)
def test_a_missing_critical_input_is_unavailable(name: str, reason: R, code: ReasonCode) -> None:
    _unavailable(_synthetic(**{name: absent(reason)}), code)


def test_absent_short_term_investments_are_zero_only_when_not_tagged() -> None:
    evidence = _synthetic(short_term_investments=absent())
    assert _ok(evidence) == 530.0
    assert evidence.zero_components == ("short_term_investments",)
    _unavailable(_synthetic(short_term_investments=absent(R.OTHER_CONCEPT)), ReasonCode.MISSING_FACT)
    _unavailable(_synthetic(short_term_investments=absent(R.UNSUPPORTED)), ReasonCode.UNSUPPORTED_MAPPING)


@pytest.mark.parametrize("name", ["short_term_borrowings", "current_portion_of_long_term_debt"])
def test_an_absent_debt_component_follows_the_debt_rule(name: str) -> None:
    zero = _synthetic(**{name: absent()})
    assert name in zero.zero_components
    _unavailable(_synthetic(**{name: absent(R.NOT_TAGGED, related="us-gaap:DebtCurrent")}), ReasonCode.DEBT_NOT_VISIBLE)
    _unavailable(_synthetic(**{name: absent(R.UNSUPPORTED)}), ReasonCode.UNSUPPORTED_MAPPING)
    _unavailable(_synthetic(**{name: absent(R.AFTER_BOUNDARY)}), ReasonCode.NOT_AVAILABLE_AS_OF)


def test_overflow_is_not_a_number() -> None:
    evidence = _synthetic(net_ppe=synthetic("ppe", 1.7e308), current_assets=synthetic("ca", 1.7e308))
    assert evidence.result.status is MetricStatus.NOT_APPLICABLE
    assert evidence.result.value is None
