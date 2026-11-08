"""The one rule that turns a ticker as written into a ticker as the engine stores and analyzes it."""


def normalize_ticker(value: str) -> str:
    """Normalize a ticker using the project's trim-and-upper-case convention.

    Args:
        value: A raw ticker, possibly carrying a venue suffix.

    Returns:
        The trimmed, uppercased ticker with any venue suffix preserved.

    Raises:
        ValueError: If the normalized ticker is empty.
    """
    normalized = value.strip().upper()
    if not normalized:
        raise ValueError("ticker must not be empty.")
    return normalized


def is_normalized_ticker(value: str) -> bool:
    """Return whether a ticker is already in the form ``normalize_ticker`` gives: non-blank, trimmed and upper-case."""
    return bool(value) and value == value.strip().upper()


__all__ = ["is_normalized_ticker", "normalize_ticker"]
