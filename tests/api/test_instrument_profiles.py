"""The instrument profile endpoints, and the identity a run overview carries, in process."""

import threading

import pytest

from investment_analysis_engine.config import ProjectSettings
from investment_analysis_engine.core.failure_codes import PROVIDER_CODE_BY_KIND
from investment_analysis_engine.core.provider_failure_kind import ProviderFailureKind
from investment_analysis_engine.data.instrument_profile import profile_identity_resolution
from investment_analysis_engine.data.repositories.instrument_profiles import INSTRUMENT_PROFILE_SCHEMA_VERSION
from investment_analysis_engine.reporting.documents.shared_parts import security_identity_part
from investment_analysis_engine.strategy_wiring import STRATEGIES
from tests._instrument_profile_fakes import (
    OLD,
    FakeSec,
    FakeYahoo,
    profile_context,
    set_profile_version,
    store_profile,
    use_providers,
    use_yahoo_only,
)
from tests.api._support import AUTH, client_for, runs_by_alias, store
from tests.api.test_refresh_jobs import _ended, _entry, _job, _start
from tests.application._refresh_fakes import FakeRuns, Probe, fakes

_KEYS = [
    "schema_version",
    "ticker",
    "refreshed_at",
    "instrument_name",
    "listing_venue",
    "issuer_identifier",
    "instrument_identifier",
    "kind",
    "quote_currency",
    "provider_id",
]


