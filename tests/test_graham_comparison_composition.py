"""Verify comparison evidence through real SEC/facade/service/CLI composition."""

import json
from contextlib import nullcontext
from dataclasses import replace
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from src.analysis.shared.financial_resolution import evaluate_price_comparison
from src.analysis.strategy.graham_growth.calculation import GrahamGrowthInputResolver
from src.analysis.strategy.graham_number.calculation import GrahamNumberInputResolver
from src.cli import app
from src.data.financial.cache import InMemoryResolvedInputCache
from src.data.financial.facts import FinancialFactRequest, FinancialUnit, ProviderFact
from src.data.financial.production import ProductionFinancialFactsProvider
from src.data.sec_edgar.financial_facts import SecEdgarFinancialFactsAdapter
from src.data.security_unit import SecurityUnitEvidence, SecurityUnitKind
from tests.data.test_sec_security_unit import NOW, FilingFixture, eps_input


class QuoteProvider:
    def fetch_facts(self, request: FinancialFactRequest) -> tuple[ProviderFact, ...]:
        return (
            ProviderFact(
                subject_kind=request.subject_kind,
                subject_id=request.subject_id,
                field_name=request.field_name,
                value=50,
                units=FinancialUnit.CURRENCY_PER_SHARE,
                currency="USD",
                provider_id="yfinance",
                provider_field="fast_info.last_price",
                retrieved_at=NOW,
                available_at=NOW,
                observed_at=NOW,
            ),
        )


@pytest.mark.parametrize("command", ["graham-number", "graham-growth"])
@pytest.mark.parametrize("mode", ["", "--json", "--details", "--diagnostics"])
@pytest.mark.parametrize("bypass", [False, True])
def test_verified_comparison_reaches_cli_and_cache(command: str, mode: str, bypass: bool) -> None:
    fixture = FilingFixture()
    sec = SecEdgarFinancialFactsAdapter(
        json_fetcher=fixture.json, filing_fetcher=fixture.document, clock=lambda: NOW, user_agent="Synthetic test"
    )
    provider = ProductionFinancialFactsProvider(sec_edgar=sec, yfinance=QuoteProvider())
    resolver_type = GrahamGrowthInputResolver if command == "graham-growth" else GrahamNumberInputResolver
    resolver = resolver_type(provider, cache=InMemoryResolvedInputCache(), clock=lambda: NOW)
    arguments = [command, "KO"]
    if mode:
        arguments.append(mode)
    if bypass:
        arguments.append("--no-cache")
    if command == "graham-growth":
        arguments.extend(["--expected-growth", "5", "--aaa-yield", "4.5"])
    with (
        patch("src.cli._build_graham_resolver", return_value=resolver),
        patch("src.cli.YFinanceClient.resolve_security_identity", return_value=None),
        patch("src.cli.YFinanceClient.resolve_instrument_kind", return_value=None),
        patch("src.cli._production_financial_cache", return_value=_cache_context()),
        patch("socket.socket.connect", side_effect=AssertionError("Network forbidden")),
    ):
        for _ in range(2):
            result = CliRunner().invoke(app, arguments)
            if result.exception is not None:
                raise result.exception
            assert result.exit_code == 0, result.output
            if mode == "--json":
                payload = json.loads(result.stdout)
                assert payload["schema_version"] == 5
                comparison = payload["price_comparison"]
                assert comparison["status"] == "available", comparison
                assert comparison["provenance"]["documents"][0]["accession"] == "0001628280-26-010047"
                key = "maximum_indicated_price" if command == "graham-number" else "growth_value"
                expected = (payload["result"][key] - 50) / payload["result"][key] * 100
                assert comparison["percent"] == pytest.approx(expected)
                assert comparison["percent"] == payload["result"]["margin_of_safety_percent"]
            else:
                assert result.output.startswith("Synthetic KO (KO) —")
                assert "Data quality rejected an input" not in result.output
                assert "Price relationship:" in result.stdout, result.stdout
                if mode == "--diagnostics":
                    assert "Share contexts:" in result.stdout
                    assert "Share-unit provider: SEC EDGAR" in result.stdout
                elif mode == "--details":
                    assert "Share contexts:" not in result.stdout
                    assert "Share-unit comparison: compatible" in result.stdout
                    assert "https://www.sec.gov/" in result.stdout
    assert len(fixture.documents) == 2


def _cache_context() -> nullcontext[InMemoryResolvedInputCache]:
    return nullcontext(InMemoryResolvedInputCache())


def test_bad_filing_preserves_value_and_reports_reason() -> None:
    fixture = FilingFixture()
    fixture.markup = fixture.markup.replace("Common Stock, $0.25 Par Value", "American Depositary Shares")
    sec = SecEdgarFinancialFactsAdapter(
        json_fetcher=fixture.json, filing_fetcher=fixture.document, clock=lambda: NOW, user_agent="Synthetic test"
    )
    provider = ProductionFinancialFactsProvider(sec_edgar=sec, yfinance=QuoteProvider())
    resolver = GrahamNumberInputResolver(provider, clock=lambda: NOW)
    with (
        patch("src.cli._build_graham_resolver", return_value=resolver),
        patch("src.cli.YFinanceClient.resolve_security_identity", return_value=None),
        patch("src.cli.YFinanceClient.resolve_instrument_kind", return_value=None),
        patch("socket.socket.connect", side_effect=AssertionError("Network forbidden")),
    ):
        result = CliRunner().invoke(app, ["graham-number", "KO", "--no-cache", "--json"])
    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"
    assert payload["result"]["maximum_indicated_price"] > 0
    assert payload["price_comparison"]["status"] == "unavailable"
    assert payload["price_comparison"]["reason"] == "unsupported_evidence"


@pytest.mark.parametrize(
    ("kind", "ratio", "reason"),
    [
        (SecurityUnitKind.ORDINARY_SHARE, None, "unknown_ratio"),
        (SecurityUnitKind.ORDINARY_SHARE, 2.0, "non_unit_ratio"),
        (SecurityUnitKind.ADR, 1.0, "unsupported_unit_kind"),
    ],
)
def test_structured_comparison_preserves_unit_rejections(
    kind: SecurityUnitKind, ratio: float | None, reason: str
) -> None:
    evidence = SecurityUnitEvidence("KO", SecurityUnitKind.ORDINARY_SHARE, kind, ratio, "sec_edgar", "synthetic")
    result = evaluate_price_comparison(
        20,
        eps_input(),
        valuation_currency="USD",
        security_unit_evidence=evidence,
        require_security_unit_evidence=True,
    )
    assert result.percent is None
    assert result.reason == reason


def test_structured_reason_precedence_and_legacy_math() -> None:
    quote = eps_input()
    assert evaluate_price_comparison(None, None).reason == "calculation_unavailable"
    assert evaluate_price_comparison(-1, None).reason == "missing_quote"
    assert evaluate_price_comparison(-1, quote).reason == "nonpositive_reference"
    assert (
        evaluate_price_comparison(
            20, replace(quote, currency="CAD"), valuation_currency="USD", require_security_unit_evidence=True
        ).reason
        == "currency_mismatch"
    )
    assert evaluate_price_comparison(20, quote, require_security_unit_evidence=True).reason == "missing_evidence"
    assert evaluate_price_comparison(20, quote).percent == 80
