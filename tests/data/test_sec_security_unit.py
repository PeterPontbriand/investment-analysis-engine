"""Synthetic filing shapes for source-unit validation; no downloaded filings."""

from collections.abc import Mapping
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from src.data.financial.provenance import ResolvedInput, SourceKind
from src.data.sec_edgar.filing_document import FilingReaderPolicy, fetch_filing, filing_url
from src.data.sec_edgar.financial_facts import SecEdgarFinancialFactsAdapter
from src.data.sec_edgar.security_unit import UnitMappingError, parse_unit_document
from src.data.security_unit import SecurityUnitRequest

NOW = datetime(2026, 9, 9, tzinfo=UTC)
ACCESSION = "0001628280-26-010047"


def filing_markup() -> str:
    """Return a reduced synthetic KO-shaped filing, including a debt registration."""
    contexts = []
    facts = []
    for year, eps in ((2023, 2), (2024, 3), (2025, 4)):
        contexts.append(
            f'<x:context id="y{year}"><x:entity><x:identifier>0000021344</x:identifier></x:entity>'
            f"<x:period><x:startDate>{year}-01-01</x:startDate><x:endDate>{year}-12-31</x:endDate></x:period></x:context>"
        )
        facts.append(
            f'<i:nonFraction name="g:EarningsPerShareDiluted" contextRef="y{year}" unitRef="per">{eps}</i:nonFraction>'
        )
    contexts.append(
        '<x:context id="balance"><x:entity><x:identifier>0000021344</x:identifier></x:entity>'
        "<x:period><x:instant>2025-12-31</x:instant></x:period></x:context>"
    )
    for concept, value, unit in (
        ("StockholdersEquity", 1000, "usd"),
        ("CommonStockSharesIssued", 200, "shares"),
        ("TreasuryStockCommonShares", 100, "shares"),
    ):
        facts.append(f'<i:nonFraction name="g:{concept}" contextRef="balance" unitRef="{unit}">{value}</i:nonFraction>')
    # The real filing repeats equity in component and investee contexts. These
    # disclosures are not competing entity-wide totals or separate share classes.
    for context, axis, member, value in (
        ("equity_component", "StatementEquityComponentsAxis", "CommonStockMember", 200),
        ("investee", "EquityMethodInvestmentNonconsolidatedInvesteeAxis", "InvesteeMember", 1500),
    ):
        contexts.append(
            f'<x:context id="{context}"><x:entity><x:identifier>0000021344</x:identifier>'
            f'<x:segment><d:explicitMember dimension="g:{axis}">g:{member}</d:explicitMember>'
            "</x:segment></x:entity><x:period><x:instant>2025-12-31</x:instant></x:period></x:context>"
        )
        facts.append(
            f'<i:nonFraction name="g:StockholdersEquity" contextRef="{context}" unitRef="usd">{value}</i:nonFraction>'
        )
    for context, member, title, symbol in (
        ("common", "CommonMember", "Common Stock, $0.25 Par Value", "KO"),
        ("debt", "DebtMember", "1.875% Notes Due 2026", "KO26"),
    ):
        contexts.append(
            f'<x:context id="{context}"><x:entity><x:identifier>0000021344</x:identifier>'
            f'<x:segment><d:explicitMember dimension="g:StatementClassOfStockAxis">ko:{member}</d:explicitMember>'
            "</x:segment></x:entity><x:period><x:startDate>2025-01-01</x:startDate>"
            "<x:endDate>2025-12-31</x:endDate></x:period></x:context>"
        )
        for concept, text in (("Security12bTitle", title), ("TradingSymbol", symbol), ("SecurityExchangeName", "NYSE")):
            facts.append(f'<i:nonNumeric name="dei:{concept}" contextRef="{context}">{text}</i:nonNumeric>')
    return (
        '<html xmlns:x="http://www.xbrl.org/2003/instance" xmlns:i="http://www.xbrl.org/2013/inlineXBRL" '
        'xmlns:g="http://fasb.org/us-gaap/2025" xmlns:dei="http://xbrl.sec.gov/dei/2025" '
        'xmlns:d="http://xbrl.org/2006/xbrldi" xmlns:ko="http://example.test/ko" '
        'xmlns:iso="http://www.xbrl.org/2003/iso4217">'
        + "".join(contexts)
        + '<x:unit id="usd"><x:measure>iso:USD</x:measure></x:unit>'
        '<x:unit id="shares"><x:measure>x:shares</x:measure></x:unit>'
        '<x:unit id="per"><x:divide><x:unitNumerator><x:measure>iso:USD</x:measure></x:unitNumerator>'
        "<x:unitDenominator><x:measure>x:shares</x:measure></x:unitDenominator></x:divide></x:unit>"
        + "".join(facts)
        + "</html>"
    )


