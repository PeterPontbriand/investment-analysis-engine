"""Identifiers of the fixture evidence a Golden-Suite case can select.

Each identifier has one home. The foreign-private-issuer identifiers stay with their evidence in
``src.evaluation.fixtures.sec_edgar_fpi``. This module imports nothing from the project, so case modules,
strategy fixture composition and tests can all name an identifier without pulling in a fixture provider.
"""

from __future__ import annotations

from typing import Final

MOMENTUM_SUCCESS_FIXTURE_ID: Final = "momentum_success"
MOMENTUM_BOUNDARY_FIXTURE_ID: Final = "momentum_boundary"
GRAHAM_FACTS_FIXTURE_ID: Final = "graham_facts"
GRAHAM_PRECEDENCE_CACHE_FIXTURE_ID: Final = "graham_precedence_cache"
FCF_GROWTH_SUCCESS_FIXTURE_ID: Final = "fcf_growth_success"
FCF_GROWTH_NONMEANINGFUL_FIXTURE_ID: Final = "fcf_growth_nonmeaningful"
FCF_GROWTH_PERIOD_AS_OF_FIXTURE_ID: Final = "fcf_growth_period_as_of"
KNOWN_ETF_PROFILE_FIXTURE_ID: Final = "known_etf_profile"
