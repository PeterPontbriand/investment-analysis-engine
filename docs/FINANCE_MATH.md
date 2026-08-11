# Financial Data & Mathematics

## Data Sources & Priority
- **Primary:** `yfinance` for Phase 1
- **Production:** Polygon.io client for real-time and aggregates
- **Fallback:** yfinance for quick prototypes and testing

## Data Handling Rules
- **Adjusted Close:** Always use adjusted close prices for all calculations
- **Resilience:** All API calls must include logging before and after requests
  - Track latency and success/failure
  - Implement retry logic using `tenacity` library
- **Rate Limiting:** Handle Polygon.io rate limits and pagination
- **Caching:** In-memory or .csv only for testing
  - Never commit real data to repository

## Momentum Analysis Standards
Default momentum calculation framework:
- **Signal:** 50/200-day SMA (Simple Moving Average) crossover
- **Return Metric:** 12-month return minus 1-month return
- **Risk Metrics:** Always include:
  - Sharpe ratio
  - Volatility (annualized standard deviation)
  - Volatility must be included in every analysis unless explicitly told otherwise

## ETF / Portfolio Analysis
- Portfolio-first architecture: Logic separated from data fetching
- Support batch analysis of multiple tickers
- Handle zero-length data series and missing values gracefully
- Validate data before performing calculations

## Financial Calculations
All financial metrics must be:
- Type-hinted with proper return types
- Documented with expected inputs and outputs
- Tested against edge cases (zero volatility, incomplete data, etc.)
- Production-ready with error handling

**See Also:**
- [Coding Conventions](./coding_conventions.md) for type hinting requirements
- [Testing Workflow](./testing_workflow.md) for financial calculation testing