def _no_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail any attempt to build a provider, which the read must never make."""

    def refuse(_context: object) -> object:
        raise AssertionError("The read contacted a provider.")

    monkeypatch.setattr(
        "investment_analysis_engine.application.instrument_profiles.build_sec_production_provider", refuse
    )
    monkeypatch.setattr("investment_analysis_engine.application.instrument_profiles.YFinanceClient", refuse)


def test_the_read_serves_an_expired_stored_profile_and_contacts_no_provider(
    isolated_cli_settings: ProjectSettings, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = profile_context(isolated_cli_settings)
    store_profile(context, refreshed_at=OLD)
    _no_provider(monkeypatch)

    with client_for(context.settings) as client:
        response = client.get("/v1/instrument-profiles/ko", headers=AUTH)

    assert response.status_code == 200
    document = response.json()
    assert list(document) == _KEYS
    assert document == {
        "schema_version": 1,
        "ticker": "KO",
        "refreshed_at": OLD.isoformat(),
        "instrument_name": "Coca-Cola Co",
        "listing_venue": None,
        "issuer_identifier": "0000021344",
        "instrument_identifier": None,
        "kind": "equity",
        "quote_currency": "USD",
        "provider_id": "sec_edgar",
    }


def test_the_read_of_a_ticker_with_no_profile_is_a_404_with_its_own_code(
    isolated_cli_settings: ProjectSettings,
) -> None:
    with client_for(isolated_cli_settings) as client:
        response = client.get("/v1/instrument-profiles/KO", headers=AUTH)

    assert response.status_code == 404
    body = response.json()
    assert (body["reason_code"], body["reason"]) == (
        "instrument_profile_not_found",
        "No instrument profile is stored for KO.",
    )


def test_a_profile_stored_under_another_payload_version_is_a_404(isolated_cli_settings: ProjectSettings) -> None:
    context = profile_context(isolated_cli_settings)
    store_profile(context, refreshed_at=OLD)
    set_profile_version(context, INSTRUMENT_PROFILE_SCHEMA_VERSION - 1)

    with client_for(context.settings) as client:
        response = client.get("/v1/instrument-profiles/KO", headers=AUTH)

    assert (response.status_code, response.json()["reason_code"]) == (404, "instrument_profile_not_found")


@pytest.mark.parametrize("method", ["get", "post"])
def test_a_blank_ticker_is_an_invalid_parameter(isolated_cli_settings: ProjectSettings, method: str) -> None:
    path = "/v1/instrument-profiles/%20" + ("/lookup" if method == "post" else "")

    with client_for(isolated_cli_settings) as client:
        response = getattr(client, method)(path, headers=AUTH)

    assert response.status_code == 400
    assert (response.json()["reason_code"], response.json()["parameters"]) == ("invalid_parameter", ["ticker"])


def test_a_lookup_stores_the_profile_and_answers_the_document_the_read_then_serves(
    isolated_cli_settings: ProjectSettings, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = profile_context(isolated_cli_settings)
    sec = FakeSec()
    use_providers(monkeypatch, sec, FakeYahoo())

    with client_for(context.settings) as client:
        looked_up = client.post("/v1/instrument-profiles/ko/lookup", headers=AUTH)
        read = client.get("/v1/instrument-profiles/KO", headers=AUTH)

    assert looked_up.status_code == 200
    assert list(looked_up.json()) == _KEYS
    assert looked_up.json() == read.json()
    assert (looked_up.json()["instrument_name"], looked_up.json()["quote_currency"]) == ("Coca-Cola Co", "USD")
    assert sec.calls == 1


def test_a_lookup_without_an_identity_anchor_is_served_and_not_stored(
    isolated_cli_settings: ProjectSettings, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = profile_context(isolated_cli_settings)
    use_providers(monkeypatch, FakeSec(identity=False), FakeYahoo())

    with client_for(context.settings) as client:
        looked_up = client.post("/v1/instrument-profiles/KO/lookup", headers=AUTH)
        read = client.get("/v1/instrument-profiles/KO", headers=AUTH)

    assert looked_up.status_code == 200
    assert (looked_up.json()["provider_id"], looked_up.json()["issuer_identifier"]) == ("yfinance", None)
    assert read.status_code == 404


_PROVIDER_STATUS = {
    ProviderFailureKind.NO_DATA: 404,
    ProviderFailureKind.UNREACHABLE: 502,
    ProviderFailureKind.UNEXPECTED_RESPONSE: 502,
    ProviderFailureKind.RATE_LIMITED: 429,
}
"""The status each kind of provider failure answers with, written out so a change to the table fails a test."""


@pytest.mark.parametrize("kind", list(ProviderFailureKind))
def test_a_lookup_that_fails_on_a_provider_answers_its_code_and_the_status_of_that_code(
    isolated_cli_settings: ProjectSettings, monkeypatch: pytest.MonkeyPatch, kind: ProviderFailureKind
) -> None:
    context = profile_context(isolated_cli_settings)
    use_providers(monkeypatch, FakeSec(failure=kind), FakeYahoo(identity=False))

    with client_for(context.settings) as client:
        response = client.post("/v1/instrument-profiles/KO/lookup", headers=AUTH)

    body = response.json()
    assert body["reason_code"] == PROVIDER_CODE_BY_KIND[kind].value
    assert response.status_code == _PROVIDER_STATUS[kind]
    assert body["provider_failure"]["inputs"][0]["provider_id"] == "sec_edgar"


def test_a_lookup_in_which_no_provider_identifies_the_ticker_is_provider_no_data(
    isolated_cli_settings: ProjectSettings, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = profile_context(isolated_cli_settings)
    use_providers(monkeypatch, FakeSec(identity=False), FakeYahoo(identity=False))

    with client_for(context.settings) as client:
        response = client.post("/v1/instrument-profiles/ZZZZ/lookup", headers=AUTH)

    body = response.json()
    assert response.status_code == 404
    assert (body["reason_code"], body["reason"]) == (
        "provider_no_data",
        "Unable to look up ZZZZ: Yahoo Finance returned no data for it.",
    )


def test_a_lookup_without_an_sec_identity_answers_yahoo_alone_and_the_read_is_still_404(
    isolated_cli_settings: ProjectSettings, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = profile_context(isolated_cli_settings, sec_identity=False)
    use_yahoo_only(monkeypatch, FakeYahoo())

    with client_for(context.settings) as client:
        looked_up = client.post("/v1/instrument-profiles/KO/lookup", headers=AUTH)
        read = client.get("/v1/instrument-profiles/KO", headers=AUTH)

    assert looked_up.status_code == 200
    body = looked_up.json()
    assert (body["provider_id"], body["instrument_name"], body["kind"], body["issuer_identifier"]) == (
        "yfinance",
        "The Coca-Cola Company",
        "equity",
        None,
    )
    assert read.status_code == 404


def test_a_lookup_without_an_sec_identity_in_which_yahoo_identifies_nothing_is_provider_no_data(
    isolated_cli_settings: ProjectSettings, monkeypatch: pytest.MonkeyPatch
) -> None:
    use_yahoo_only(monkeypatch, FakeYahoo(identity=False))

    with client_for(profile_context(isolated_cli_settings, sec_identity=False).settings) as client:
        response = client.post("/v1/instrument-profiles/ZZZZ/lookup", headers=AUTH)

    assert response.json()["reason_code"] == "provider_no_data"


def test_a_lookup_without_an_sec_identity_answers_an_existing_stored_profile_unchanged(
    isolated_cli_settings: ProjectSettings, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = profile_context(isolated_cli_settings, sec_identity=False)
    store_profile(context, refreshed_at=OLD)
    use_yahoo_only(monkeypatch, FakeYahoo())

    with client_for(context.settings) as client:
        looked_up = client.post("/v1/instrument-profiles/KO/lookup", headers=AUTH)
        read = client.get("/v1/instrument-profiles/KO", headers=AUTH)

    assert looked_up.json() == read.json()
    assert looked_up.json()["refreshed_at"] == OLD.isoformat()


def test_the_endpoints_accept_only_their_methods(isolated_cli_settings: ProjectSettings) -> None:
    with client_for(isolated_cli_settings) as client:
        assert client.post("/v1/instrument-profiles/KO", headers=AUTH).status_code == 405
        assert client.get("/v1/instrument-profiles/KO/lookup", headers=AUTH).status_code == 405


@pytest.mark.parametrize("descriptor", STRATEGIES, ids=lambda item: item.alias)
def test_a_run_overview_carries_the_identity_the_run_retained(
    descriptor: object, isolated_cli_settings: ProjectSettings
) -> None:
    run = runs_by_alias()[descriptor.alias]  # type: ignore[attr-defined]
    store(isolated_cli_settings, run)
    profile = run.instrument_profile
    expected = security_identity_part(run.ticker, None if profile is None else profile_identity_resolution(profile))

    with client_for(isolated_cli_settings) as client:
        response = client.get(f"/v1/runs/{run.analysis_run_id}/overview", headers=AUTH)

    assert response.json()["security_identity"] == expected.model_dump(mode="json")


def test_the_identity_of_a_run_is_never_relabelled_with_the_tickers_current_profile(
    isolated_cli_settings: ProjectSettings,
) -> None:
    run = runs_by_alias()[STRATEGIES[0].alias]
    context = profile_context(isolated_cli_settings)
    store(context.settings, run)
    store_profile(context, refreshed_at=OLD, ticker=run.ticker)

    with client_for(context.settings) as client:
        overview = client.get(f"/v1/runs/{run.analysis_run_id}/overview", headers=AUTH).json()
        current = client.get(f"/v1/instrument-profiles/{run.ticker}", headers=AUTH).json()

    assert current["instrument_name"] == "Coca-Cola Co"
    assert overview["security_identity"]["instrument_name"] != "Coca-Cola Co"


def test_a_lookup_succeeds_while_a_refresh_job_runs(
    isolated_cli_settings: ProjectSettings, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = profile_context(isolated_cli_settings)
    use_providers(monkeypatch, FakeSec(), FakeYahoo())
    gate, entered = threading.Event(), threading.Event()
    body = {"entries": [_entry(STRATEGIES[0], "KO")], "save": False}

    with client_for(context.settings) as client, fakes(Probe(), FakeRuns(gate=gate, entered=entered)):
        refresh_id = _start(client, body).json()["refresh_id"]
        assert entered.wait(30)
        running = _job(client, refresh_id).json()["state"]
        looked_up = client.post("/v1/instrument-profiles/KO/lookup", headers=AUTH)
        gate.set()
        _ended(client, refresh_id)

    assert running == "running"
    assert looked_up.status_code == 200
    assert looked_up.json()["instrument_name"] == "Coca-Cola Co"
