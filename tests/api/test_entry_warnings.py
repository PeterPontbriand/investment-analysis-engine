"""The watchlist entries endpoint answers the entries-added document: the watchlist and a warning for each ticker."""

from unittest.mock import MagicMock

import pytest

from investment_analysis_engine.application import entry_check
from investment_analysis_engine.config import ProjectSettings
from investment_analysis_engine.core.provider_failure_kind import ProviderFailureKind
from investment_analysis_engine.data.base_client import DataFetchError
from investment_analysis_engine.strategy_wiring import STRATEGIES
from tests.api._support import AUTH, client_for
from tests.api.test_actions import _add, _create

_DESCRIPTOR = STRATEGIES[0]


def _lookup(monkeypatch: pytest.MonkeyPatch, failures: dict[str, ProviderFailureKind]) -> MagicMock:
    def answer(_context: object, ticker: str) -> None:
        if ticker in failures:
            raise DataFetchError("failed", kind=failures[ticker], provider_id="yfinance")

    lookup = MagicMock(side_effect=answer)
    monkeypatch.setattr(entry_check, "lookup_instrument_profile", lookup)
    return lookup


def test_every_ticker_confirmed_answers_an_empty_warnings_list(isolated_cli_settings: ProjectSettings) -> None:
    with client_for(isolated_cli_settings) as client:
        created = _create(client)
        response = _add(client, created["watchlist_id"], _DESCRIPTOR, "KO")

    body = response.json()
    assert response.status_code == 200
    assert list(body) == ["schema_version", "watchlist", "warnings"]
    assert (body["schema_version"], body["warnings"]) == (1, [])
    assert [entry["ticker"] for entry in body["watchlist"]["entries"]] == ["KO"]


def test_an_unconfirmed_ticker_is_added_and_warned_of_with_the_shape_of_a_rule_error(
    isolated_cli_settings: ProjectSettings, monkeypatch: pytest.MonkeyPatch
) -> None:
    lookup = _lookup(
        monkeypatch,
        {"KOO": ProviderFailureKind.NO_DATA, "MSFT": ProviderFailureKind.UNREACHABLE},
    )
    with client_for(isolated_cli_settings) as client:
        created = _create(client)
        response = _add(client, created["watchlist_id"], _DESCRIPTOR, "ko", "koo", "msft", "pg")
        shown = client.get(f"/v1/watchlists/{created['watchlist_id']}", headers=AUTH).json()

    body = response.json()
    assert response.status_code == 200
    assert [entry["ticker"] for entry in shown["entries"]] == ["KO", "KOO", "MSFT", "PG"]
    assert body["watchlist"] == shown
    unrecognized, unreachable, skipped = body["warnings"]
    assert unrecognized == {
        "ticker": "KOO",
        "code": "ticker_not_recognized",
        "reason_code": None,
        "arguments": {"ticker": "KOO"},
        "message": "No data provider recognizes KOO. Check the ticker, and remove the entry if it is wrong.",
        "template": "No data provider recognizes {ticker}. Check the ticker, and remove the entry if it is wrong.",
    }
    assert (unreachable["code"], unreachable["reason_code"]) == ("ticker_not_checked", "provider_unreachable")
    assert (skipped["ticker"], skipped["reason_code"], skipped["message"]) == (
        "PG",
        "provider_unreachable",
        "PG could not be checked, because the data providers could not be reached.",
    )
    for warning in body["warnings"]:
        assert warning["template"].replace("{ticker}", warning["ticker"]) == warning["message"]
    assert lookup.call_count == 3


def test_other_endpoints_keep_answering_the_watchlist_document(isolated_cli_settings: ProjectSettings) -> None:
    with client_for(isolated_cli_settings) as client:
        created = _create(client)
        shown = client.get(f"/v1/watchlists/{created['watchlist_id']}", headers=AUTH).json()

    assert "warnings" not in created
    assert "warnings" not in shown


def test_a_refused_add_asks_no_provider_and_answers_its_failure(
    isolated_cli_settings: ProjectSettings, monkeypatch: pytest.MonkeyPatch
) -> None:
    lookup = _lookup(monkeypatch, {})
    with client_for(isolated_cli_settings) as client:
        created = _create(client)
        response = _add(client, created["watchlist_id"], _DESCRIPTOR, "KO", "ko")

    assert response.status_code == 400
    assert lookup.call_count == 0


class _UnlistedSec:
    """Stands in for the SEC adapter whose ticker list lacks every ticker."""

    def lists_ticker(self, ticker: str) -> bool:
        del ticker
        return False


def test_an_unlisted_ticker_for_a_strategy_that_reads_sec_filings_is_added_with_the_sec_list_warning(
    isolated_cli_settings: ProjectSettings, monkeypatch: pytest.MonkeyPatch
) -> None:
    _lookup(monkeypatch, {})
    monkeypatch.setattr(entry_check, "build_sec_edgar_adapter", lambda _context: _UnlistedSec())
    graham = next(item for item in STRATEGIES if item.alias == "graham-number")
    with client_for(isolated_cli_settings) as client:
        created = _create(client)
        response = _add(client, created["watchlist_id"], graham, "ntr.to")

    body = response.json()
    assert response.status_code == 200
    assert [entry["ticker"] for entry in body["watchlist"]["entries"]] == ["NTR.TO"]
    (warning,) = body["warnings"]
    assert warning["code"] == "ticker_not_in_sec_list"
    assert warning["reason_code"] is None
    assert warning["arguments"] == {"ticker": "NTR.TO", "strategies": "Graham Number"}
    assert (
        warning["template"].replace("{ticker}", "NTR.TO").replace("{strategies}", "Graham Number") == warning["message"]
    )
    assert warning["message"].startswith(
        "NTR.TO is not in SEC EDGAR's ticker list, so Graham Number will be unavailable"
    )
