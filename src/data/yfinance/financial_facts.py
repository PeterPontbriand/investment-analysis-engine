"""Yahoo Finance valuation-fact adapter for current security quotes."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from src.data.base_client import DataFetchError
from src.data.financial.facts import (
    FinancialFactRequest,
    FinancialField,
    FinancialProviderError,
    FinancialUnit,
    ProviderFact,
)
from src.data.financial.provenance import FinancialSubjectKind
from src.data.security_identity import SecurityIdentity, SecurityIdentityRequest
from src.data.yfinance.client import YFINANCE_PROVIDER_ID, YFinanceClient

YFINANCE_CURRENT_PRICE_FIELD = "fast_info.last_price"


class YFinanceFinancialFactsAdapter:
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

    def fetch_facts(self, request: FinancialFactRequest) -> tuple[ProviderFact, ...]:
        """Return one current quote fact, or explicit unavailability."""
        if not self._supports(request):
            return ()

        retrieved_at = self._clock()
        if retrieved_at.tzinfo is None or retrieved_at.tzinfo.utcoffset(retrieved_at) is None:
            msg = "Yahoo financial-facts adapter clock returned a naive datetime."
            raise FinancialProviderError(msg)

        try:
            quote = self._client.fetch_current_quote(request.subject_id)
        except DataFetchError as exc:
            msg = f"Yahoo Finance quote retrieval failed for {request.subject_id}."
            raise FinancialProviderError(msg) from exc

        if quote.currency is None:
            return ()

        return (
            ProviderFact(
                subject_kind=FinancialSubjectKind.SECURITY,
                subject_id=request.subject_id,
                field_name=FinancialField.CURRENT_PRICE,
                value=quote.price,
                units=FinancialUnit.CURRENCY_PER_SHARE,
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

    def resolve_security_identity(self, request: SecurityIdentityRequest) -> SecurityIdentity | None:
        """Delegate current descriptive metadata to the retained Yahoo client."""
        return self._client.resolve_security_identity(request)

    @staticmethod
    def _supports(request: FinancialFactRequest) -> bool:
        """Return whether the request is exactly the supported current-quote shape."""
        return (
            request.provider_id == YFINANCE_PROVIDER_ID
            and request.subject_kind is FinancialSubjectKind.SECURITY
            and request.field_name is FinancialField.CURRENT_PRICE
            and request.basis is None
            and request.observation_count == 1
            and request.as_of is None
        )
