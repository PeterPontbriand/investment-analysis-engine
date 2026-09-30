"""Provider EPS-basis capability, shared by every strategy that resolves normalized EPS."""

from typing import Final

_SEC_EDGAR_PROVIDER_ID: Final = "sec_edgar"
_MASSIVE_PROVIDER_ID: Final = "massive"

MASSIVE_ONLY_EPS_BASIS: Final = "ttm"


def default_eps_basis_for_provider(provider_id: str) -> str:
    """Return the provider-driven default EPS basis.

    SEC EDGAR defaults to three-year-average; every other provider — including Massive,
    which can structurally only ever supply TTM — defaults to TTM. Every strategy calls
    this same function for its own default, so a provider's own default can never be
    rejected by that same provider's own accept rule.
    """
    return "three_year_average" if provider_id == _SEC_EDGAR_PROVIDER_ID else MASSIVE_ONLY_EPS_BASIS


def is_massive_provider(provider_id: str) -> bool:
    """Return whether *provider_id* is Massive, which supplies EPS as TTM only."""
    return provider_id == _MASSIVE_PROVIDER_ID


def is_sec_edgar_provider(provider_id: str) -> bool:
    """Return whether *provider_id* is SEC EDGAR."""
    return provider_id == _SEC_EDGAR_PROVIDER_ID
