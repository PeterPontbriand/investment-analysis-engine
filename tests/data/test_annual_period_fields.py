"""The completed-annual income-statement and cash-flow fields, and the depreciation evidence behind Beneish's DEPI."""

import copy
import hashlib
from datetime import UTC, date, datetime
from typing import Any

import pytest

from investment_analysis_engine.data.financial.facts import (
    ANNUAL_PERIOD_FIELDS,
    INSTANT_SERIES_FIELDS,
    FinancialFactRequest,
    FinancialField,
    FinancialUnit,
    _expected_unit,
)
from investment_analysis_engine.data.financial.provenance import FinancialSubjectKind, PeriodKind
from investment_analysis_engine.data.sec_edgar.annual_series import (
    IFRS_ANNUAL_CONCEPTS,
    US_GAAP_ANNUAL_CONCEPTS,
    annual_concepts,
)
from investment_analysis_engine.data.sec_edgar.financial_facts import SEC_PROVIDER_ID
from tests._sec_instants import (
    ANNUAL_FIXTURES,
    NOW,
    REGRESSION_SET,
    FixtureFetcher,
    adapter_for,
    annual_request,
    annual_series,
    load,
    series,
)
from tests.data.test_instant_series import _ACCEPTED, _MID, _NEW, _OLD, _document, _fetcher

F = FinancialField


def _by_year(facts: tuple[Any, ...]) -> dict[int, float]:
    """The value of each fiscal year, from the newest filing that reports it."""
    newest: dict[int, Any] = {}
    for fact in facts:
        year = fact.observation_period_end.year
        if year not in newest or fact.available_at >= newest[year].available_at:
            newest[year] = fact
    return {year: fact.value for year, fact in sorted(newest.items())}


def _latest(ticker: str, field: FinancialField) -> float | None:
    values = _by_year(annual_series(ticker, field))
    return values[max(values)] / 1 if values else None


# --- fields, units and the series set ------------------------------------------------------------------------------


def test_the_thirteen_annual_fields_are_currency_fields_and_the_series_set_accepts_only_them_and_the_older_four() -> (
    None
):
    assert len(ANNUAL_PERIOD_FIELDS) == 13
    assert all(_expected_unit(field) is FinancialUnit.CURRENCY for field in ANNUAL_PERIOD_FIELDS)
    for field in ANNUAL_PERIOD_FIELDS:
        request = annual_request("SYN", field, count=3)
        assert request.observation_count == 3
    for field in (F.TOTAL_ASSETS, F.COMMON_SHARES_OUTSTANDING, F.CURRENT_PRICE, F.STOCKHOLDERS_EQUITY):
        with pytest.raises(ValueError, match="observation_count > 1"):
            FinancialFactRequest(
                FinancialSubjectKind.SECURITY, "SYN", field, SEC_PROVIDER_ID, basis="fiscal_year", observation_count=2
            )
    # An annual field is not a balance-sheet instant, and the reverse.
    assert not ANNUAL_PERIOD_FIELDS & INSTANT_SERIES_FIELDS
    assert _expected_unit(F.EPS) is FinancialUnit.CURRENCY_PER_SHARE


def test_every_annual_field_has_a_list_per_taxonomy_and_only_the_two_unsupported_ifrs_ones_are_empty() -> None:
    assert set(US_GAAP_ANNUAL_CONCEPTS) == ANNUAL_PERIOD_FIELDS == set(IFRS_ANNUAL_CONCEPTS)
    assert all(US_GAAP_ANNUAL_CONCEPTS.values())
    assert {field for field, names in IFRS_ANNUAL_CONCEPTS.items() if not names} == {
        F.SELLING_GENERAL_ADMINISTRATIVE,
        F.DEPRECIATION,
    }
    assert annual_concepts(F.TOTAL_ASSETS, "us-gaap") == ()
    assert annual_concepts(F.SALES, "ifrs-full") == ("Revenue", "RevenueFromContractsWithCustomers")


