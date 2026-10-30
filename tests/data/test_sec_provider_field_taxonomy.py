"""The taxonomy of a provider field the SEC adapter emits."""

import pytest

from investment_analysis_engine.data.financial.facts import FinancialField as F
from investment_analysis_engine.data.sec_edgar import financial_facts
from investment_analysis_engine.data.sec_edgar.annual_series import IFRS_ANNUAL_CONCEPTS, US_GAAP_ANNUAL_CONCEPTS
from investment_analysis_engine.data.sec_edgar.financial_facts import taxonomy_of_provider_field
from investment_analysis_engine.data.sec_edgar.instant_series import IFRS_CONCEPTS, US_GAAP_CONCEPTS

# The fields the Piotroski F-Score reads, from the instant series and from the completed-annual series.
_INSTANT_FIELDS = (
    F.TOTAL_ASSETS,
    F.CURRENT_ASSETS,
    F.CURRENT_LIABILITIES,
    F.SHORT_TERM_BORROWINGS,
    F.CURRENT_PORTION_OF_LONG_TERM_DEBT,
    F.NONCURRENT_LONG_TERM_DEBT,
    F.LONG_TERM_DEBT_TOTAL,
    F.LEASE_LIABILITIES_AS_DEBT,
)
_ANNUAL_FIELDS = (F.SALES, F.COST_OF_REVENUE, F.GROSS_PROFIT, F.NET_INCOME, F.INTEREST_EXPENSE)


def _concept_fields() -> list[tuple[str, str]]:
    """Return each (provider field, taxonomy) the adapter forms as ``<taxonomy>:<concept>`` for those fields."""
    forms: list[tuple[str, str]] = []
    for taxonomy, instant, annual in (
        ("us-gaap", US_GAAP_CONCEPTS, US_GAAP_ANNUAL_CONCEPTS),
        ("ifrs-full", IFRS_CONCEPTS, IFRS_ANNUAL_CONCEPTS),
    ):
        for field_name in _INSTANT_FIELDS:
            forms.extend((f"{taxonomy}:{concept}", taxonomy) for concept in instant.get(field_name, ()))
        for field_name in _ANNUAL_FIELDS:
            forms.extend((f"{taxonomy}:{concept}", taxonomy) for concept in annual.get(field_name, ()))
    return forms


def test_the_concept_tables_give_fields_on_both_taxonomies() -> None:
    assert {taxonomy for _field, taxonomy in _concept_fields()} == {"us-gaap", "ifrs-full"}


@pytest.mark.parametrize(("provider_field", "taxonomy"), _concept_fields())
def test_every_concept_the_adapter_reads_for_those_fields_has_its_taxonomy(provider_field: str, taxonomy: str) -> None:
    assert taxonomy_of_provider_field(provider_field) == taxonomy


@pytest.mark.parametrize(
    ("provider_field", "taxonomy"),
    [
        (financial_facts.SEC_OPERATING_CASH_FLOW_FIELD, "us-gaap"),
        (financial_facts.SEC_IFRS_OPERATING_CASH_FLOW_FIELD, "ifrs-full"),
        (financial_facts.SEC_STOCKHOLDERS_EQUITY_FIELD, "us-gaap"),
        (financial_facts.SEC_EPS_FIELD, "us-gaap"),
        (financial_facts.SEC_IFRS_EPS_FIELD, "ifrs-full"),
    ],
)
def test_the_adapters_provider_field_constants_have_their_taxonomy(provider_field: str, taxonomy: str) -> None:
    assert taxonomy_of_provider_field(provider_field) == taxonomy


def test_the_derived_share_count_field_has_the_taxonomy_its_parts_share() -> None:
    derived = financial_facts._SEC_DERIVED_COMMON_SHARES_FIELD
    assert derived.startswith("derived:")
    assert taxonomy_of_provider_field(derived) == "us-gaap"
    assert taxonomy_of_provider_field("derived:ifrs-full:SharesIssued-ifrs-full:TreasuryShares") == "ifrs-full"


@pytest.mark.parametrize(
    "provider_field",
    [
        "derived:us-gaap:CommonStockSharesIssued-ifrs-full:TreasuryShares",
        financial_facts.SEC_COVER_PAGE_SHARES_FIELD,
        financial_facts._SEC_INFERRED_PREFERRED_ABSENCE_FIELD,
        "derived:us-gaap:CommonStockSharesIssued",
        "derived:us-gaap:A-us-gaap",
        "derived:us-gaap:A-other:B",
        "synthetic:net_income_t",
        "us-gaap:",
        "us-gaap:A:B",
        "us-gaap:A-us-gaap:B",
        "us-gaap",
        "Assets",
        "",
    ],
)
def test_a_form_the_adapter_does_not_emit_has_no_taxonomy(provider_field: str) -> None:
    assert taxonomy_of_provider_field(provider_field) is None
