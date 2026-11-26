"""Each strategy says whether a selection reads SEC EDGAR, and a run agrees with it.

For every strategy and each selection case, the strategy's declared predicate is compared with a run through its
analyzer. SEC EDGAR's ticker list lacks the ticker and Yahoo Finance answers with no history. A selection the predicate
says reads SEC EDGAR stops with ``provider_no_data`` and the message that names SEC's ticker list. A selection it says
does not is not stopped by the unlisted ticker. No network or model call is made.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from contextlib import ExitStack
from dataclasses import dataclass
from typing import Any
from unittest.mock import patch

import pandas as pd
import pytest
from typer.testing import CliRunner

from investment_analysis_engine.cli import app
from investment_analysis_engine.config import ProjectSettings
from investment_analysis_engine.core.provider_failure_kind import ProviderFailureKind
from investment_analysis_engine.core.strategy_errors import UndeclaredStrategyError
from investment_analysis_engine.data.financial.facts import FinancialProviderError
from investment_analysis_engine.data.sec_edgar.financial_facts import SEC_PROVIDER_ID, SecEdgarFinancialFactsAdapter
from investment_analysis_engine.strategies.fcf_growth.selection import FCFGrowthSelection
from investment_analysis_engine.strategies.graham_growth.selection import GrahamGrowthSelection
from investment_analysis_engine.strategies.graham_number.selection import GrahamNumberSelection
from investment_analysis_engine.strategies.momentum.selection import MomentumSelection
from investment_analysis_engine.strategies.piotroski.selection import PiotroskiSelection
from investment_analysis_engine.strategy_wiring import STRATEGIES, sec_edgar_strategy_label
from investment_analysis_engine.workspace.strategy_types import SelectionMember
from tests._sec_ticker_file import exchange_file

pytestmark = pytest.mark.usefixtures("isolated_cli_settings", "stub_yahoo_identity_metadata")

_TICKER = "ZZZZQ"
_UNLISTED_MESSAGE = "SEC EDGAR's ticker list does not include"
_GROWTH_ARGUMENTS = ("--expected-growth", "5", "--aaa-yield", "4.5")


@dataclass(frozen=True)
class Case:
    """One selection of one strategy: its command-line arguments, its selection and what the predicate must say."""

    alias: str
    arguments: tuple[str, ...]
    selection: SelectionMember
    reads: bool

    def __str__(self) -> str:
        """Name the case by its strategy and arguments."""
        return f"{self.alias} {' '.join(self.arguments) or 'no options'}"


_MOMENTUM = MomentumSelection(short_window=20, long_window=50, rsi_period=14)


def _growth(eps: float | None, quote: float | None = None) -> GrahamGrowthSelection:
    return GrahamGrowthSelection(expected_growth=5.0, aaa_yield_override=4.5, eps_override=eps, quote_override=quote)


CASES = (
    Case("momentum", (), _MOMENTUM, reads=False),
    Case("graham-number", (), GrahamNumberSelection(), reads=True),
    Case("graham-number", ("--eps", "5"), GrahamNumberSelection(eps_override=5.0), reads=True),
    Case("graham-number", ("--bvps", "30"), GrahamNumberSelection(bvps_override=30.0), reads=True),
    Case(
        "graham-number",
        ("--eps", "5", "--bvps", "30", "--current-price", "100"),
        GrahamNumberSelection(eps_override=5.0, bvps_override=30.0, quote_override=100.0),
        reads=False,
    ),
    Case("graham-growth", _GROWTH_ARGUMENTS, _growth(None), reads=True),
    Case(
        "graham-growth", (*_GROWTH_ARGUMENTS, "--eps", "5", "--current-price", "100"), _growth(5.0, 100.0), reads=False
    ),
    Case("fcf-growth", (), FCFGrowthSelection(), reads=True),
    Case("piotroski", (), PiotroskiSelection(), reads=True),
)

Fetcher = Callable[..., object]


def _unlisted_fetcher(url: str, **kwargs: Any) -> object:
    """Return an SEC fetcher whose ticker list is empty; every other document answers 404."""
    if "company_tickers" in url:
        return exchange_file({})
    raise FinancialProviderError("404", kind=kwargs["not_found"], provider_id=SEC_PROVIDER_ID)


@pytest.fixture
def unlisted_ticker(monkeypatch: pytest.MonkeyPatch, isolated_cli_settings: ProjectSettings) -> Iterator[None]:
    """Install an SEC adapter whose ticker list lacks the ticker, with Yahoo Finance answering an empty history."""
    monkeypatch.setattr(isolated_cli_settings, "sec_user_agent", "Test Suite test@example.com")
    with ExitStack() as stack:
        stack.enter_context(
            patch("investment_analysis_engine.data.yfinance.client.yf.download", return_value=pd.DataFrame())
        )
        stack.enter_context(
            patch.dict(SecEdgarFinancialFactsAdapter.__init__.__kwdefaults__, {"json_fetcher": _unlisted_fetcher})
        )
        yield


def _run(case: Case) -> dict[str, Any]:
    """Run the strategy's direct command for the case and return its document."""
    result = CliRunner().invoke(app, [case.alias, _TICKER, "--no-cache", "--json", *case.arguments])
    document: dict[str, Any] = json.loads(result.stdout)
    document["reason"] = document.get("reason", document.get("classification_reason"))
    document["reason_code"] = document.get("reason_code", document.get("classification_reason_code"))
    return document