def test_a_request_for_a_new_field_without_a_fiscal_year_basis_is_not_served() -> None:
    adapter = adapter_for("WMT", FixtureFetcher("WMT", folder=ANNUAL_FIXTURES))
    request = FinancialFactRequest(
        FinancialSubjectKind.SECURITY, "WMT", F.SALES, SEC_PROVIDER_ID, basis="fiscal_year_end"
    )
    assert adapter.fetch_facts(request, effective_as_of=NOW) == ()


def test_facts_are_completed_annual_currency_amounts_with_provenance() -> None:
    facts = annual_series("WMT", F.NET_INCOME)
    newest = max(facts, key=lambda fact: fact.observation_period_end or NOW)

    assert newest.value == 21_893_000_000.0
    assert (newest.units, newest.currency, newest.basis, newest.period_kind) == (
        FinancialUnit.CURRENCY,
        "USD",
        "fiscal_year",
        PeriodKind.COMPLETED_ANNUAL,
    )
    assert newest.provider_field == "us-gaap:NetIncomeLoss"
    assert newest.observation_period_start == datetime(2025, 2, 1, tzinfo=UTC)
    assert newest.observation_period_end is not None
    assert newest.observation_period_end.date() == date(2026, 1, 31)
    assert newest.fiscal_year == 2026
    assert "concept_priority=NetIncomeLoss" in newest.notes
    assert any(note.startswith("accession=0000104169-26-000055") for note in newest.notes)


# --- revenue and the priority lists --------------------------------------------------------------------------------


def test_total_revenue_is_the_total_and_never_a_part_or_a_sum() -> None:
    walmart = _by_year(annual_series("WMT", F.SALES))
    # Walmart tags net sales (706,413) and total revenues (713,163): the face total is `Revenues`.
    assert walmart[2026] == 713_163_000_000.0
    assert walmart[2026] != 706_413_000_000.0 + 713_163_000_000.0
    assert {fact.provider_field for fact in annual_series("WMT", F.SALES)} == {"us-gaap:Revenues"}
    assert _by_year(annual_series("HON", F.SALES))[2025] == 37_442_000_000.0
    assert {fact.provider_field for fact in annual_series("DUK", F.SALES)} == {
        "us-gaap:RevenueFromContractWithCustomerIncludingAssessedTax"
    }
    assert _by_year(annual_series("SAP", F.SALES))[2025] == 36_800_000_000.0
    assert {fact.provider_field for fact in annual_series("NTR", F.SALES)} == {
        "ifrs-full:RevenueFromContractsWithCustomers"
    }


def _issuer(concepts: dict[str, list[tuple[str, list[dict[str, Any]]]]], **document: Any) -> FixtureFetcher:

    facts, submissions = _document(concepts, **document)
    return _fetcher(facts, submissions)


def _row(
    year: int, value: float, accession: str, *, start: str | None = None, end: str | None = None
) -> dict[str, Any]:

    return {
        "start": start or f"{year}-01-01",
        "end": end or f"{year}-12-31",
        "val": value,
        "accn": accession,
        "fy": year,
        "fp": "FY",
        "form": "10-K",
        "filed": _ACCEPTED[accession][:10],
    }


def _series(concepts: dict[str, list[tuple[str, list[dict[str, Any]]]]], field: FinancialField, **keywords: Any) -> Any:
    adapter = adapter_for("WMT", _issuer(concepts, **keywords))
    request = FinancialFactRequest(
        FinancialSubjectKind.SECURITY, "SYN", field, SEC_PROVIDER_ID, basis="fiscal_year", observation_count=3
    )
    with adapter.analysis_scope(subject_id="SYN", provider_id=SEC_PROVIDER_ID, as_of=None):
        return adapter.fetch_facts(request, effective_as_of=NOW)


