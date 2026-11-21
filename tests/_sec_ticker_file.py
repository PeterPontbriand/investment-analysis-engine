"""Build SEC ``company_tickers_exchange.json`` documents for offline tests."""

from typing import Any

TICKER_FILE_NAME = "company_tickers_exchange.json"
TICKER_FILE_FIELDS = ["cik", "name", "ticker", "exchange"]


def exchange_file(rows: Any, *, exchange: str | None = None) -> dict[str, object]:
    """Return the exchange file for rows written in the older ``cik_str``/``ticker``/``title`` layout.

    A document already in the exchange layout is returned as it is. A row's own ``exchange`` key wins over the
    ``exchange`` argument, so a test can give one row its own venue.
    """
    if "fields" in rows:
        return dict(rows)
    return {
        "fields": list(TICKER_FILE_FIELDS),
        "data": [[row["cik_str"], row["title"], row["ticker"], row.get("exchange", exchange)] for row in rows.values()],
    }


def one_row_file(*, cik: object, ticker: str, name: str, exchange: str | None = None) -> dict[str, object]:
    """Return an exchange file with a single row."""
    return {"fields": list(TICKER_FILE_FIELDS), "data": [[cik, name, ticker, exchange]]}
