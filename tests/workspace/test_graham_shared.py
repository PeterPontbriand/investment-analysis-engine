"""Focused tests for the shared Graham/FCF instrument-profile composition helper."""

from unittest.mock import patch

from src.data.financial.providers import SEC_PROVIDER_ID, YFINANCE_PROVIDER_ID
from src.data.instrument_profile import InstrumentProfile, InstrumentProfileCandidate
from src.workspace.graham_shared import compose_graham_profile


def test_yahoo_is_appended_as_a_second_identity_candidate_when_primary_differs() -> None:
    primary = object()
    yahoo = object()
    captured: dict[str, object] = {}

    def fake_compose(ticker: str, *, identity_candidates: object, kind_candidate: object) -> object:
        captured["ticker"] = ticker
        captured["identity_candidates"] = identity_candidates
        captured["kind_candidate"] = kind_candidate
        return "sentinel"

    with patch("src.workspace.graham_shared.compose_instrument_profile", fake_compose):
        compose_graham_profile(
            "KO", primary_provider=primary, primary_provider_id=SEC_PROVIDER_ID, yahoo_provider=yahoo
        )

    assert captured["ticker"] == "KO"
    assert captured["identity_candidates"] == (
        InstrumentProfileCandidate(SEC_PROVIDER_ID, primary),
        InstrumentProfileCandidate(YFINANCE_PROVIDER_ID, yahoo),
    )
    assert captured["kind_candidate"] == InstrumentProfileCandidate(YFINANCE_PROVIDER_ID, yahoo)


def test_yahoo_is_not_duplicated_when_it_is_already_the_primary_provider() -> None:
    yahoo = object()
    captured: dict[str, object] = {}

    def fake_compose(_ticker: str, *, identity_candidates: object, kind_candidate: object) -> object:
        del kind_candidate
        captured["identity_candidates"] = identity_candidates
        return "sentinel"

    with patch("src.workspace.graham_shared.compose_instrument_profile", fake_compose):
        compose_graham_profile(
            "KO", primary_provider=yahoo, primary_provider_id=YFINANCE_PROVIDER_ID, yahoo_provider=yahoo
        )

    assert captured["identity_candidates"] == (InstrumentProfileCandidate(YFINANCE_PROVIDER_ID, yahoo),)


def test_profile_cache_is_used_instead_of_live_composition_when_supplied() -> None:
    primary = object()
    yahoo = object()
    sentinel = InstrumentProfile(ticker="KO", identity=None, kind_evidence=None, diagnostics=())
    captured: dict[str, object] = {}

    class _FakeProfileCache:
        def resolve(
            self,
            ticker: str,
            *,
            identity_candidates: object,
            kind_candidate: object,
            force_refresh: bool = False,
        ) -> InstrumentProfile:
            del force_refresh
            captured["ticker"] = ticker
            captured["identity_candidates"] = identity_candidates
            captured["kind_candidate"] = kind_candidate
            return sentinel

    with patch("src.workspace.graham_shared.compose_instrument_profile") as fake_compose:
        result = compose_graham_profile(
            "KO",
            primary_provider=primary,
            primary_provider_id=SEC_PROVIDER_ID,
            yahoo_provider=yahoo,
            profile_cache=_FakeProfileCache(),
        )

    fake_compose.assert_not_called()
    assert result is sentinel
    assert captured["ticker"] == "KO"
    assert captured["identity_candidates"] == (
        InstrumentProfileCandidate(SEC_PROVIDER_ID, primary),
        InstrumentProfileCandidate(YFINANCE_PROVIDER_ID, yahoo),
    )
    assert captured["kind_candidate"] == InstrumentProfileCandidate(YFINANCE_PROVIDER_ID, yahoo)
