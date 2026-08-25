"""Yahoo Finance valuation-fact adapter for current security quotes."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from src.data.base_client import DataFetchError
from src.data.valuation.facts import (
    ProviderFact,
    ValuationFactRequest,
    ValuationField,
    ValuationProviderError,
    ValuationUnit,
)
from src.data.valuation.provenance import ValuationSubjectKind
from src.data.yfinance.client import YFINANCE_PROVIDER_ID, YFinanceClient

YFINANCE_CURRENT_PRICE_FIELD = "fast_info.last_price"


class YFinanceValuationAdapter:
    """Provide current Yahoo security quotes through valuation-fact contracts."""

    def __init__(
        self,
        *,
        client: YFinanceClient | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        """Initialize with injectable market client and retrieval clock."""
        self._client = client or YFinanceClient()
        self._clock = clock or (lambda: datetime.now(UTC))

    def fetch_facts(self, request: ValuationFactRequest) -> tuple[ProviderFact, ...]:
        """Return one current quote fact, or explicit unavailability."""
        if not self._supports(request):
            return ()

        retrieved_at = self._clock()
        if retrieved_at.tzinfo is None or retrieved_at.tzinfo.utcoffset(retrieved_at) is None:
            msg = "Yahoo valuation adapter clock returned a naive datetime."
            raise ValuationProviderError(msg)

        try:
            quote = self._client.fetch_current_quote(request.subject_id)
        except DataFetchError as exc:
            msg = f"Yahoo Finance quote retrieval failed for {request.subject_id}."
            raise ValuationProviderError(msg) from exc

        if quote.currency is None:
            return ()

        return (
            ProviderFact(
                subject_kind=ValuationSubjectKind.SECURITY,
                subject_id=request.subject_id,
                field_name=ValuationField.CURRENT_PRICE,
                value=quote.price,
                units=ValuationUnit.CURRENCY_PER_SHARE,
                provider_id=YFINANCE_PROVIDER_ID,
                provider_field=YFINANCE_CURRENT_PRICE_FIELD,
                retrieved_at=retrieved_at,
                currency=quote.currency,
                observed_at=retrieved_at,
                available_at=retrieved_at,
                notes=(
                    "Yahoo fast_info current quote",
                    "observed_at and available_at conservatively use retrieval time; "
                    "upstream exchange timestamp is not retained",
                ),
            ),
        )

    @staticmethod
    def _supports(request: ValuationFactRequest) -> bool:
        """Return whether the request is exactly the supported current-quote shape."""
        return (
            request.provider_id == YFINANCE_PROVIDER_ID
            and request.subject_kind is ValuationSubjectKind.SECURITY
            and request.field_name is ValuationField.CURRENT_PRICE
            and request.basis is None
            and request.observation_count == 1
            and request.as_of is None
        )