def test_one_concept_serves_a_whole_series_and_a_year_it_does_not_cover_is_absent() -> None:

    concepts = {
        "Revenues": [("USD", [_row(2025, 300.0, _NEW), _row(2024, 200.0, _MID)])],
        "RevenueFromContractWithCustomerExcludingAssessedTax": [
            ("USD", [_row(2025, 299.0, _NEW), _row(2024, 199.0, _MID), _row(2023, 99.0, _OLD)])
        ],
    }
    facts = _series(concepts, F.SALES)
    assert _by_year(facts) == {2024: 200.0, 2025: 300.0}
    assert {fact.provider_field for fact in facts} == {"us-gaap:Revenues"}
    # The first listed concept is used only if it reports the newest year; otherwise the next one is.
    stale = {
        "Revenues": [("USD", [_row(2024, 200.0, _MID)])],
        "RevenueFromContractWithCustomerExcludingAssessedTax": concepts[
            "RevenueFromContractWithCustomerExcludingAssessedTax"
        ],
    }
    assert {fact.provider_field for fact in _series(stale, F.SALES)} == {
        "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax"
    }
    assert _series({"Assets": []}, F.SALES) == ()


def test_quarters_year_to_date_periods_and_stub_years_are_rejected_and_fifty_three_week_years_accepted() -> None:

    rows = [
        _row(2025, 300.0, _NEW),
        _row(2025, 70.0, _NEW, start="2025-01-01", end="2025-03-31"),
        _row(2025, 150.0, _NEW, start="2025-01-01", end="2025-06-30"),
        _row(2024, 10.0, _NEW, start="2024-07-01", end="2024-12-31"),
        _row(2023, 280.0, _NEW, start="2022-12-26", end="2023-12-31"),
        {**_row(2022, 5.0, _NEW), "fp": "Q4"},
        {**_row(2021, 5.0, _NEW), "form": "10-Q"},
    ]
    only_newest = {_NEW: _ACCEPTED[_NEW]}
    facts = _series({"Revenues": [("USD", rows)]}, F.SALES, accessions=only_newest)
    assert _by_year(facts) == {2023: 280.0, 2025: 300.0}
    deere = _by_year(annual_series("DE", F.SALES))
    assert set(deere) == {2023, 2024, 2025}


def test_the_boundary_and_the_taxonomy_regime_apply_to_the_new_fields_too() -> None:
    adapter = adapter_for("WMT", FixtureFetcher("WMT", folder=ANNUAL_FIXTURES))
    boundary = datetime(2025, 4, 1, tzinfo=UTC)
    request = annual_request("WMT", F.SALES, as_of=boundary)
    with adapter.analysis_scope(subject_id="WMT", provider_id=SEC_PROVIDER_ID, as_of=boundary):
        facts = adapter.fetch_facts(request, effective_as_of=boundary)
    assert max(_by_year(facts)) == 2025
    assert all(fact.available_at is not None and fact.available_at <= boundary for fact in facts)


# --- the regression set --------------------------------------------------------------------------------------------


