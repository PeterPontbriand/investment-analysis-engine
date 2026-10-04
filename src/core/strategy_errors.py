"""Fail-closed lookup shared by every layer that dispatches on a declared strategy.

A consumer that receives a mapping from the composition root looks an input up through ``require`` (or
``find`` where it must keep its own exception type). An input that matches no declared strategy is a
programming or configuration error, so it raises ``UndeclaredStrategyError`` and never falls back to a
default strategy.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping


class UndeclaredStrategyError(LookupError):
    """Raised when an input matches no declared strategy.

    The message names the key, type or tool that matched nothing and the declared alternatives.
    """


def describe(key: object) -> str:
    """Return a stable, readable name for a lookup key or a declared alternative."""
    if isinstance(key, type):
        return f"{key.__module__}.{key.__qualname__}"
    return repr(key)


def undeclared(what: str, key: object, declared: Iterable[object] = ()) -> UndeclaredStrategyError:
    """Build the error for an input that matches no declared strategy.

    Args:
        what: Kind of input, such as ``"tool"`` or ``"result type"``.
        key: The input that matched nothing.
        declared: The declared alternatives, when the caller has them.

    Returns:
        An error naming the input and, when supplied, the declared alternatives.
    """
    message = f"No declared strategy for {what} {describe(key)}"
    alternatives = sorted(describe(declared_key) for declared_key in declared)
    if alternatives:
        message += "; declared: " + ", ".join(alternatives)
    return UndeclaredStrategyError(message + ".")


def require[K, V](mapping: Mapping[K, V], key: K, *, what: str) -> V:
    """Return the entry for ``key`` or raise ``UndeclaredStrategyError`` naming it."""
    try:
        return mapping[key]
    except KeyError:
        raise undeclared(what, key, mapping) from None


def find[K, V](mapping: Mapping[K, V], key: K) -> V | None:
    """Return the entry for ``key``, or ``None`` for a consumer that keeps its own exception type."""
    return mapping.get(key)
