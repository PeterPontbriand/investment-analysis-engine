# 📖 Financial & Quantitative Analysis Glossary

This glossary outlines the financial concepts, technical indicators, and industry acronyms used throughout the development and future roadmapping of this repository.

---

## 🔹 Core Terminology

### Ticker (Ticker Symbol)
A unique alphabetical code assigned to a security, asset, or cryptocurrency for trading purposes. 
* *Project Context:* The system defaults to `BTC-USD` to track the Bitcoin-to-U.S.-Dollar pair via market data streams.

### Momentum Indicator
A technical analysis tool used to measure the velocity of asset price changes over a specified period. Momentum strategies operate on the thesis that assets moving strongly in a given direction are likely to continue that trajectory.
* *Project Context:* Handled natively by the `src.analysis.momentum` module.

### Bullish
A market condition or sentiment characterized by rising prices, upward momentum, or the expectation that an asset's price will appreciate.

### Bearish
A market condition or sentiment characterized by falling prices, downward momentum, or the expectation that an asset's price will depreciate.
* *Project Context:* The current default state outputted by the pipeline based on recent historical ingestion.

---

## 📈 Technical Indicators & Strategy

### SMA (Simple Moving Average)
The unweighted mean of an asset's price over a specific number of periods (e.g., a 20-day or 50-day SMA). It smooths out price volatility to help identify the prevailing trend direction.

### EMA (Exponential Moving Average)
A type of moving average that applies more weight and significance to the most recent data points. It reacts faster to recent price changes than an SMA.

### Crossover Strategy
A trading methodology where two different moving averages (typically a short-term "fast" average and a long-term "slow" average) intersect. 
* **Golden Cross:** A short-term average crosses *above* a long-term average, signaling long-term **bullish** momentum.
* **Death Cross:** A short-term average crosses *below* a long-term average, signaling long-term **bearish** momentum.

### RSI (Relative Strength Index)
A momentum oscillator that measures the speed and change of price movements on a scale from 0 to 100. Traditionally, an asset is considered **overbought** when above 70 (potential reversal down) and **oversold** when below 30 (potential reversal up).

### MACD (Moving Average Convergence Divergence)
A trend-following momentum indicator that shows the relationship between two moving averages of an asset’s price (usually the 26-period and 12-period EMAs). A 9-period EMA of the MACD, called the "signal line," is plotted on top to trigger buy or sell signals.

---

## 📊 Performance & Risk Metrics

### Backtesting
The process of testing a trading strategy or predictive model on historical data to estimate how it would have performed in the past. This is critical for validating the viability of a momentum algorithm before deploying it.

### Sharpe Ratio
A metric used to understand the return of an investment compared to its risk. It measures the excess return per unit of deviation in an investment asset or a trading strategy. Higher numbers signify better risk-adjusted performance.

### Drawdown (Max Drawdown)
The peak-to-trough decline during a specific record period of an investment, fund, or trading strategy. It is usually quoted as the percentage between the peak and the subsequent trough, serving as a primary metric for assessing downside risk.

### OHLCV (Open, High, Low, Close, Volume)
A standard structured data format representing financial market data across a specific timeframe (e.g., 1-day intervals). 
* **Open/Close:** The asset price at the beginning and end of the period.
* **High/Low:** The maximum and minimum price reached during the period.
* **Volume:** The total number of units traded during that period.

---

## 💻 Data & Infrastructure

### Market Data Ingestion
The programmatic structural collection of real-time or historical market pricing data from external data APIs (e.g., `yfinance`, CCXT) into local computing environments or databases.

---

## 📐 Mathematical & Algorithmic Specifications

### 1. Simple Moving Average (SMA)
The SMA computes the unweighted mean of the closing prices over a moving window of $n$ periods.

**Formula:**
$$\text{SMA}_t = \frac{1}{n} \sum_{i=0}^{n-1} P_{t-i}$$

Where:
* $P_t$ = Closing price at time $t$
* $n$ = Number of periods in the moving window (e.g., $n=50$ or $n=200$)

### 2. Exponential Moving Average (EMA)
Unlike the SMA, the EMA applies a smoothing factor $\alpha$ to give exponentially decreasing weight to older prices.

**Formula:**
$$\text{EMA}_t = \left( P_t \times \alpha \right) + \left( \text{EMA}_{t-1} \times (1 - \alpha) \right)$$

Where $\alpha = \frac{2}{n + 1}$

### 3. Relative Strength Index (RSI)
The RSI is a bounded momentum oscillator that evaluates whether an asset is overbought or oversold over a default window of 14 periods.

**Formula:**
$$\text{RSI} = 100 - \left( \frac{100}{1 + \text{RS}} \right)$$
$$\text{RS} = \frac{\text{Average Gain}}{\text{Average Loss}}$$

Wilder's Smoothing Technique:
* $\text{Average Gain}_t = \frac{(\text{Average Gain}_{t-1} \times 13) + \text{Current Gain}}{14}$
* $\text{Average Loss}_t = \frac{(\text{Average Loss}_{t-1} \times 13) + \text{Current Loss}}{14}$

### 4. Moving Average Convergence Divergence (MACD)
The MACD turns two trend-following indicators (EMAs) into a momentum oscillator.

**Formula Components:**
* $\text{MACD Line} = \text{EMA}_{12}(P) - \text{EMA}_{26}(P)$
* $\text{Signal Line} = \text{EMA}_9(\text{MACD Line})$
* $\text{MACD Histogram} = \text{MACD Line} - \text{Signal Line}$

### 5. Sharpe Ratio (Risk-Adjusted Return)
The Sharpe Ratio quantifies the excess return generated per unit of asset volatility.

**Formula:**
$$S = \frac{R_p - R_f}{\sigma_p}$$

Where:
* $R_p$ = Expected portfolio or strategy return
* $R_f$ = Risk-free rate of return (often approximated as 0 for crypto)
* $\sigma_p$ = Standard deviation of the strategy's excess returns

Annualization Layer (Crypto 24/7/365):
$$\text{Sharpe}_{\text{Annualized}} = \frac{\text{Mean}(\text{Daily Returns})}{\text{StdDev}(\text{Daily Returns})} \times \sqrt{365}$$