def test_values_match_the_rendered_statements_the_evidence_checked() -> None:
    expected: dict[tuple[str, FinancialField], float] = {
        ("WMT", F.SALES): 713_163e6,
        ("WMT", F.COST_OF_REVENUE): 535_395e6,
        ("WMT", F.OPERATING_INCOME): 29_825e6,
        ("WMT", F.SELLING_GENERAL_ADMINISTRATIVE): 147_943e6,
        ("WMT", F.PRETAX_INCOME): 29_469e6,
        ("WMT", F.INCOME_TAX_EXPENSE): 7_199e6,
        ("WMT", F.NET_INCOME): 21_893e6,
        ("WMT", F.DEPRECIATION_AND_AMORTIZATION): 14_203e6,
        ("GOOGL", F.SALES): 402_836e6,
        ("GOOGL", F.COST_OF_REVENUE): 162_535e6,
        ("GOOGL", F.OPERATING_INCOME): 129_039e6,
        ("GOOGL", F.PRETAX_INCOME): 158_826e6,
        ("GOOGL", F.INCOME_TAX_EXPENSE): 26_656e6,
        ("GOOGL", F.NET_INCOME): 132_170e6,
        ("GOOGL", F.DEPRECIATION): 21_136e6,
        ("MRNA", F.SALES): 1_944e6,
        ("MRNA", F.COST_OF_REVENUE): 868e6,
        ("MRNA", F.OPERATING_INCOME): -3_074e6,
        ("MRNA", F.PRETAX_INCOME): -2_768e6,
        ("MRNA", F.NET_INCOME): -2_822e6,
        ("MNST", F.SALES): 8_294.343e6,
        ("MNST", F.GROSS_PROFIT): 4_632.195e6,
        ("MNST", F.OPERATING_INCOME): 2_419.354e6,
        ("MNST", F.INCOME_TAX_EXPENSE): 577.097e6,
        ("HON", F.SALES): 37_442e6,
        ("HON", F.COST_OF_REVENUE): 23_613e6,
        ("HON", F.SELLING_GENERAL_ADMINISTRATIVE): 5_450e6,
        ("HON", F.PRETAX_INCOME): 5_476e6,
        ("HON", F.INCOME_TAX_EXPENSE): 1_008e6,
        ("HON", F.NET_INCOME): 4_729e6,
        ("HON", F.DISCONTINUED_OPERATIONS): 304e6,
        ("HON", F.DEPRECIATION): 546e6,
        ("HON", F.DEPRECIATION_AND_AMORTIZATION): 1_388e6,
        ("SAP", F.SALES): 36_800e6,
        ("SAP", F.COST_OF_REVENUE): 9_986e6,
        ("SAP", F.GROSS_PROFIT): 26_814e6,
        ("SAP", F.OPERATING_INCOME): 9_617e6,
        ("SAP", F.PRETAX_INCOME): 10_270e6,
        ("SAP", F.INCOME_TAX_EXPENSE): 2_944e6,
        ("SAP", F.NET_INCOME): 7_161e6,
        ("SAP", F.DEPRECIATION_AND_AMORTIZATION): 1_311e6,
        ("SAP", F.DISCONTINUED_OPERATIONS): 0.0,
        ("NTR", F.SALES): 26_885e6,
        ("NTR", F.COST_OF_REVENUE): 17_602e6,
        ("NTR", F.GROSS_PROFIT): 8_347e6,
        ("NTR", F.OPERATING_INCOME): 3_736e6,
        ("NTR", F.PRETAX_INCOME): 3_049e6,
        ("NTR", F.INCOME_TAX_EXPENSE): 752e6,
        ("NTR", F.NET_INCOME): 2_267e6,
        ("NTR", F.DEPRECIATION_AND_AMORTIZATION): 2_369e6,
    }
    for (ticker, field), value in expected.items():
        values = _by_year(annual_series(ticker, field))
        assert values[max(values)] == pytest.approx(value), (ticker, field)


def test_every_field_of_every_regression_issuer_answers_with_only_annual_facts_in_one_currency() -> None:
    for ticker in REGRESSION_SET:
        for field in sorted(ANNUAL_PERIOD_FIELDS, key=lambda item: item.value):
            facts = annual_series(ticker, field)
            assert {fact.currency for fact in facts} <= {"EUR" if ticker == "SAP" else "USD"}
            assert all(fact.period_kind is PeriodKind.COMPLETED_ANNUAL for fact in facts)
            assert len({fact.provider_field for fact in facts}) <= 1, (ticker, field)


def test_unsupported_ifrs_fields_and_unreported_lines_are_unavailable_never_borrowed() -> None:
    for ticker in ("SAP", "NTR"):
        for field in (F.SELLING_GENERAL_ADMINISTRATIVE, F.DEPRECIATION):
            assert annual_series(ticker, field) == ()
    # Moderna reports "selling, general and administrative" under a general-and-administrative concept: not SG&A.
    assert annual_series("MRNA", F.SELLING_GENERAL_ADMINISTRATIVE) == ()
    # Alphabet reports no SG&A and no gross profit; Walmart reports no gross profit; Monster tags only ProfitLoss.
    assert annual_series("GOOGL", F.SELLING_GENERAL_ADMINISTRATIVE) == ()
    assert annual_series("WMT", F.GROSS_PROFIT) == ()
    assert annual_series("MNST", F.NET_INCOME) == ()
    # Walmart's gross interest is two lines (debt and finance leases), and InterestExpenseDebt is not the field.
    assert annual_series("WMT", F.INTEREST_EXPENSE) == ()
    # Deere's pre-tax concept includes equity-method results and is not the mapped one.
    assert annual_series("DE", F.PRETAX_INCOME) == ()