def company_facts() -> dict[str, Any]:
    """Build matching synthetic source facts for the real SEC adapter."""
    concepts: dict[str, Any] = {}
    for concept, values, units in (
        ("EarningsPerShareDiluted", [(2023, 2), (2024, 3), (2025, 4)], "USD/shares"),
        ("StockholdersEquity", [(2025, 1000)], "USD"),
        ("CommonStockSharesIssued", [(2025, 200)], "shares"),
        ("TreasuryStockCommonShares", [(2025, 100)], "shares"),
    ):
        observations = []
        for year, value in values:
            item: dict[str, Any] = {
                "end": f"{year}-12-31",
                "val": value,
                "accn": ACCESSION,
                "fy": 2025,
                "fp": "FY",
                "form": "10-K",
                "filed": "2026-02-20",
            }
            if concept == "EarningsPerShareDiluted":
                item["start"] = f"{year}-01-01"
            observations.append(item)
        concepts[concept] = {"units": {units: observations}}
    return {"cik": 21344, "entityName": "Synthetic KO", "facts": {"us-gaap": concepts}}


class FilingFixture:
    """Inject SEC JSON and documents; reject every unexpected URL."""

    def __init__(self) -> None:
        """Prepare isolated synthetic payloads and fetch records."""
        self.markup = filing_markup()
        self.facts = company_facts()
        self.documents: list[str] = []
        self.submissions: dict[str, Any] = {
            "cik": "0000021344",
            "tickers": ["KO"],
            "filings": {
                "recent": {
                    "accessionNumber": [ACCESSION],
                    "form": ["10-K"],
                    "acceptanceDateTime": ["2026-02-20T14:46:00Z"],
                    "primaryDocument": ["ko-20251231.htm"],
                }
            },
        }

    def json(self, url: str, *, headers: Mapping[str, str]) -> object:
        assert headers["User-Agent"]
        if url.endswith("company_tickers.json"):
            return {"0": {"ticker": "KO", "cik_str": 21344, "title": "Synthetic KO"}}
        if "/companyfacts/" in url:
            return self.facts
        if "/submissions/" in url:
            return self.submissions
        raise AssertionError(url)

    def document(self, url: str, *, headers: Mapping[str, str], policy: FilingReaderPolicy) -> str:
        assert headers["User-Agent"]
        assert policy.max_documents == 4
        assert url == filing_url("21344", ACCESSION, "ko-20251231.htm")
        self.documents.append(url)
        return self.markup


def eps_input() -> ResolvedInput:
    return ResolvedInput(
        field_name="eps",
        value=4,
        source_kind=SourceKind.PROVIDER,
        resolved_at=NOW,
        provider_id="sec_edgar",
        provider_field="us-gaap:EarningsPerShareDiluted",
        units="currency_per_share",
        currency="USD",
        retrieved_at=NOW,
        observation_period_start=datetime(2025, 1, 1, tzinfo=UTC),
        observation_period_end=datetime(2025, 12, 31, tzinfo=UTC),
        provider_fact_id=f"{ACCESSION}:us-gaap:EarningsPerShareDiluted:USD:2025-01-01:2025-12-31",
    )


def test_context_join_and_exact_source_value() -> None:
    parsed = parse_unit_document(filing_markup(), cik="21344", ticker="KO")
    assert parsed.class_contexts == ("common",)
    assert parsed.verify(eps_input()) == ("y2025",)
    with pytest.raises(UnitMappingError):
        parsed.verify(replace(eps_input(), value=4.1))
    with pytest.raises(UnitMappingError):
        parse_unit_document(filing_markup(), cik="21344", ticker="KO26")


def equity_input() -> ResolvedInput:
    """Return the synthetic aggregate equity source, not an equity component."""
    return replace(
        eps_input(),
        field_name="stockholders_equity",
        value=1000,
        provider_field="us-gaap:StockholdersEquity",
        units="currency",
        observation_period_start=None,
    )


def test_equity_components_do_not_override_entity_wide_total() -> None:
    parsed = parse_unit_document(filing_markup(), cik="21344", ticker="KO")
    assert parsed.verify(equity_input()) == ("balance",)
    # Neither a component nor an investee value can substitute for the total.
    for value in (200, 1500):
        with pytest.raises(UnitMappingError, match="absent or contradictory"):
            parsed.verify(replace(equity_input(), value=value))


