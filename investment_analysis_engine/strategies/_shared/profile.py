"""Instrument-profile composition shared by the Graham and FCF direct commands.

This helper is genuinely method-agnostic: Graham Number, Graham Growth, and
FCF/Earnings Growth all compose one profile the same way, with the same
primary-provider/Yahoo precedence. It lives here (not in a single method's
adapter module) so future adapters can share it without importing from
``investment_analysis_engine.cli``, which would create a circular import (``investment_analysis_engine.cli`` needs to
import each method's adapter).
"""

from investment_analysis_engine.data.instrument_profile import (
    InstrumentProfile,
    InstrumentProfileCandidate,
    compose_instrument_profile,
)
from investment_analysis_engine.data.instrument_profile_cache import InstrumentProfileResolver
from investment_analysis_engine.data.sec_edgar.financial_facts import SEC_PROVIDER_ID
from investment_analysis_engine.data.yfinance.client import YFINANCE_PROVIDER_ID


def compose_graham_profile(
    ticker: str,
    *,
    primary_provider: object,
    yahoo_provider: object,
    profile_cache: InstrumentProfileResolver | None = None,
) -> InstrumentProfile:
    """Compose current profile evidence with explicit production precedence.

    The primary (security-fact) provider, SEC EDGAR, is tried first for
    identity; Yahoo is the second identity candidate and always the kind
    candidate.

    ``profile_cache``, when supplied, resolves through the durable P2-Profiles
    cache instead of composing live every call; precedence and candidate
    construction are identical either way (P2-Profiles contract §3).
    """
    yahoo_candidate = InstrumentProfileCandidate(YFINANCE_PROVIDER_ID, yahoo_provider)
    identity_candidates = (InstrumentProfileCandidate(SEC_PROVIDER_ID, primary_provider), yahoo_candidate)
    if profile_cache is not None:
        return profile_cache.resolve(ticker, identity_candidates=identity_candidates, kind_candidate=yahoo_candidate)
    return compose_instrument_profile(
        ticker,
        identity_candidates=identity_candidates,
        kind_candidate=yahoo_candidate,
    )


__all__ = ["compose_graham_profile"]
