"""Parameter handling: unknown, repeated and malformed values, the defaults and the runs-list checks."""

from uuid import uuid4

import pytest

from investment_analysis_engine.analysis.run_models import RunOutcome
from investment_analysis_engine.application.runs import RunQueryNames, build_run_query, declared_method_id
from investment_analysis_engine.config import ProjectSettings
from investment_analysis_engine.core.operator_errors import InvalidParameterError
from investment_analysis_engine.strategy_wiring import STRATEGIES
from investment_analysis_engine.workspace.runs import RunQuery
from tests.api._support import AUTH, client_for, runs_by_alias, store

_RUN_ID = uuid4()


def _rejected(response_json: dict[str, object], *, parameters: list[str]) -> None:
    assert response_json["reason_code"] == "invalid_parameter"
    assert response_json["status"] == "error"
    assert response_json["parameters"] == parameters


@pytest.mark.parametrize(
    ("path", "query", "parameter"),
    [
        ("/v1/runs", [("colour", "red")], "colour"),
        ("/v1/info", [("limit", "1")], "limit"),
        ("/v1/strategies", [("x", "1")], "x"),
        (f"/v1/runs/{_RUN_ID}", [("mode", "concise")], "mode"),
        (f"/v1/runs/{_RUN_ID}/text", [("mode", "concise"), ("extra", "1")], "extra"),
        ("/v1/runs", [("", "1")], "query"),
        ("/v1/runs", [("limit", "1"), ("limit", "2")], "limit"),
        ("/v1/runs", [("ticker", "A"), ("ticker", "B")], "ticker"),
        (f"/v1/runs/{_RUN_ID}/text", [("mode", "concise"), ("mode", "details")], "mode"),
    ],
)
def test_an_unknown_or_repeated_query_parameter_is_invalid_and_named(
    path: str, query: list[tuple[str, str]], parameter: str, isolated_cli_settings: ProjectSettings
) -> None:
    with client_for(isolated_cli_settings) as client:
        response = client.get(path, params=query, headers=AUTH)
    assert response.status_code == 400
    _rejected(response.json(), parameters=[parameter])


@pytest.mark.parametrize(
    ("path", "name"),
    [
        ("/v1/runs/not-a-uuid", "analysis_run_id"),
        ("/v1/runs/not-a-uuid/text", "analysis_run_id"),
        ("/v1/watchlists/12345", "watchlist_id"),
        ("/v1/refreshes/abc/compare", "refresh_id"),
    ],
)
def test_a_malformed_id_in_a_path_is_invalid_not_missing(
    path: str, name: str, isolated_cli_settings: ProjectSettings
) -> None:
    with client_for(isolated_cli_settings) as client:
        response = client.get(path, params={"mode": "concise"} if path.endswith("/text") else None, headers=AUTH)
    assert response.status_code == 400
    _rejected(response.json(), parameters=[name])


@pytest.mark.parametrize(
    ("query", "parameter", "message"),
    [
        ({"ticker": " "}, "ticker", "ticker must not be empty."),
        ({"method_id": "nonsense"}, "method_id", None),
        ({"status": "great"}, "status", "status must be one of: completed, unavailable, not_applicable, failed."),
        ({"refresh_id": "abc"}, "refresh_id", None),
        ({"limit": "0"}, "limit", "limit must be between 1 and 100."),
        ({"limit": "101"}, "limit", "limit must be between 1 and 100."),
        ({"limit": "ten"}, "limit", "limit must be an integer."),
        ({"limit": "1.5"}, "limit", "limit must be an integer."),
        ({"offset": "-1"}, "offset", "offset must be 0 or greater."),
        ({"offset": "x"}, "offset", "offset must be an integer."),
    ],
)
def test_each_runs_list_check_rejects_with_the_api_spelling(
    query: dict[str, str], parameter: str, message: str | None, isolated_cli_settings: ProjectSettings
) -> None:
    with client_for(isolated_cli_settings) as client:
        response = client.get("/v1/runs", params=query, headers=AUTH)
    assert response.status_code == 400
    _rejected(response.json(), parameters=[parameter])
    if message is not None:
        assert response.json()["reason"] == message
    assert "--" not in response.json()["reason"].split("Use the full ID")[0]


