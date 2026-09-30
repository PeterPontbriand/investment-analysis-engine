"""The hyphenated analysis aliases the CLI accepts and prints, and their canonical method identifiers.

Canonical ``method_id`` values are persisted identity (stored watchlist entries, run envelopes,
``--json`` payloads) and never change. The aliases are the human and command-line vocabulary:
command input and human-readable text use them, and this module holds the only mapping between
the two.
"""

ANALYSIS_ALIASES = ("momentum", "graham-number", "graham-growth", "fcf-growth")

ALIAS_METHOD_IDS: dict[str, str] = {
    "momentum": "sma_crossover",
    "graham-number": "graham_number",
    "graham-growth": "graham_growth_value",
    "fcf-growth": "reported_fcf_eps_cagr",
}

METHOD_ID_ALIASES: dict[str, str] = {method_id: alias for alias, method_id in ALIAS_METHOD_IDS.items()}


def alias_for_method_id(method_id: str) -> str:
    """Return the alias for a canonical ``method_id``.

    Raises:
        KeyError: If ``method_id`` has no alias. For a decoded selection or a stored run this is a
            programming error, so there is deliberately no fallback to the canonical identifier.
    """
    return METHOD_ID_ALIASES[method_id]


__all__ = ["ALIAS_METHOD_IDS", "ANALYSIS_ALIASES", "METHOD_ID_ALIASES", "alias_for_method_id"]
