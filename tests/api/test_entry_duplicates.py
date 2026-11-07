"""The watchlist entries endpoint refuses a duplicate under the one rule, as the command line does."""

import httpx2

from investment_analysis_engine.config import ProjectSettings
from investment_analysis_engine.strategy_wiring import STRATEGIES
from tests.api._support import AUTH, client_for
from tests.api.test_actions import _add, _create, _fields

_DESCRIPTOR = STRATEGIES[0]


def _refused(response: httpx2.Response) -> dict[str, object]:
    assert response.status_code == 400, response.text
    body: dict[str, object] = response.json()
    assert body["reason_code"] == "invalid_parameter"
    assert body["parameters"] == ["tickers"]
    return body


def test_a_repeat_within_one_request_is_a_400_and_nothing_is_written(isolated_cli_settings: ProjectSettings) -> None:
    with client_for(isolated_cli_settings) as client:
        watchlist = _create(client)
        refused = _add(client, watchlist["watchlist_id"], _DESCRIPTOR, "KO", "PG", " ko")
        shown = client.get(f"/v1/watchlists/{watchlist['watchlist_id']}", headers=AUTH).json()

    body = _refused(refused)
    assert body["reason"] == (
        f"tickers must not duplicate an entry: KO is already listed for {_DESCRIPTOR.method_id} with an equal "
        "selection earlier in this request."
    )
    assert body["errors"][0]["rule"] == "entries.duplicate"  # type: ignore[index]
    assert body["errors"][0]["arguments"] == {  # type: ignore[index]
        "ticker": "KO",
        "method_id": _DESCRIPTOR.method_id,
        "where": "earlier in this request",
    }
    assert shown["entries"] == []


def test_a_repeat_of_a_stored_entry_is_a_400_and_another_selection_is_accepted(
    isolated_cli_settings: ProjectSettings,
) -> None:
    with client_for(isolated_cli_settings) as client:
        watchlist = _create(client)
        assert _add(client, watchlist["watchlist_id"], _DESCRIPTOR, "KO").status_code == 200
        refused = _add(client, watchlist["watchlist_id"], _DESCRIPTOR, "PG", "KO")
        other = client.post(
            f"/v1/watchlists/{watchlist['watchlist_id']}/entries",
            json={
                "method_id": _DESCRIPTOR.method_id,
                "tickers": ["KO"],
                "selection": _fields(_DESCRIPTOR) | {"rsi_period": 21},
            },
            headers=AUTH,
        )

    body = _refused(refused)
    assert str(body["reason"]).endswith("with an equal selection in the watchlist.")
    assert other.status_code == 200
    assert [entry["ticker"] for entry in other.json()["entries"]] == ["KO", "KO"]
