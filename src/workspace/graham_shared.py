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


def compose_graham_profile(
    ticker: str,
    *,
    primary_provider: object,
    primary_provider_id: str,
    yahoo_provider: object,
) -> InstrumentProfile:
    """Compose current profile evidence with explicit production precedence.

    The primary (security-fact) provider is tried first for identity; Yahoo
    is added as a second identity candidate only when it is not already the
    primary provider. Yahoo is always the kind candidate.
    """
    yahoo_candidate = InstrumentProfileCandidate(YFINANCE_PROVIDER_ID, yahoo_provider)
    identity_candidates: tuple[InstrumentProfileCandidate, ...] = (
        InstrumentProfileCandidate(primary_provider_id, primary_provider),
    )
    if primary_provider_id != YFINANCE_PROVIDER_ID:
        identity_candidates = (*identity_candidates, yahoo_candidate)
    return compose_instrument_profile(
        ticker,
        identity_candidates=identity_candidates,
        kind_candidate=yahoo_candidate,
    )


__all__ = ["compose_graham_profile"]
