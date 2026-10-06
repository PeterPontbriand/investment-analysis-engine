"""The strategy flags of the watchlist ``create`` and ``add`` commands, as typed on the command line.

Every strategy's selection builder reads this one bundle and consults only the flags that concern it, so the
generic watchlist commands pass the same value to whichever builder the CLI tier supplies for ``--analysis``.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class WatchlistFlags:
    """Raw watchlist strategy flags, validated by the selection builder of the chosen strategy."""

    short_window: int
    long_window: int
    rsi_period: int
    as_of: str | None
    data_provider: str | None
    no_cache: bool
    eps: float | None
    eps_basis: str | None
    bvps: float | None
    current_price: float | None
    expected_growth: float | None
    aaa_yield: float | None
    growth_years: int | None
    forward_policy: str
    classification_basis: str
    currency: str
