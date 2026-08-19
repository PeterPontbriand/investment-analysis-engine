# /analyze-momentum

**Purpose:** Run or inspect the repository's existing Momentum analysis. This convenience command is not an architectural specification.

## Instructions

- Reuse the existing `MomentumAnalyzer`, `MomentumConfig`, `BaseDataClient`, CLI, and project configuration.
- Do not create a second Momentum implementation.
- Do not add RSI, MACD, Sharpe, volatility, fixed risk-free rates, plotting dependencies, or new provider dependencies unless the explicit task asks for them.
- Use configured/default short/long SMA windows unless the caller supplies valid alternatives.
- Preserve `short_window < long_window` validation.
- For deterministic tests, inject/mock market data; never make live external calls.
- Follow `AGENTS.md`, `docs/FINANCE_MATH.md`, and the active milestone plan when they are more specific.
- Run relevant `uv run` quality/test commands after changes.

Example application invocation:

```bash
uv run financial-agents momentum --ticker FCIM.TO
```