def test_an_unknown_method_id_lists_the_declared_method_ids(isolated_cli_settings: ProjectSettings) -> None:
    with client_for(isolated_cli_settings) as client:
        response = client.get("/v1/runs", params={"method_id": "momentum"}, headers=AUTH)
    assert response.json()["reason"] == f"method_id must be one of: {', '.join(item.method_id for item in STRATEGIES)}."
    assert response.json()["parameters"] == ["method_id"]


def test_a_declared_method_id_is_accepted(isolated_cli_settings: ProjectSettings) -> None:
    with client_for(isolated_cli_settings) as client:
        response = client.get("/v1/runs", params={"method_id": STRATEGIES[0].method_id}, headers=AUTH)
    assert response.status_code == 200


def test_the_runs_list_defaults_to_twenty_rows_from_the_start(isolated_cli_settings: ProjectSettings) -> None:
    runs = list(runs_by_alias().values())
    store(isolated_cli_settings, *runs)
    with client_for(isolated_cli_settings) as client:
        default = client.get("/v1/runs", headers=AUTH).json()
        explicit = client.get("/v1/runs", params={"limit": 20, "offset": 0}, headers=AUTH).json()
    assert default == explicit
    assert len(default["items"]) == len(runs)


def test_mode_is_required_and_has_no_default(isolated_cli_settings: ProjectSettings) -> None:
    with client_for(isolated_cli_settings) as client:
        missing = client.get(f"/v1/runs/{_RUN_ID}/text", headers=AUTH)
        wrong = client.get(f"/v1/runs/{_RUN_ID}/text", params={"mode": "json"}, headers=AUTH)
    assert missing.status_code == 400
    _rejected(missing.json(), parameters=["mode"])
    assert missing.json()["reason"] == "mode is required."
    assert wrong.status_code == 400
    _rejected(wrong.json(), parameters=["mode"])
    assert wrong.json()["reason"] == "mode must be one of: concise, details, diagnostics."


_API_NAMES = RunQueryNames(
    ticker="ticker", method="method_id", status="status", refresh_id="refresh_id", limit="limit", offset="offset"
)


def _query(  # noqa: PLR0913
    *,
    ticker: str | None = None,
    method: str | None = None,
    status: str | None = None,
    refresh_id: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> RunQuery:
    return build_run_query(
        names=_API_NAMES,
        resolve_method=lambda value: declared_method_id(value, name="method_id"),
        ticker=ticker,
        method=method,
        status=status,
        refresh_id=refresh_id,
        limit=limit,
        offset=offset,
    )


def test_the_query_function_reports_the_first_rejected_parameter_in_the_order_the_command_checks_them() -> None:
    with pytest.raises(InvalidParameterError) as caught:
        _query(ticker=" ", method="nonsense", status="bad", limit=0, offset=-1)
    assert caught.value.parameters == ("ticker",)
    with pytest.raises(InvalidParameterError) as caught:
        _query(method="nonsense", status="bad", limit=0, offset=-1)
    assert caught.value.parameters == ("method_id",)
    with pytest.raises(InvalidParameterError) as caught:
        _query(status="bad", limit=0, offset=-1)
    assert caught.value.parameters == ("status",)
    with pytest.raises(InvalidParameterError) as caught:
        _query(refresh_id="x", limit=0, offset=-1)
    assert caught.value.parameters == ("refresh_id",)
    with pytest.raises(InvalidParameterError) as caught:
        _query(limit=0, offset=-1)
    assert caught.value.parameters == ("limit",)


def test_the_query_function_builds_a_normalized_query() -> None:
    refresh_id = uuid4()
    query = _query(
        ticker=" brk-b ", method=STRATEGIES[0].method_id, status="failed", refresh_id=str(refresh_id), limit=5, offset=2
    )
    assert query.ticker == "BRK-B"
    assert query.method_id == STRATEGIES[0].method_id
    assert query.status is RunOutcome.FAILED
    assert query.refresh_id == refresh_id
    assert (query.limit, query.offset) == (5, 2)
