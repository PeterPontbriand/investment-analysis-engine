"""Fail-closed lookup shared by every layer that dispatches on a declared strategy."""

from __future__ import annotations

from types import MappingProxyType

import pytest

from src.core.strategy_errors import UndeclaredStrategyError, describe, find, require, undeclared


class _Declared:
    """A type used as a lookup key."""


def test_require_returns_the_declared_entry() -> None:
    """A declared key returns its entry unchanged."""
    assert require({"alpha": 1}, "alpha", what="key") == 1


def test_require_names_the_input_and_every_declared_alternative() -> None:
    """A missing key raises an error naming it and the sorted declared alternatives."""
    with pytest.raises(UndeclaredStrategyError) as caught:
        require(MappingProxyType({"beta": 2, "alpha": 1}), "gamma", what="widget")
    assert str(caught.value) == "No declared strategy for widget 'gamma'; declared: 'alpha', 'beta'."


def test_the_error_is_a_lookup_error_that_does_not_chain_the_key_error() -> None:
    """Callers may catch ``LookupError``; the raw ``KeyError`` is not part of the message."""
    with pytest.raises(LookupError) as caught:
        require({"alpha": 1}, "gamma", what="key")
    assert caught.value.__cause__ is None
    assert caught.value.__suppress_context__ is True


def test_types_are_described_by_their_qualified_name() -> None:
    """A type key or alternative is named by module and qualified name, not by its repr."""
    assert describe(_Declared) == f"{__name__}._Declared"
    declared: dict[type, int] = {_Declared: 1}
    with pytest.raises(UndeclaredStrategyError, match="No declared strategy for type .*_Other; declared: .*_Declared"):
        require(declared, type("_Other", (), {}), what="type")


def test_find_returns_none_instead_of_raising() -> None:
    """Consumers that keep their own exception type look up with ``find``."""
    assert find({"alpha": 1}, "alpha") == 1
    assert find({"alpha": 1}, "gamma") is None


def test_undeclared_without_alternatives_omits_the_declared_clause() -> None:
    """The message ends at the input when the caller has no alternatives to list."""
    assert str(undeclared("tool", "x")) == "No declared strategy for tool 'x'."
