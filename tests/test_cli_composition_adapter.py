"""The shared SEC adapter builder in the CLI composition, and the provider builder that calls it.

Piotroski needs the adapter itself (it is the as-filed SIC source) as well as the provider composed from it, so the
construction of the adapter is one function that ``build_sec_production_provider`` calls and Piotroski calls beside it.
"""

from pathlib import Path
from typing import Any

import pytest

from investment_analysis_engine import cli_composition
from investment_analysis_engine.config import settings
from investment_analysis_engine.core.operator_errors import AnalysisConfigurationError
from investment_analysis_engine.data.financial.production import ProductionFinancialFactsProvider
from investment_analysis_engine.data.sec_edgar.financial_facts import SecEdgarFinancialFactsAdapter
from investment_analysis_engine.strategies.fcf_growth import cli as fcf_growth_cli

NOT_CONFIGURED = (
    "SEC EDGAR access is not configured. "
    'Set SEC_USER_AGENT to a declared identity such as "Your Name your-email@example.com" and retry.'
)


class _Recorder:
    """Stands in for the adapter and records how the builder constructed it."""

    given: dict[str, Any] = {}

    def __init__(self, **keywords: Any) -> None:
        _Recorder.given = dict(keywords)


@pytest.fixture
def configured(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "providers").mkdir()
    (tmp_path / "providers" / "sec_edgar.toml").write_text("[ticker_overrides]\nXOM = 34088\n", encoding="utf-8")
    monkeypatch.setattr(cli_composition, "_settings_folder", lambda: tmp_path)
    monkeypatch.setattr(settings, "sec_user_agent", "Fixture Tester fixture@example.com")


@pytest.mark.usefixtures("configured")
def test_the_adapter_builder_hands_the_identity_and_the_ticker_overrides_to_the_adapter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(cli_composition, "SecEdgarFinancialFactsAdapter", _Recorder)
    cli_composition.build_sec_edgar_adapter()
    assert _Recorder.given == {
        "user_agent": "Fixture Tester fixture@example.com",
        "ticker_overrides": {"XOM": "0000034088"},
    }


@pytest.mark.parametrize("identity", [None, "", "   "])
def test_both_builders_refuse_without_a_declared_identity_with_the_same_message(
    identity: str | None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "sec_user_agent", identity)
    for build in (cli_composition.build_sec_edgar_adapter, cli_composition.build_sec_production_provider):
        with pytest.raises(AnalysisConfigurationError) as raised:
            build()
        assert str(raised.value) == NOT_CONFIGURED


@pytest.mark.usefixtures("configured")
def test_the_provider_builder_wraps_the_adapter_the_shared_builder_made(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = SecEdgarFinancialFactsAdapter(user_agent="Synthetic test")
    calls: list[str] = []

    def build() -> SecEdgarFinancialFactsAdapter:
        calls.append("built")
        return adapter

    monkeypatch.setattr(cli_composition, "build_sec_edgar_adapter", build)
    provider = cli_composition.build_sec_production_provider()
    assert calls == ["built"]
    assert isinstance(provider, ProductionFinancialFactsProvider)
    assert provider._providers["sec_edgar"] is adapter


@pytest.mark.usefixtures("configured")
def test_the_adapter_builder_makes_a_real_adapter_that_the_provider_builder_does_not_share() -> None:
    first = cli_composition.build_sec_edgar_adapter()
    assert isinstance(first, SecEdgarFinancialFactsAdapter)
    provider = cli_composition.build_sec_production_provider()
    assert provider._providers["sec_edgar"] is not first


def test_fcf_growth_still_composes_through_the_provider_builder_alone() -> None:
    assert vars(fcf_growth_cli)["build_sec_production_provider"] is cli_composition.build_sec_production_provider
    assert "build_sec_edgar_adapter" not in vars(fcf_growth_cli)
