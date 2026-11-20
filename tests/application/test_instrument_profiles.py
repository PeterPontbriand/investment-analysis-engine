"""The instrument profile operations: the stored read and the live lookup, with fake providers."""

from datetime import UTC, datetime, timedelta

import pytest

from investment_analysis_engine.application.context import ApplicationContext
from investment_analysis_engine.application.instrument_profiles import (
    InstrumentProfileNotFoundError,
    get_instrument_profile,
    lookup_instrument_profile,
)
from investment_analysis_engine.config import ProjectSettings
from investment_analysis_engine.core.failure_codes import PROVIDER_CODE_BY_KIND, FailureReasonCode
from investment_analysis_engine.core.operator_errors import AnalysisConfigurationError, InvalidParameterError
from investment_analysis_engine.core.provider_failure_kind import ProviderFailureKind
from investment_analysis_engine.data.base_client import DataFetchError
from investment_analysis_engine.data.repositories.instrument_profiles import INSTRUMENT_PROFILE_SCHEMA_VERSION
from tests._instrument_profile_fakes import (
    ANCHOR,
    OLD,
    FakeSec,
    FakeYahoo,
    profile_context,
    set_profile_version,
    store_profile,
    use_providers,
)


@pytest.fixture
def context(isolated_cli_settings: ProjectSettings) -> ApplicationContext:
    return profile_context(isolated_cli_settings)


