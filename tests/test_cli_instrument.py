"""The ``instrument show`` command: the stored profile, the lookup, and the document, in process."""

import json

import pytest
from typer.testing import CliRunner

from investment_analysis_engine.application.context import ApplicationContext
from investment_analysis_engine.cli import app
from investment_analysis_engine.config import ProjectSettings
from tests._cli_helpers import normalize_cli_output
from tests._instrument_profile_fakes import (
    OLD,
    FakeSec,
    FakeYahoo,
    profile_context,
    store_profile,
    use_providers,
    use_yahoo_only,
)

runner = CliRunner()


@pytest.fixture
def context(isolated_cli_settings: ProjectSettings, monkeypatch: pytest.MonkeyPatch) -> ApplicationContext:
    """An application context over the isolated database, with an SEC identity set up and the command pointed at it."""
    context = profile_context(isolated_cli_settings)
    monkeypatch.setattr("investment_analysis_engine.cli_support.settings", context.settings)
    return context


def test_show_prints_the_stored_profile_as_text(context: ApplicationContext, monkeypatch: pytest.MonkeyPatch) -> None:
    store_profile(context, refreshed_at=OLD)
    sec = FakeSec()
    use_providers(monkeypatch, sec, FakeYahoo())

    result = runner.invoke(app, ["instrument", "show", "ko"])

    assert result.exit_code == 0, result.output
    assert result.stdout == (
        "Coca-Cola Co (KO)\n"
        "Kind: equity\n"
        "Listing venue: unknown\n"
        "Quote currency: USD\n"
        "Issuer identifier: 0000021344\n"
        "Instrument identifier: unknown\n"
        "Identity from: SEC EDGAR\n"
        f"Last checked: {OLD.isoformat()}\n"
    )
    assert sec.calls == 0, "The command asked no provider."


def test_show_json_prints_the_one_document(context: ApplicationContext) -> None:
    store_profile(context, refreshed_at=OLD)

    result = runner.invoke(app, ["instrument", "show", "KO", "--json"])

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {
        "schema_version": 2,
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
    assert result.stdout.count("\n") == 1


@pytest.mark.usefixtures("context")
def test_show_without_a_stored_profile_fails_in_text_and_in_json() -> None:
    text = runner.invoke(app, ["instrument", "show", "KO"])
    document = runner.invoke(app, ["instrument", "show", "KO", "--json"])

    assert text.exit_code == 1
    assert "No instrument profile is stored for KO." in text.output
    assert document.exit_code == 1
    failure = json.loads(document.stdout)
    assert (failure["reason_code"], failure["reason"]) == (
        "instrument_profile_not_found",
        "No instrument profile is stored for KO.",
    )


@pytest.mark.usefixtures("context")
def test_show_with_lookup_asks_the_providers_stores_the_profile_and_prints_it(monkeypatch: pytest.MonkeyPatch) -> None:
    sec = FakeSec()
    use_providers(monkeypatch, sec, FakeYahoo())

    looked_up = runner.invoke(app, ["instrument", "show", "KO", "--lookup", "--json"])
    stored = runner.invoke(app, ["instrument", "show", "KO", "--json"])

    assert looked_up.exit_code == stored.exit_code == 0, looked_up.output
    assert sec.calls == 1
    assert looked_up.stdout == stored.stdout
    assert json.loads(looked_up.stdout)["quote_currency"] == "USD"


@pytest.mark.usefixtures("context")
def test_show_with_lookup_prints_text_for_a_profile_without_an_anchor(monkeypatch: pytest.MonkeyPatch) -> None:
    use_providers(monkeypatch, FakeSec(identity=False), FakeYahoo())

    result = runner.invoke(app, ["instrument", "show", "KO", "--lookup"])

    assert result.exit_code == 0, result.output
    assert result.stdout.splitlines()[:5] == [
        "The Coca-Cola Company (KO)",
        "Kind: equity",
        "Listing venue: New York Stock Exchange (NYSE)",
        "Quote currency: USD",
        "Issuer identifier: unknown",
    ]
    assert "Identity from: Yahoo Finance" in result.stdout
    assert runner.invoke(app, ["instrument", "show", "KO"]).exit_code == 1


@pytest.mark.usefixtures("context")
def test_a_failed_lookup_exits_one_with_its_code(monkeypatch: pytest.MonkeyPatch) -> None:
    use_providers(monkeypatch, FakeSec(identity=False), FakeYahoo(identity=False))

    text = runner.invoke(app, ["instrument", "show", "ZZZZ", "--lookup"])
    document = runner.invoke(app, ["instrument", "show", "ZZZZ", "--lookup", "--json"])

    assert text.exit_code == document.exit_code == 1
    assert "Unable to look up ZZZZ: Yahoo Finance returned no data for it." in text.output
    assert json.loads(document.stdout)["reason_code"] == "provider_no_data"


@pytest.mark.usefixtures("context")
def test_a_blank_ticker_is_an_invalid_parameter() -> None:
    result = runner.invoke(app, ["instrument", "show", "  ", "--json"])

    assert result.exit_code == 1
    assert json.loads(result.stdout)["reason_code"] == "invalid_parameter"


def test_the_command_is_listed_in_the_help() -> None:
    result = runner.invoke(app, ["--help"])

    assert "instrument" in result.output
    assert "--lookup" in normalize_cli_output(runner.invoke(app, ["instrument", "show", "--help"]).output)


@pytest.fixture
def no_sec_context(isolated_cli_settings: ProjectSettings, monkeypatch: pytest.MonkeyPatch) -> ApplicationContext:
    """A context with no SEC identity set up, with the command pointed at it."""
    context = profile_context(isolated_cli_settings, sec_identity=False)
    monkeypatch.setattr("investment_analysis_engine.cli_support.settings", context.settings)
    return context


@pytest.mark.usefixtures("no_sec_context")
def test_lookup_without_an_sec_identity_answers_yahoo_alone_and_stores_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    use_yahoo_only(monkeypatch, FakeYahoo())

    looked_up = runner.invoke(app, ["instrument", "show", "KO", "--lookup"])

    assert looked_up.exit_code == 0, looked_up.output
    assert "The Coca-Cola Company (KO)" in looked_up.stdout
    assert "Identity from: Yahoo Finance" in looked_up.stdout
    assert runner.invoke(app, ["instrument", "show", "KO"]).exit_code == 1


@pytest.mark.usefixtures("no_sec_context")
def test_lookup_without_an_sec_identity_in_which_yahoo_identifies_nothing_is_no_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    use_yahoo_only(monkeypatch, FakeYahoo(identity=False))

    result = runner.invoke(app, ["instrument", "show", "ZZZZ", "--lookup", "--json"])

    assert result.exit_code == 1
    assert json.loads(result.stdout)["reason_code"] == "provider_no_data"


def test_lookup_without_an_sec_identity_answers_an_existing_stored_profile_unchanged(
    no_sec_context: ApplicationContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    store_profile(no_sec_context, refreshed_at=OLD)
    use_yahoo_only(monkeypatch, FakeYahoo())

    looked_up = runner.invoke(app, ["instrument", "show", "KO", "--lookup", "--json"])
    stored = runner.invoke(app, ["instrument", "show", "KO", "--json"])

    assert looked_up.exit_code == 0, looked_up.output
    assert looked_up.stdout == stored.stdout
    assert json.loads(looked_up.stdout)["refreshed_at"] == OLD.isoformat()
