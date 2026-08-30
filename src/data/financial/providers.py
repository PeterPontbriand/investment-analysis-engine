"""Verified production financial-facts adapters."""

from src.data.financial.production import ProductionFinancialFactsProvider
from src.data.massive.constants import MASSIVE_PROVIDER_ID
from src.data.massive.financial_facts import MassiveFinancialFactsAdapter
from src.data.sec_edgar.financial_facts import SEC_PROVIDER_ID, SecEdgarFinancialFactsAdapter
from src.data.yfinance import YFINANCE_PROVIDER_ID, YFinanceFinancialFactsAdapter

__all__ = [
    "MASSIVE_PROVIDER_ID",
    "SEC_PROVIDER_ID",
    "YFINANCE_PROVIDER_ID",
    "MassiveFinancialFactsAdapter",
    "ProductionFinancialFactsProvider",
    "SecEdgarFinancialFactsAdapter",
    "YFinanceFinancialFactsAdapter",
]
