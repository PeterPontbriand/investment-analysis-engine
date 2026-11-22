"""A run whose provider has nothing for the ticker is ``unavailable``, for every declared strategy.

Each test iterates the declared strategies. Yahoo Finance returns an empty history, and SEC EDGAR either does not list
the ticker or lists it under a CIK whose company documents answer 404; both are ``no_data`` failures of the first input
the strategy reads. A failure while loading SEC's ticker list keeps its own kind. No network or model call is made.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from contextlib import ExitStack
from typing import Any
from unittest.mock import patch

import pandas as pd
import pytest
from typer.testing import CliRunner

from investment_analysis_engine.analysis.run_models import RunOutcome
from investment_analysis_engine.cli import app
from investment_analysis_engine.config import ProjectSettings
from investment_analysis_engine.core.analysis_status import CalculationStatus
from investment_analysis_engine.core.provider_failure_kind import ProviderFailureKind
from investment_analysis_engine.data.financial.facts import FinancialProviderError
from investment_analysis_engine.data.sec_edgar.financial_facts import SEC_PROVIDER_ID, SecEdgarFinancialFactsAdapter
from investment_analysis_engine.strategy_wiring import STRATEGIES, StrategyDescriptor
from investment_analysis_engine.workspace.capture import ExecutionCapture
from tests._sec_ticker_file import exchange_file

pytestmark = pytest.mark.usefixtures("isolated_cli_settings", "stub_yahoo_identity_metadata")

_TICKER = "ZZZZQ"
_REQUIRED_OPTIONS = {"graham-growth": ("--expected-growth", "5", "--aaa-yield", "4.5")}
_SEC_STRATEGIES = tuple(item for item in STRATEGIES if item.alias != "momentum")

Fetcher = Callable[..., object]


def _fetcher_of(listed: bool, ticker_list_failure: ProviderFailureKind | None = None) -> Fetcher:
    """Return an SEC fetcher: a ticker list that holds the ticker or none, whose company documents answer 404."""

    def fetch(url: str, **kwargs: Any) -> object:
        if "company_tickers" in url:
            if ticker_list_failure is not None:
                raise FinancialProviderError("SEC is down.", kind=ticker_list_failure, provider_id=SEC_PROVIDER_ID)
            rows = {"0": {"cik_str": 1234567, "ticker": _TICKER, "title": "Zed Corp"}} if listed else {}
            return exchange_file(rows)
        raise FinancialProviderError("404", kind=kwargs["not_found"], provider_id=SEC_PROVIDER_ID)

    return fetch


def _invoke(descriptor: StrategyDescriptor) -> dict[str, Any]:
    """Run the strategy's direct command; the document gains the exit code and the run record's failure code."""
    arguments = [descriptor.alias, _TICKER, "--no-cache", "--json", *_REQUIRED_OPTIONS.get(descriptor.alias, ())]
    captures: list[ExecutionCapture] = []
    original = ExecutionCapture.__init__

    def spy(self: ExecutionCapture, *args: Any, **kwargs: Any) -> None:
        original(self, *args, **kwargs)
        captures.append(self)

    with patch.object(ExecutionCapture, "__init__", spy):
        result = CliRunner().invoke(app, arguments)
    document: dict[str, Any] = json.loads(result.stdout)
    document["exit_code"] = result.exit_code
    document["captured_failure_reason_codes"] = [capture.failure_reason_code for capture in captures]
    document["reason"] = document.get("reason", document.get("classification_reason"))
    document["reason_code"] = document.get("reason_code", document.get("classification_reason_code"))
    return document


@pytest.fixture
def sec_fetcher(
    monkeypatch: pytest.MonkeyPatch, isolated_cli_settings: ProjectSettings
) -> Iterator[Callable[[Fetcher], None]]:
    """Return a function that installs an SEC fetcher, with Yahoo Finance answering an empty history."""
    monkeypatch.setattr(isolated_cli_settings, "sec_user_agent", "Test Suite test@example.com")
    with ExitStack() as stack:
        stack.enter_context(
            patch("investment_analysis_engine.data.yfinance.client.yf.download", return_value=pd.DataFrame())
        )

        def install(fetcher: Fetcher) -> None:
            stack.enter_context(
                patch.dict(SecEdgarFinancialFactsAdapter.__init__.__kwdefaults__, {"json_fetcher": fetcher})
            )

        yield install


def _assert_unavailable_for_no_data(document: dict[str, Any]) -> None:
    assert document["status"] == "input_unavailable", document["reason"]
    assert document["provider_failure"] is not None, (document["reason"], document["reason_code"])
    assert document["provider_failure"]["reason_code"] == "provider_no_data"
    assert {item["kind"] for item in document["provider_failure"]["inputs"]} == {"no_data"}
    assert RunOutcome.from_status(CalculationStatus(document["status"])) is RunOutcome.UNAVAILABLE
    assert document["exit_code"] == 1
    assert document["captured_failure_reason_codes"] == [None]


@pytest.mark.parametrize("descriptor", STRATEGIES, ids=lambda item: item.alias)
def test_a_ticker_absent_from_the_provider_is_an_unavailable_run_with_a_no_data_failure(
    descriptor: StrategyDescriptor, sec_fetcher: Callable[[Fetcher], None]
) -> None:
    sec_fetcher(_fetcher_of(listed=False))

    document = _invoke(descriptor)

    _assert_unavailable_for_no_data(document)
    assert document["reason_code"] == "provider_no_data"


def test_the_messages_name_the_provider_and_never_say_the_ticker_does_not_exist(
    sec_fetcher: Callable[[Fetcher], None],
) -> None:
    sec_fetcher(_fetcher_of(listed=False))
    messages = {item.alias: _invoke(item)["reason"] for item in STRATEGIES}

    assert messages["momentum"] == f"Yahoo Finance returned no price history for {_TICKER}."
    for descriptor in _SEC_STRATEGIES:
        assert messages[descriptor.alias].startswith(f"SEC EDGAR's ticker list does not include {_TICKER}")
    assert not any("exist" in message for message in messages.values())


@pytest.mark.parametrize("descriptor", _SEC_STRATEGIES, ids=lambda item: item.alias)
def test_a_listed_ticker_whose_company_documents_answer_404_is_an_unavailable_run_with_a_no_data_failure(
    descriptor: StrategyDescriptor, sec_fetcher: Callable[[Fetcher], None]
) -> None:
    sec_fetcher(_fetcher_of(listed=True))

    document = _invoke(descriptor)

    _assert_unavailable_for_no_data(document)
    assert document["reason_code"] == "provider_no_data"
    assert document["reason"].startswith("SEC EDGAR returned no ")


@pytest.mark.parametrize("descriptor", _SEC_STRATEGIES, ids=lambda item: item.alias)
def test_a_failure_while_loading_the_ticker_list_keeps_its_own_kind_and_is_a_provider_error(
    descriptor: StrategyDescriptor, sec_fetcher: Callable[[Fetcher], None]
) -> None:
    sec_fetcher(_fetcher_of(listed=False, ticker_list_failure=ProviderFailureKind.UNREACHABLE))

    document = _invoke(descriptor)

    assert document["status"] == "provider_error", document["reason"]
    assert document["provider_failure"]["reason_code"] == "provider_unreachable"
    assert {item["kind"] for item in document["provider_failure"]["inputs"]} == {"unreachable"}
