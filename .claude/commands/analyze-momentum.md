# /analyze-momentum

**Purpose**: Analyze momentum for one or more ETFs/tickers using yfinance.

**Usage**: 
/analyze-momentum FCIM.TO SPY QQQ

**Instructions for Claude**:
- Fetch 1-year historical data (adjusted close) for each ticker.
- Calculate: 50-day SMA, 200-day SMA, 12-month return, 1-month return, volatility, and basic Sharpe ratio (assume risk-free rate 0.04).
- Detect golden/death cross.
- Generate a clear summary report + matplotlib/seaborn plot (save to docs/ or notebooks/).
- Use src/data/ modules if they exist; otherwise create robust, reusable code.
- Always include error handling and logging.
- Output key insights in a markdown table.
- Run tests if relevant.

**Rules**:
- Prefer adjusted close prices.
- Handle rate limits gracefully with tenacity.
- Never commit real data files.