def test_interest_expense_reads_either_concept_the_evidence_shows_to_be_the_same_line() -> None:
    assert _by_year(annual_series("PLD", F.INTEREST_EXPENSE))[2025] == pytest.approx(1_002e6, rel=1e-3)
    assert {fact.provider_field for fact in annual_series("GOOGL", F.INTEREST_EXPENSE)} == {
        "us-gaap:InterestExpenseNonoperating"
    }
    assert {fact.provider_field for fact in annual_series("DUK", F.INTEREST_EXPENSE)} == {"us-gaap:InterestExpense"}
    assert _by_year(annual_series("NTR", F.INTEREST_EXPENSE))[2025] == 746e6


# --- pretax, tax, continuing and discontinued income share one fiscal period ---------------------------------------


def test_pretax_tax_continuing_and_discontinued_income_are_read_from_the_same_fiscal_period() -> None:
    for ticker in ("HON", "DUK"):
        periods = {}
        for field in (
            F.PRETAX_INCOME,
            F.INCOME_TAX_EXPENSE,
            F.INCOME_FROM_CONTINUING_OPERATIONS,
            F.DISCONTINUED_OPERATIONS,
        ):
            facts = annual_series(ticker, field)
            latest = max(fact.observation_period_end for fact in facts if fact.observation_period_end)
            periods[field] = {
                (fact.observation_period_start, fact.observation_period_end)
                for fact in facts
                if fact.observation_period_end == latest
            }
        assert len({frozenset(value) for value in periods.values()}) == 1, ticker
    # Honeywell: income from continuing operations (4,461) is the parent's share, so the parent's net income (4,729)
    # is that plus the parent's share of the discontinued result (268), not the 304 of the face.
    assert _by_year(annual_series("HON", F.INCOME_FROM_CONTINUING_OPERATIONS))[2025] == 4_461e6
    assert _by_year(annual_series("HON", F.DISCONTINUED_OPERATIONS))[2025] == 304e6
    # Under IFRS the same parent basis: SAP's continuing profit attributable to owners (7,161) is its net income.
    assert _by_year(annual_series("SAP", F.INCOME_FROM_CONTINUING_OPERATIONS))[2025] == 7_161e6
    assert _by_year(annual_series("SAP", F.NET_INCOME))[2025] == 7_161e6
    # A filer reporting neither continuing nor discontinued income reports nothing for them.
    assert annual_series("WMT", F.INCOME_FROM_CONTINUING_OPERATIONS) == ()
    assert annual_series("WMT", F.DISCONTINUED_OPERATIONS) == ()


# --- depreciation evidence -----------------------------------------------------------------------------------------


def _fixture_values(ticker: str, concept: str, year: int) -> list[float]:
    document = load(ticker, ANNUAL_FIXTURES)
    units = document["companyfacts"]["facts"]["us-gaap"][concept]["units"]["USD"]
    return [
        row["val"] for row in units if row["end"].startswith(str(year)) and row["accn"] == document["anchor_accession"]
    ]