def test_equity_total_is_required_and_conflicting_totals_still_reject() -> None:
    aggregate = '<i:nonFraction name="g:StockholdersEquity" contextRef="balance" unitRef="usd">1000</i:nonFraction>'
    markup = filing_markup()
    assert aggregate in markup
    parsed = parse_unit_document(markup.replace(aggregate, ""), cik="21344", ticker="KO")
    with pytest.raises(UnitMappingError, match="absent or contradictory"):
        parsed.verify(equity_input())
    conflict = aggregate.replace(">1000<", ">1001<")
    parsed = parse_unit_document(markup.replace("</html>", conflict + "</html>"), cik="21344", ticker="KO")
    with pytest.raises(UnitMappingError, match="absent or contradictory"):
        parsed.verify(equity_input())


def test_financial_share_class_dimension_still_rejects() -> None:
    markup = filing_markup().replace("g:StatementEquityComponentsAxis", "g:StatementClassOfStockAxis")
    with pytest.raises(UnitMappingError, match="Class-specific financial input"):
        parse_unit_document(markup, cik="21344", ticker="KO")


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("Common Stock, $0.25 Par Value", "Class A Common Stock"),
        ("Common Stock, $0.25 Par Value", "American Depositary Shares"),
        ("Common Stock, $0.25 Par Value", "Preferred Stock"),
        ("1.875% Notes Due 2026", "Unrecognized Units"),
        ('contextRef="common">KO<', 'contextRef="common">OTHER<'),
        ('name="dei:Security12bTitle"', 'continuedAt="unknown" name="dei:Security12bTitle"'),
        ("0000021344", "0000021345"),
    ],
)
def test_unsupported_evidence_fails_closed(old: str, new: str) -> None:
    with pytest.raises(UnitMappingError):
        parse_unit_document(filing_markup().replace(old, new), cik="21344", ticker="KO")


@pytest.mark.parametrize("filename", ["../other.htm", "https://example.com/x.htm", "x.htm?secret=1", "x%2f.htm"])
def test_document_url_rejects_escape(filename: str) -> None:
    with pytest.raises(ValueError, match="Invalid primary document"):
        filing_url("21344", ACCESSION, filename)


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ('id="y2023"', 'id="y2025"'),
        ('id="usd"', 'id="shares"'),
        ('unitRef="per">4', 'unitRef="usd">4'),
        ('unitRef="per">4', 'unitRef="per" scale="21">4'),
        ('unitRef="per">4', 'unitRef="per" format="g:unknown">4'),
        ('unitRef="per">4', 'unitRef="per">NaN'),
        ('unitRef="per">4', 'unitRef="per"><i:exclude>4</i:exclude>'),
        ('unitRef="per">4', 'unitRef="per" continuedAt="other">4'),
        ('unitRef="per">4', 'unitRef="per" xmlns:z="http://www.w3.org/2001/XMLSchema-instance" z:nil="true">4'),
        ("1.875% Notes Due 2026", "Common Stock"),
        ("</html>", ""),
        ('unitRef="shares">200', 'unitRef="shares">0'),
        ('dimension="g:StatementClassOfStockAxis"', 'dimension="ko:StatementClassOfStockAxis"'),
    ],
)
def test_malformed_or_ambiguous_financial_evidence(old: str, new: str) -> None:
    with pytest.raises(UnitMappingError):
        parse_unit_document(filing_markup().replace(old, new), cik="21344", ticker="KO").verify(eps_input())


def test_nested_scaled_numeric_and_conflicting_duplicate() -> None:
    markup = filing_markup().replace('unitRef="per">4', 'unitRef="per" scale="-1"><span>40</span>')
    parsed = parse_unit_document(markup, cik="21344", ticker="KO")
    assert parsed.verify(eps_input()) == ("y2025",)
    duplicate = '<i:nonFraction name="g:EarningsPerShareDiluted" contextRef="y2025" unitRef="per">5</i:nonFraction>'
    parsed = parse_unit_document(markup.replace("</html>", duplicate + "</html>"), cik="21344", ticker="KO")
    with pytest.raises(UnitMappingError, match="contradictory"):
        parsed.verify(eps_input())


