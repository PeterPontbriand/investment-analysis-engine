"""Instrument-profile composition shared by the Graham and FCF direct commands.

This helper is genuinely method-agnostic: Graham Number, Graham Growth, and
FCF/Earnings Growth all compose one profile the same way, with the same
primary-provider/Yahoo precedence. It lives here (not in a single method's
adapter module) so future adapters can share it without importing from
``src.cli``, which would create a circular import (``src.cli`` needs to
import each method's adapter).
"""

from src.data.financial.providers import YFINANCE_PROVIDER_ID
from src.data.instrument_profile import InstrumentProfile, InstrumentProfileCandidate, compose_instrument_profile
from src.data.instrument_profile_cache import InstrumentProfileResolver


def compose_graham_profile(
    ticker: str,
    *,
    primary_provider: object,
    primary_provider_id: str,
    yahoo_provider: object,
    profile_cache: InstrumentProfileResolver | None = None,
) -> InstrumentProfile:
    """Compose current profile evidence with explicit production precedence.

    The primary (security-fact) provider is tried first for identity; Yahoo
    is added as a second identity candidate only when it is not already the
    primary provider. Yahoo is always the kind candidate.

    ``profile_cache``, when supplied, resolves through the durable P2-Profiles
    cache instead of composing live every call; precedence and candidate
    construction are identical either way (P2-Profiles contract §3).
    """
    yahoo_candidate = InstrumentProfileCandidate(YFINANCE_PROVIDER_ID, yahoo_provider)
    identity_candidates: tuple[InstrumentProfileCandidate, ...] = (
        InstrumentProfileCandidate(primary_provider_id, primary_provider),
    )
    if primary_provider_id != YFINANCE_PROVIDER_ID:
        identity_candidates = (*identity_candidates, yahoo_candidate)
    if profile_cache is not None:
        return profile_cache.resolve(ticker, identity_candidates=identity_candidates, kind_candidate=yahoo_candidate)
    return compose_instrument_profile(
        ticker,
        identity_candidates=identity_candidates,
        kind_candidate=yahoo_candidate,
    )


__all__ = ["compose_graham_profile"]