@pytest.mark.parametrize("case", CASES, ids=str)
def test_the_predicate_says_what_the_selection_reads(case: Case) -> None:
    descriptor = next(item for item in STRATEGIES if item.alias == case.alias)

    assert descriptor.behavior.reads_sec_edgar_for(case.selection) is case.reads
    assert sec_edgar_strategy_label(case.selection) == (descriptor.label if case.reads else None)


@pytest.mark.usefixtures("unlisted_ticker")
@pytest.mark.parametrize("case", CASES, ids=str)
def test_a_run_agrees_with_the_predicate_when_sec_edgars_list_lacks_the_ticker(case: Case) -> None:
    document = _run(case)

    stopped_by_the_list = document["reason"] is not None and document["reason"].startswith(_UNLISTED_MESSAGE)
    assert stopped_by_the_list is case.reads, document["reason"]
    if case.reads:
        assert document["status"] == "input_unavailable"
        assert document["reason_code"] == "provider_no_data"
        assert document["reason"].endswith("SEC EDGAR lists companies under their US ticker symbols only.")


def test_every_declared_strategy_has_a_case_for_each_answer_the_predicate_gives() -> None:
    answers = {(case.alias, case.reads) for case in CASES}

    for descriptor in STRATEGIES:
        assert any(alias == descriptor.alias for alias, _ in answers), descriptor.alias


def test_a_selection_of_no_declared_strategy_is_refused() -> None:
    class _Undeclared:
        analysis_id = "undeclared"
        method_id = "undeclared"

    with pytest.raises(UndeclaredStrategyError):
        sec_edgar_strategy_label(_Undeclared())  # type: ignore[arg-type]


def _adapter(
    rows: dict[str, dict[str, object]], overrides: dict[str, str] | None = None
) -> SecEdgarFinancialFactsAdapter:
    """Return an SEC adapter whose ticker file holds ``rows`` and whose other documents are never fetched."""

    def fetch(url: str, **kwargs: Any) -> object:
        del kwargs
        assert "company_tickers" in url, url
        return exchange_file(rows)

    return SecEdgarFinancialFactsAdapter(
        json_fetcher=fetch, user_agent="Test Suite test@example.com", ticker_overrides=overrides
    )


_LISTED = {"0": {"cik_str": 1234567, "ticker": "ZED", "title": "Zed Corp"}}


def test_a_ticker_the_file_lists_under_one_cik_is_listed() -> None:
    assert _adapter(_LISTED).lists_ticker("ZED") is True


def test_a_ticker_the_file_lists_under_several_ciks_is_listed() -> None:
    rows = {
        "0": {"cik_str": 1, "ticker": "ZED", "title": "Zed One"},
        "1": {"cik_str": 2, "ticker": "ZED", "title": "Zed Two"},
    }

    assert _adapter(rows).lists_ticker("ZED") is True


def test_a_ticker_with_an_override_is_listed_even_when_the_file_lacks_it() -> None:
    assert _adapter(_LISTED, {"NTR.TO": "0000000001"}).lists_ticker("NTR.TO") is True


def test_a_ticker_the_loaded_file_lacks_and_no_override_names_is_not_listed() -> None:
    assert _adapter(_LISTED).lists_ticker("NTR.TO") is False


def test_a_failure_loading_the_file_is_raised() -> None:
    def fetch(url: str, **kwargs: Any) -> object:
        del url, kwargs
        raise FinancialProviderError("down", kind=ProviderFailureKind.UNREACHABLE, provider_id=SEC_PROVIDER_ID)

    adapter = SecEdgarFinancialFactsAdapter(json_fetcher=fetch, user_agent="Test Suite test@example.com")

    with pytest.raises(FinancialProviderError):
        adapter.lists_ticker("ZED")


class _UnlistedSec:
    """Stands in for the SEC adapter whose ticker list lacks every ticker."""

    def lists_ticker(self, ticker: str) -> bool:
        del ticker
        return False


def test_the_command_line_prints_the_sec_list_warning_under_warnings_and_in_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from investment_analysis_engine.application import entry_check  # noqa: PLC0415

    monkeypatch.setattr(entry_check, "lookup_instrument_profile", lambda _context, _ticker: None)
    monkeypatch.setattr(entry_check, "build_sec_edgar_adapter", lambda _context: _UnlistedSec())
    runner = CliRunner()
    assert runner.invoke(app, ["watchlist", "create", "CA test"]).exit_code == 0

    text = runner.invoke(app, ["watchlist", "add-selection", "piotroski", "CA test", "SHOP.TO"])
    as_json = runner.invoke(app, ["watchlist", "add-selection", "graham-number", "CA test", "NTR.TO", "--json"])
    momentum = runner.invoke(app, ["watchlist", "add-selection", "momentum", "CA test", "BCE.TO", "--json"])

    lines = text.stdout.splitlines()
    assert text.exit_code == 0
    assert lines[-2] == "Warnings:"
    assert lines[-1].startswith("  SHOP.TO is not in SEC EDGAR's ticker list, so Piotroski F-Score will be unavailable")
    (warning,) = json.loads(as_json.stdout)["warnings"]
    assert (warning["code"], warning["reason_code"]) == ("ticker_not_in_sec_list", None)
    assert warning["arguments"] == {"ticker": "NTR.TO", "strategies": "Graham Number"}
    assert json.loads(momentum.stdout)["warnings"] == []