def test_transport_enforces_size_timeout_user_agent_and_no_redirects() -> None:
    policy = FilingReaderPolicy(timeout_seconds=3, max_document_bytes=8)
    url = filing_url("21344", ACCESSION, "ko.htm")
    opener = MagicMock()
    response = opener.open.return_value.__enter__.return_value
    response.read.return_value = b"<html />"
    with patch("src.data.sec_edgar.filing_document.build_opener", return_value=opener) as builder:
        assert fetch_filing(url, headers={"User-Agent": "Synthetic"}, policy=policy) == "<html />"
        opener.open.assert_called_once()
        assert opener.open.call_args.kwargs["timeout"] == 3
        assert opener.open.call_args.args[0].get_header("User-agent") == "Synthetic"
        response.read.assert_called_once_with(9)
        assert builder.call_args.args[0].redirect_request() is None
        response.read.return_value = b"123456789"
        with pytest.raises(ValueError, match="size limit"):
            fetch_filing(url, headers={"User-Agent": "Synthetic"}, policy=policy)
    with pytest.raises(ValueError, match="User-Agent"):
        fetch_filing(url, headers={}, policy=policy)
    with pytest.raises(ValueError, match="Unsupported filing URL"):
        fetch_filing("https://example.test/x.htm", headers={"User-Agent": "Synthetic"}, policy=policy)


@pytest.mark.parametrize(
    ("case", "reason"),
    [
        ("legacy", "missing_evidence"),
        ("historical", "unsupported_temporal_evidence"),
        ("primary", "unsupported_evidence"),
        ("provider", "provider_unsupported"),
        ("symbol", "source_mismatch"),
        ("overflow", "unsupported_evidence"),
        ("transport", "provider_error"),
    ],
)
def test_acquisition_boundaries(case: str, reason: str) -> None:
    fixture = FilingFixture()
    source = eps_input()
    inputs: tuple[ResolvedInput, ...] = (source,)
    if case == "legacy":
        inputs = (replace(source, provider_fact_id=None),)
    if case == "primary":
        fixture.submissions["filings"]["recent"]["primaryDocument"] = []
    if case == "symbol":
        fixture.submissions["tickers"] = ["OTHER"]
    if case == "overflow":
        inputs = tuple(replace(source, provider_fact_id=f"0001628280-26-{i:06}:source") for i in range(5))
    request = SecurityUnitRequest(
        "KO",
        "sec_edgar",
        NOW if case == "historical" else None,
        inputs,
        replace(source, provider_id="other" if case == "provider" else "yfinance"),
    )
    adapter = SecEdgarFinancialFactsAdapter(
        json_fetcher=fixture.json, filing_fetcher=fixture.document, clock=lambda: NOW, user_agent="Synthetic"
    )
    with adapter.analysis_scope(subject_id="KO", provider_id="sec_edgar", as_of=None):
        if case == "transport":
            with patch.object(adapter, "_filing_fetcher", side_effect=OSError("private transport detail")):
                resolution = adapter.resolve_security_unit(request)
        else:
            resolution = adapter.resolve_security_unit(request)
    assert resolution.reason.value == reason
    assert resolution.evidence is None
    assert fixture.documents == []


def test_four_original_accessions_are_each_verified_once() -> None:
    fixture = FilingFixture()
    accessions = [f"0001628280-26-{i:06}" for i in range(4)]
    for concept in fixture.facts["facts"]["us-gaap"].values():
        for observations in concept["units"].values():
            for observation in observations:
                observation["accn"] = accessions[-1]
    recent = fixture.submissions["filings"]["recent"]
    recent["accessionNumber"] = accessions
    for name in ("form", "acceptanceDateTime", "primaryDocument"):
        recent[name] *= 4
    inputs = tuple(replace(eps_input(), provider_fact_id=f"{accession}:source") for accession in accessions)
    seen: list[str] = []

    def document(url: str, *, headers: Mapping[str, str], policy: FilingReaderPolicy) -> str:
        assert headers["User-Agent"]
        assert policy.max_documents == 4
        seen.append(url)
        return fixture.markup

    adapter = SecEdgarFinancialFactsAdapter(
        json_fetcher=fixture.json, filing_fetcher=document, clock=lambda: NOW, user_agent="Synthetic"
    )
    request = SecurityUnitRequest("KO", "sec_edgar", None, inputs, replace(eps_input(), provider_id="yfinance"))
    with adapter.analysis_scope(subject_id="KO", provider_id="sec_edgar", as_of=None):
        result = adapter.resolve_security_unit(request)
    assert result.reason.value == "resolved"
    assert result.provenance is not None
    assert {item.accession for item in result.provenance.documents} == set(accessions)
    assert len(seen) == len(set(seen)) == 4


def test_conflicting_registered_titles_fail_closed() -> None:
    fact = '<i:nonNumeric name="dei:Security12gTitle" contextRef="common">Preferred Stock</i:nonNumeric>'
    with pytest.raises(UnitMappingError, match="Conflicting registered"):
        parse_unit_document(filing_markup().replace("</html>", fact + "</html>"), cik="21344", ticker="KO")