def test_a_filing_that_reports_depreciation_alone_one_that_reports_only_combined_da_and_one_that_reports_both() -> None:
    # Alphabet: depreciation of property and equipment alone, no combined concept.
    assert _by_year(annual_series("GOOGL", F.DEPRECIATION))[2025] == 21_136e6
    assert annual_series("GOOGL", F.DEPRECIATION_AND_AMORTIZATION) == ()
    # Walmart, Monster, Moderna, Deere, Duke and Prologis: combined D&A only.
    for ticker in ("WMT", "MNST", "MRNA", "DE", "DUK", "PLD", "JPM"):
        assert annual_series(ticker, F.DEPRECIATION) == ()
        assert annual_series(ticker, F.DEPRECIATION_AND_AMORTIZATION) != ()
    # Honeywell: both, and the identity D&A = depreciation + amortization holds to the dollar.
    depreciation = _by_year(annual_series("HON", F.DEPRECIATION))
    combined = _by_year(annual_series("HON", F.DEPRECIATION_AND_AMORTIZATION))
    amortization = {year: _fixture_values("HON", "AdjustmentForAmortization", year) for year in (2023, 2024, 2025)}
    sums = {year: depreciation[year] + amortization[year][0] for year in (2023, 2024, 2025)}
    # Exact in 2023 and 2025; in 2024 the filer's own lines, each rounded to millions, differ by one million.
    assert sums[2023] == combined[2023]
    assert sums[2025] == combined[2025]
    assert abs(sums[2024] - combined[2024]) == 1e6


def test_depreciation_is_the_expense_of_the_year_and_not_the_accumulated_balance() -> None:
    for ticker in ("HON", "GOOGL"):
        for fact in annual_series(ticker, F.DEPRECIATION):
            assert fact.provider_field == "us-gaap:Depreciation"
            assert fact.observation_period_start is not None
            assert fact.observation_period_end is not None
            assert 335 <= (fact.observation_period_end - fact.observation_period_start).days + 1 <= 395
    # Honeywell's expense (546 million) is a fraction of its accumulated depreciation (7,431 million of 12,060 gross).
    assert _by_year(annual_series("HON", F.DEPRECIATION))[2025] < 7_431e6 / 10


def test_the_three_us_gaap_combined_concepts_are_one_line_item_and_ifrs_has_two_names_for_it() -> None:
    assert {fact.provider_field for fact in annual_series("WMT", F.DEPRECIATION_AND_AMORTIZATION)} == {
        "us-gaap:DepreciationAmortizationAndAccretionNet"
    }
    assert {fact.provider_field for fact in annual_series("PLD", F.DEPRECIATION_AND_AMORTIZATION)} == {
        "us-gaap:DepreciationAndAmortization"
    }
    assert {fact.provider_field for fact in annual_series("SAP", F.DEPRECIATION_AND_AMORTIZATION)} == {
        "ifrs-full:AdjustmentsForDepreciationAndAmortisationExpense"
    }
    assert {fact.provider_field for fact in annual_series("NTR", F.DEPRECIATION_AND_AMORTIZATION)} == {
        "ifrs-full:DepreciationAndAmortisationExpense"
    }
    # Nutrien tags both IFRS names with one value for the year.
    document = load("NTR", ANNUAL_FIXTURES)["companyfacts"]["facts"]["ifrs-full"]
    both = {
        name: [row["val"] for row in document[name]["units"]["USD"] if row["end"] == "2025-12-31"][0]
        for name in ("DepreciationAndAmortisationExpense", "AdjustmentsForDepreciationAndAmortisationExpense")
    }
    assert len(set(both.values())) == 1


def test_net_ppe_is_obtainable_for_the_same_dates_as_depreciation_where_a_filer_tags_it() -> None:
    # Alphabet changed the concept of its balance-sheet line in 2025 and Honeywell and Moderna use the finance-lease
    # variant throughout; both concepts are the face line of the filer that uses them.
    honeywell = series("HON", F.NET_PPE, count=2)
    assert {fact.provider_field for fact in honeywell.facts} == {
        "us-gaap:PropertyPlantAndEquipmentAndFinanceLeaseRightOfUseAssetAfterAccumulatedDepreciationAndAmortization"
    }
    assert {
        fact.observation_period_end.year: fact.value for fact in honeywell.facts if fact.observation_period_end
    } == {
        2024: 4_457e6,
        2025: 4_629e6,
    }
    alphabet = series("GOOGL", F.NET_PPE)
    assert len(alphabet.facts) == 2
    assert [item.reason.value for item in alphabet.absences] == ["other_concept"]


