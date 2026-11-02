"""The production provider forwards every optional capability that a production adapter implements.

``ProductionFinancialFactsProvider`` answers a request by routing it to one adapter, and it forwards each optional
capability by hand, with its own typed answer for an adapter that lacks the capability. A capability protocol that an
adapter satisfies and the production provider does not would make every caller that holds the production provider see
the capability as absent, silently. This test finds the adapters and the protocols from the code, so a new adapter
method or a new protocol needs no edit here, and it names each gap by protocol and adapter.
"""

import importlib
import pkgutil
from collections.abc import Iterable
from types import ModuleType
from typing import Protocol, runtime_checkable

import pytest

import investment_analysis_engine.data as data_package
from investment_analysis_engine.data.financial.facts import (
    AnalysisScopedFinancialFactsProvider,
    FinancialFactsProvider,
    InstantSeriesProvider,
)
from investment_analysis_engine.data.financial.production import ProductionFinancialFactsProvider
from investment_analysis_engine.data.instrument_profile import InstrumentKindProvider
from investment_analysis_engine.data.sec_edgar.cover_listing import CoverListingProvider
from investment_analysis_engine.data.sec_edgar.financial_facts import (
    AnchorYearEndProvider,
    SecEdgarFinancialFactsAdapter,
)
from investment_analysis_engine.data.security_identity import SecurityIdentityProvider
from investment_analysis_engine.data.security_unit import SecurityUnitProvider
from investment_analysis_engine.data.yfinance.financial_facts import YFinanceFinancialFactsAdapter

ADAPTER_PACKAGES = ("investment_analysis_engine.data.sec_edgar", "investment_analysis_engine.data.yfinance")
"""The packages that hold the production adapters: the sources the production provider routes to."""


def _modules(package_name: str) -> list[ModuleType]:
    """Import and return every module of the package and its sub-packages."""
    package = importlib.import_module(package_name)
    names = [package_name] + [item.name for item in pkgutil.walk_packages(package.__path__, prefix=f"{package_name}.")]
    return [importlib.import_module(name) for name in names]


def _classes(modules: Iterable[ModuleType]) -> list[type]:
    """Return each class that one of the modules defines itself, not one it imports."""
    return [
        value
        for module in modules
        for value in vars(module).values()
        if isinstance(value, type) and value.__module__ == module.__name__
    ]


def _is_runtime_protocol(candidate: type) -> bool:
    """Return whether ``candidate`` is a protocol that ``isinstance`` and ``issubclass`` can check."""
    bases: tuple[object, ...] = candidate.__bases__
    if Protocol not in bases:
        return False
    try:
        issubclass(object, candidate)
    except TypeError:
        return False
    return True


def _production_adapters() -> list[type]:
    """Return the classes of the adapter packages that provide financial facts."""
    return [
        candidate
        for candidate in _classes(module for name in ADAPTER_PACKAGES for module in _modules(name))
        if not _is_runtime_protocol(candidate) and issubclass(candidate, FinancialFactsProvider)
    ]


def _capability_protocols() -> list[type]:
    """Return the runtime-checkable protocols that the data package defines."""
    return [candidate for candidate in _classes(_modules(data_package.__name__)) if _is_runtime_protocol(candidate)]


def forwarding_gaps(production: type, adapters: Iterable[type], protocols: Iterable[type]) -> list[str]:
    """Return one line per protocol that an adapter satisfies and ``production`` does not."""
    adapters = list(adapters)
    return [
        f"{protocol.__name__} is implemented by {adapter.__name__} but not by {production.__name__}"
        for protocol in protocols
        if not issubclass(production, protocol)
        for adapter in adapters
        if issubclass(adapter, protocol)
    ]


def test_the_search_finds_the_adapters_and_the_protocols_the_production_provider_routes() -> None:
    """The derived sets are not empty: both adapters and every capability protocol the provider checks are in them."""
    adapters = _production_adapters()
    assert SecEdgarFinancialFactsAdapter in adapters
    assert YFinanceFinancialFactsAdapter in adapters
    assert ProductionFinancialFactsProvider not in adapters
    protocols = _capability_protocols()
    for routed in (
        InstantSeriesProvider,
        SecurityUnitProvider,
        AnalysisScopedFinancialFactsProvider,
        SecurityIdentityProvider,
        InstrumentKindProvider,
        AnchorYearEndProvider,
        CoverListingProvider,
    ):
        assert routed in protocols


def test_the_production_provider_implements_every_capability_protocol_an_adapter_implements() -> None:
    """A capability that an adapter has is also one the production provider has, so no caller sees it as absent."""
    gaps = forwarding_gaps(ProductionFinancialFactsProvider, _production_adapters(), _capability_protocols())
    assert not gaps, "\n".join(gaps)


@pytest.mark.parametrize(
    ("method", "protocol", "adapter"),
    [
        ("fetch_instant_series", InstantSeriesProvider, SecEdgarFinancialFactsAdapter),
        ("resolve_security_unit", SecurityUnitProvider, SecEdgarFinancialFactsAdapter),
        ("analysis_scope", AnalysisScopedFinancialFactsProvider, SecEdgarFinancialFactsAdapter),
        ("resolve_security_identity", SecurityIdentityProvider, SecEdgarFinancialFactsAdapter),
        ("resolve_instrument_kind", InstrumentKindProvider, YFinanceFinancialFactsAdapter),
        ("resolve_anchor_year_end", AnchorYearEndProvider, SecEdgarFinancialFactsAdapter),
        ("resolve_cover_listing", CoverListingProvider, SecEdgarFinancialFactsAdapter),
    ],
)
def test_a_production_provider_without_one_forwarding_method_fails_naming_the_protocol_and_the_adapter(
    method: str, protocol: type, adapter: type
) -> None:
    """Removing any one forwarding method is reported as a gap that names its protocol and an adapter."""
    members = {name: value for name, value in vars(ProductionFinancialFactsProvider).items() if name != method}
    lacking = type("ProductionWithoutOneForward", (), members)
    gaps = forwarding_gaps(lacking, _production_adapters(), _capability_protocols())
    assert f"{protocol.__name__} is implemented by {adapter.__name__} but not by ProductionWithoutOneForward" in gaps


def test_a_protocol_that_is_not_runtime_checkable_is_not_a_capability_protocol() -> None:
    """Only a protocol that ``isinstance`` can check counts, since only such a protocol is detected at run time."""

    class Plain(Protocol):
        def one(self) -> None: ...

    @runtime_checkable
    class Checkable(Protocol):
        def one(self) -> None: ...

    assert not _is_runtime_protocol(Plain)
    assert _is_runtime_protocol(Checkable)
