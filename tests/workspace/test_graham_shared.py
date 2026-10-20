"""Focused tests for the shared Graham/FCF instrument-profile composition helper."""

from unittest.mock import patch

from investment_analysis_engine.data.instrument_profile import InstrumentProfile, InstrumentProfileCandidate
from investment_analysis_engine.data.sec_edgar.financial_facts import SEC_PROVIDER_ID
from investment_analysis_engine.data.yfinance.client import YFINANCE_PROVIDER_ID
from investment_analysis_engine.strategies._shared.profile import compose_graham_profile


def test_yahoo_is_the_second_identity_candidate_after_sec_edgar() -> None:
    primary = object()
    yahoo = object()
    captured: dict[str, object] = {}

    def fake_compose(ticker: str, *, identity_candidates: object, kind_candidate: object) -> object:
        captured["ticker"] = ticker
        captured["identity_candidates"] = identity_candidates
        captured["kind_candidate"] = kind_candidate
        return "sentinel"

    with patch("investment_analysis_engine.strategies._shared.profile.compose_instrument_profile", fake_compose):
        compose_graham_profile("KO", primary_provider=primary, yahoo_provider=yahoo)

    assert captured["ticker"] == "KO"
    assert captured["identity_candidates"] == (
        InstrumentProfileCandidate(SEC_PROVIDER_ID, primary),
        InstrumentProfileCandidate(YFINANCE_PROVIDER_ID, yahoo),
    )
    assert captured["kind_candidate"] == InstrumentProfileCandidate(YFINANCE_PROVIDER_ID, yahoo)


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

    with patch("investment_analysis_engine.strategies._shared.profile.compose_instrument_profile") as fake_compose:
        result = compose_graham_profile(
            "KO",
            primary_provider=primary,
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
