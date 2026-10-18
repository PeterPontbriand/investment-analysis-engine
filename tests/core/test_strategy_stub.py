"""The marker that a generated body has not been written yet."""

import pytest

from investment_analysis_engine.core.strategy_stub import UnfilledStubError, unfilled_stub


def test_an_unfilled_stub_raises_and_names_its_site() -> None:
    """Reaching a stub fails with an error that names the site whose body is missing."""
    with pytest.raises(UnfilledStubError, match="'codec' site has not been written"):
        unfilled_stub("codec")


def test_the_error_is_a_not_implemented_error() -> None:
    """Callers that treat unfinished work as ``NotImplementedError`` also catch it."""
    assert issubclass(UnfilledStubError, NotImplementedError)