def test_the_read_serves_an_expired_stored_profile_without_a_provider(
    context: ApplicationContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    sec, yahoo = FakeSec(), FakeYahoo()
    use_providers(monkeypatch, sec, yahoo)
    store_profile(context, refreshed_at=OLD)
    sec.calls = yahoo.calls = 0

    stored = get_instrument_profile(context, " ko ")

    assert stored.refreshed_at == OLD
    assert stored.profile.ticker == "KO"
    assert stored.profile.identity is not None
    assert (stored.profile.identity.instrument_name, stored.profile.quote_currency) == ("Coca-Cola Co", "USD")
    assert (sec.calls, yahoo.calls) == (0, 0)


def test_the_read_of_a_ticker_with_no_profile_is_not_found(context: ApplicationContext) -> None:
    with pytest.raises(InstrumentProfileNotFoundError) as error:
        get_instrument_profile(context, "ko")

    assert error.value.reason_code is FailureReasonCode.INSTRUMENT_PROFILE_NOT_FOUND
    assert str(error.value) == "No instrument profile is stored for KO."


def test_the_read_treats_a_profile_of_an_older_payload_version_as_absent(context: ApplicationContext) -> None:
    store_profile(context, refreshed_at=OLD)
    set_profile_version(context, INSTRUMENT_PROFILE_SCHEMA_VERSION - 1)

    with pytest.raises(InstrumentProfileNotFoundError):
        get_instrument_profile(context, "KO")


def test_the_read_serves_only_the_current_profile_of_a_reused_ticker(context: ApplicationContext) -> None:
    store_profile(context, refreshed_at=OLD, anchor="0000000001")
    store_profile(context, refreshed_at=OLD + timedelta(days=1))

    stored = get_instrument_profile(context, "KO")

    assert stored.profile.identity is not None
    assert stored.profile.identity.issuer_identifier == ANCHOR


@pytest.mark.parametrize("ticker", ["", "   "])
def test_a_blank_ticker_is_an_invalid_parameter_for_both_operations(context: ApplicationContext, ticker: str) -> None:
    for operation in (get_instrument_profile, lookup_instrument_profile):
        with pytest.raises(InvalidParameterError) as error:
            operation(context, ticker)

        assert error.value.parameters == ("ticker",)


def test_a_lookup_stores_an_anchored_profile_and_the_read_then_serves_it(
    context: ApplicationContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    sec, yahoo = FakeSec(), FakeYahoo()
    use_providers(monkeypatch, sec, yahoo)
    before = datetime.now(UTC)

    looked_up = lookup_instrument_profile(context, "ko")

    assert sec.calls == 1
    assert looked_up.refreshed_at >= before
    assert looked_up.profile.identity is not None
    assert looked_up.profile.identity.issuer_identifier == ANCHOR
    assert looked_up.profile.quote_currency == "USD"
    assert get_instrument_profile(context, "KO").profile.identity == looked_up.profile.identity


def test_a_lookup_reuses_a_fresh_stored_profile_without_a_provider(
    context: ApplicationContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    sec, yahoo = FakeSec(), FakeYahoo()
    use_providers(monkeypatch, sec, yahoo)
    first = lookup_instrument_profile(context, "KO")
    sec.calls = yahoo.calls = 0

    second = lookup_instrument_profile(context, "KO")

    assert (sec.calls, yahoo.calls) == (0, 0)
    assert second.refreshed_at == first.refreshed_at


def test_a_lookup_checks_an_expired_stored_profile_again(
    context: ApplicationContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    sec, yahoo = FakeSec(), FakeYahoo()
    use_providers(monkeypatch, sec, yahoo)
    store_profile(context, refreshed_at=OLD)
    sec.calls = 0

    looked_up = lookup_instrument_profile(context, "KO")

    assert sec.calls == 1
    assert looked_up.refreshed_at > OLD
    assert get_instrument_profile(context, "KO").refreshed_at == looked_up.refreshed_at


def test_a_lookup_without_an_identity_anchor_returns_the_profile_and_stores_nothing(
    context: ApplicationContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    use_providers(monkeypatch, FakeSec(identity=False), FakeYahoo())

    looked_up = lookup_instrument_profile(context, "KO")

    assert looked_up.profile.identity is not None
    assert looked_up.profile.identity.issuer_identifier is None
    assert looked_up.profile.identity.provider_id == "yfinance"
    assert looked_up.refreshed_at == looked_up.profile.identity.resolved_at
    with pytest.raises(InstrumentProfileNotFoundError):
        get_instrument_profile(context, "KO")


def test_a_lookup_keeps_the_stored_profile_when_no_anchor_can_be_confirmed(
    context: ApplicationContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    store_profile(context, refreshed_at=OLD)
    use_providers(monkeypatch, FakeSec(identity=False), FakeYahoo())

    looked_up = lookup_instrument_profile(context, "KO")

    assert looked_up.refreshed_at == OLD
    assert looked_up.profile.identity is not None
    assert looked_up.profile.identity.issuer_identifier == ANCHOR


def test_a_lookup_in_which_no_provider_identifies_the_ticker_is_no_data(
    context: ApplicationContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    use_providers(monkeypatch, FakeSec(identity=False), FakeYahoo(identity=False))

    with pytest.raises(DataFetchError) as error:
        lookup_instrument_profile(context, "ZZZZ")

    assert error.value.reason_code is FailureReasonCode.PROVIDER_NO_DATA
    assert (error.value.kind, error.value.provider_id) == (ProviderFailureKind.NO_DATA, "yfinance")
    assert str(error.value) == "Unable to look up ZZZZ: Yahoo Finance returned no data for it."


@pytest.mark.parametrize("kind", list(ProviderFailureKind))
def test_a_provider_failure_is_reported_under_its_own_code(
    context: ApplicationContext, monkeypatch: pytest.MonkeyPatch, kind: ProviderFailureKind
) -> None:
    use_providers(monkeypatch, FakeSec(failure=kind), FakeYahoo(identity=False))

    with pytest.raises(DataFetchError) as error:
        lookup_instrument_profile(context, "KO")

    assert error.value.reason_code is PROVIDER_CODE_BY_KIND[kind]
    assert (error.value.kind, error.value.provider_id) == (kind, "sec_edgar")
    assert str(error.value).startswith("Unable to look up KO: SEC EDGAR ")


def test_the_most_serious_provider_failure_wins(context: ApplicationContext, monkeypatch: pytest.MonkeyPatch) -> None:
    use_providers(
        monkeypatch,
        FakeSec(failure=ProviderFailureKind.RATE_LIMITED),
        FakeYahoo(failure=ProviderFailureKind.UNREACHABLE),
    )

    with pytest.raises(DataFetchError) as error:
        lookup_instrument_profile(context, "KO")

    assert (error.value.kind, error.value.provider_id) == (ProviderFailureKind.UNREACHABLE, "yfinance")


def test_a_lookup_without_an_sec_identity_is_a_configuration_error_that_names_no_setting(
    isolated_cli_settings: ProjectSettings,
) -> None:
    with pytest.raises(AnalysisConfigurationError) as error:
        lookup_instrument_profile(profile_context(isolated_cli_settings, sec_identity=False), "KO")

    assert error.value.reason_code is FailureReasonCode.CONFIGURATION_ERROR
    assert "SEC_USER_AGENT" not in str(error.value)
    assert str(error.value) == "Looking up an instrument profile needs an SEC identity, and none is set up."