def test_the_depi_algebra_checked_by_hand_against_honeywell() -> None:
    depreciation = _by_year(annual_series("HON", F.DEPRECIATION))
    plant = {
        fact.observation_period_end.year: fact.value
        for fact in series("HON", F.NET_PPE, count=2).facts
        if fact.observation_period_end
    }
    # [depreciation / (depreciation + net PP&E)] of the prior year, over the same for the year.
    prior = depreciation[2024] / (depreciation[2024] + plant[2024])
    current = depreciation[2025] / (depreciation[2025] + plant[2025])
    assert prior == pytest.approx(493 / (493 + 4_457))
    assert current == pytest.approx(546 / (546 + 4_629))
    assert prior / current == pytest.approx(0.9439, abs=1e-4)


def test_the_new_fields_work_without_an_analysis_scope_for_us_gaap_filers() -> None:
    adapter = adapter_for("HON", FixtureFetcher("HON", folder=ANNUAL_FIXTURES))
    facts = adapter.fetch_facts(annual_request("HON", F.NET_INCOME), effective_as_of=NOW)
    assert _by_year(facts)[2025] == 4_729e6


def test_the_annual_fixtures_match_their_checksums() -> None:
    lines = (ANNUAL_FIXTURES / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
    listed = {line.split("  ")[1]: line.split("  ")[0] for line in lines}
    assert set(listed) == {path.name for path in ANNUAL_FIXTURES.glob("*.json")}
    for name, digest in listed.items():
        assert hashlib.sha256((ANNUAL_FIXTURES / name).read_bytes()).hexdigest() == digest
    document = copy.deepcopy(load("JPM", ANNUAL_FIXTURES))
    assert set(document["pages"]) == {"CIK0000019617-submissions-008.json", "CIK0000019617-submissions-018.json"}


# --- paging for the annual series (JPMorgan) -----------------------------------------------------------------------


def test_jpmorgans_older_annual_facts_take_their_acceptance_times_from_the_extra_pages() -> None:
    fetcher = FixtureFetcher("JPM", folder=ANNUAL_FIXTURES)
    facts = annual_series("JPM", F.OPERATING_CASH_FLOW, adapter=adapter_for("JPM", fetcher))

    by_filing = {}
    for fact in facts:
        accession = next(note for note in fact.notes if note.startswith("accession=")).removeprefix("accession=")
        by_filing[accession] = fact.available_at
    assert by_filing["0000019617-25-000270"] == datetime(2025, 2, 14, 21, 17, 7, tzinfo=UTC)
    assert by_filing["0000019617-24-000225"] == datetime(2024, 2, 16, 21, 20, 22, tzinfo=UTC)
    assert all("acceptanceDateTime unavailable" not in note for fact in facts for note in fact.notes)
    pages = [call.rsplit("/", 1)[1] for call in fetcher.calls if "-submissions-" in call]
    assert sorted(pages) == ["CIK0000019617-submissions-008.json", "CIK0000019617-submissions-018.json"]
    assert {fact.observation_period_end.year for fact in facts if fact.observation_period_end} == {2023, 2024, 2025}


def test_the_new_fields_page_too_and_a_series_in_the_recent_block_reads_no_page() -> None:
    fetcher = FixtureFetcher("JPM", folder=ANNUAL_FIXTURES)
    adapter = adapter_for("JPM", fetcher)
    sales = annual_series("JPM", F.SALES, adapter=adapter)
    assert {fact.observation_period_end.year for fact in sales if fact.observation_period_end} == {2023, 2024, 2025}
    assert len([call for call in fetcher.calls if "-submissions-" in call]) == 2
    recent = FixtureFetcher("JPM", folder=ANNUAL_FIXTURES)
    annual_series("JPM", F.SALES, count=1, adapter=adapter_for("JPM", recent))
    assert [call for call in recent.calls if "-submissions-" in call] == []
