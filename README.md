# Financial Data Agents

> **Local-first investment analysis with deterministic calculations, traceable financial data, and optional AI-assisted research.**

Financial Data Agents is a terminal-first research tool for investors who want useful quantitative analysis **without treating an AI model as a calculator or an oracle**. Financial calculations are performed by deterministic Python [analysis strategies](docs/user/GLOSSARY.md#analysis-strategy); financial values retain [provenance](docs/user/GLOSSARY.md#provenance), measurement basis, and time boundaries so that a result can be inspected rather than merely accepted.

The application currently provides [Momentum](docs/user/GLOSSARY.md#momentum-analyzer), dual-method [Graham analysis](docs/user/GLOSSARY.md#graham-analysis), and [Free Cash Flow & Earnings Growth](docs/user/GLOSSARY.md#free-cash-flow--earnings-growth-strategy). Local [LLM](docs/user/GLOSSARY.md#llm-large-language-model) orchestration through Ollama is a separate capability: AI may help select, organize, or explain [typed evidence](docs/user/GLOSSARY.md#typed-evidence), but it does not perform financial arithmetic or silently invent missing values.

**Status:** Active development — pre-v1.0.

> Financial Data Agents is research/educational software, not investment advice. See [Limitations & disclaimer](#limitations--disclaimer).

---

## See what it does first

A default [Graham Number](docs/user/GLOSSARY.md#graham-number) analysis resolves [EPS](docs/user/GLOSSARY.md#eps-earnings-per-share) and [BVPS](docs/user/GLOSSARY.md#bvps-book-value-per-share) from available financial evidence and can compare the resulting [maximum indicated price / screening ceiling](docs/user/GLOSSARY.md#maximum-indicated-price--screening-ceiling) with a [current market price](docs/user/GLOSSARY.md#current-quote--current-market-price), expressed as a [price relationship](docs/user/GLOSSARY.md#price-relationship):

```bash
uv run financial-agents graham KO
```

A representative result looks like this:

```text
KO — Graham Number (maximum indicated price): 21.14 USD
Current price: 91.86 USD
Price relationship: 334.47% above the Graham Number

Basis: 3-year average diluted EPS + latest eligible fiscal-year-end BVPS
EPS (3-year average): 2.66 USD
Book value per common share: 7.48 USD
Sources / freshness: EPS — derived from SEC EDGAR (available 2026-02-20); BVPS — derived from SEC EDGAR (available 2026-02-20)
Limitation: The Graham Number is a maximum indicated price / screening ceiling, not a complete intrinsic-value conclusion or investment recommendation.
```

Live prices and newly published filings change, so the numbers above are illustrative. When supported provider evidence supplies an instrument name, the heading uses `Instrument Name (TICKER)`; otherwise it safely falls back to the ticker alone. The important part is the shape of the answer: the result names the method, shows the market comparison, identifies the financial basis, summarizes data sources/freshness, and states the method limitation.

Want to inspect more?

```bash
uv run financial-agents graham KO --details
uv run financial-agents graham KO --diagnostics
uv run financial-agents graham KO --json
```

`--json` produces [machine-readable output](docs/user/GLOSSARY.md#machine-readable-output) in [JSON](docs/user/GLOSSARY.md#json-javascript-object-notation), intended for another program rather than primarily for a person.

For ordinary usage, see the [Usage Guide](docs/user/USAGE.md). For the formula, assumptions, data sources, and interpretation, see the [Graham Analysis Strategy Guide](docs/user/strategies/GRAHAM.md).

---

## Who is this for?

Financial Data Agents is being built for several overlapping audiences, with investors first:

- **Experienced investors who already maintain spreadsheets, databases, screens, or scripts** and want calculations whose data and assumptions they can challenge, compare, override, and audit.
- **Experienced investors who are not software specialists** and want a low-friction way to go from a ticker symbol to a useful, intelligible result. The project does not yet have a one-click installer, so the installation guide deliberately assumes very little prior software-development knowledge.
- **Technically comfortable people learning investing** who want the running software and its documentation to reinforce one another.
- **Software engineers, architects, AI practitioners, and prospective contributors** who want to review the project design, implementation plans, and reliability boundaries. See [Project & Technical Documentation](docs/project/README.md).

When terms such as [TTM](docs/user/GLOSSARY.md#ttm-trailing-twelve-months), [SMA](docs/user/GLOSSARY.md#sma-simple-moving-average), [margin of safety](docs/user/GLOSSARY.md#margin-of-safety-mos), [look-ahead bias](docs/user/GLOSSARY.md#look-ahead-bias), or [override](docs/user/GLOSSARY.md#override) have a project-specific meaning, the documentation links to the project's definition rather than assuming that every reader uses the term identically.

---

## Getting started

Choose the guide that matches what you need:

- **New to Git or Python?** Follow the [Installation & Configuration Guide](docs/user/INSTALLATION.md).
- **Already comfortable with Python development?** Use the [Quick Start](docs/user/QUICKSTART.md).
- **Already installed?** Go directly to the [Usage Guide](docs/user/USAGE.md).

Direct deterministic analysis does **not** require Ollama or a GPU. Local-AI features are optional.

---

## What you can analyze today

| Analysis strategy / method | Values used | Data sources | What the result means |
|---|---|---|---|
| [Momentum](docs/user/strategies/MOMENTUM.md) | Historical closing prices; configurable short/long [SMA](docs/user/GLOSSARY.md#sma-simple-moving-average) windows | Yahoo Finance historical prices via `yfinance` | Current SMA/[crossover](docs/user/GLOSSARY.md#crossover) state when sufficient history is available; otherwise the result reports insufficient history |
| [Graham Number](docs/user/strategies/GRAHAM.md#graham-number-default-method) | Three completed fiscal years of diluted EPS averaged together + latest eligible fiscal-year-end BVPS; current quote optional for comparison | [SEC](docs/user/GLOSSARY.md#sec) [EDGAR](docs/user/GLOSSARY.md#edgar) financial facts + Yahoo Finance current quote via `yfinance` | Maximum indicated price / screening ceiling based on earnings and book value |
| [Graham Growth Value](docs/user/strategies/GRAHAM.md#graham-growth-value-secondary-method) | Explicit expected-growth assumption + explicit current [AAA corporate-bond yield](docs/user/GLOSSARY.md#aaa-corporate-bond-yield) + supported EPS basis; current quote optional for comparison | SEC EDGAR + Yahoo Finance current quote via `yfinance`, or optionally [Massive](docs/user/GLOSSARY.md#massive) for supported current TTM EPS/quote data | Forecast-dependent growth-formula estimate; not the Graham Number |
| [Free Cash Flow & Earnings Growth](docs/user/strategies/FCF_EARNINGS_GROWTH.md) | Completed annual operating cash flow, normalized capital expenditures, diluted EPS, and weighted-average diluted shares | SEC EDGAR annual company facts | `PASS`, `FAIL`, or `INDETERMINATE` historical growth screen; both total-company and per-share FCF growth are reported |

[`yfinance`](https://ranaroussi.github.io/yfinance/) is an independent open-source library that Financial Data Agents uses to access Yahoo Finance data. It is not affiliated with, endorsed by, or vetted by Yahoo.

An [analysis strategy](docs/user/GLOSSARY.md#analysis-strategy) is a deterministic analytical capability in the application. A [method](docs/user/GLOSSARY.md#method) is a particular calculation within a strategy when that strategy offers more than one approach. For example, the Graham Analysis Strategy currently offers the Graham Number and Graham Growth Value methods.

Each strategy has its own guide under [Analysis Strategy Guides](docs/user/strategies).

---

## Understanding and trusting a result

Financial Data Agents uses **progressive disclosure** so an ordinary result can stay readable without hiding the evidence needed to inspect or audit it. A result can be expanded from a concise investor-oriented view into progressively deeper layers of information:

- the calculation result, interpretation, important freshness/source context, warnings, and limitations;
- the financial facts, measurement bases, dates, data sources, and derivations behind the calculation;
- technical information about how the software resolved or failed to resolve those facts; and
- a structured [machine-readable representation](docs/user/GLOSSARY.md#machine-readable-output) for integration with other software.

This separation keeps routine analysis approachable while preserving the provenance and technical evidence needed for deeper scrutiny. The [Usage Guide](docs/user/USAGE.md) and individual [Analysis Strategy Guides](docs/user/strategies/README.md) explain how to request the available levels of detail.

Historical analysis also distinguishes when a fact describes from when that fact actually became available. This helps avoid [look-ahead bias](docs/user/GLOSSARY.md#look-ahead-bias).

Two calculations can legitimately disagree because they use different formulas, data sources, measurement conventions, dates, adjustment rules, or assumptions. The individual strategy guides explain the most important comparison points for each analysis.

---

## How AI fits — and where it does not

The core rule is simple: **AI may help reason about structured evidence, but it does not become the source of financial truth.**

- Financial calculations, validation, resolution rules, and computed values are always performed by deterministic Python analysis strategies, never by AI models.
- Data providers supply external information through narrow validated boundaries.
- Local AI may assist with planning, capability selection, bounded recovery, and later synthesis of already-computed evidence.
- Missing financial facts do not silently become zero.
- Analysis strategies never receive invented financial values from the model.
- Structured model output is schema-validated rather than trusted as free-form application state.

A GPU is not required for direct deterministic analysis. See [Hardware & Local AI](docs/user/HARDWARE.md) if you want to use optional local-model features.

---

## For technical reviewers and contributors

The investor/user documentation is intentionally separated from project implementation material.

Start with the [Project & Technical Documentation Index](docs/project/README.md) for:

- the architecture;
- the Master Plan and design rationale;
- the active milestone implementation plan;
- active step/slice plans and status;
- [engineering quality gates](docs/project/README.md#quality-gates); and
- deployment/configuration artifacts intended for project reviewers.

### Documentation authority

For implementation work, use:

1. the implementation request, issue, or explicitly agreed task currently being worked on;
2. the **active milestone implementation plan**;
3. the Master Plan;
4. the Architecture Guide and Discovery Workbook;
5. specialized references such as Financial Math and strategy guides; and
6. convenience/readme material.

The [Project & Technical Documentation Index](docs/project/README.md) is the single navigation point for identifying the active milestone, step, and slice documents. The root README intentionally does not hard-code that moving project status.

---

## Documentation

- [Investor & User Documentation](docs/user/README.md) — installation, usage, terminology, financial math, hardware, and strategy guides.
- [Project & Technical Documentation](docs/project/README.md) — architecture, roadmap, design rationale, milestone plans, step/slice plans, and engineering review material.
- [Documentation Router](docs/README.md) — choose the documentation set relevant to you.

---

## Limitations & disclaimer

Financial Data Agents is not an investment recommendation engine. A deterministic formula can still be inappropriate for a particular company, and accurate provider data can still be incomplete, stale, restated, differently defined, or economically misleading without context.

For example, the [Graham Number](docs/user/GLOSSARY.md#graham-number) is a limited earnings-and-book-value screen, the [Graham growth-value method](docs/user/GLOSSARY.md#graham-growth-value-method-graham_growth_value) depends materially on user-supplied assumptions, [Momentum](docs/user/GLOSSARY.md#momentum-analyzer) describes price-series behavior rather than business quality or fair value, and [Free Cash Flow & Earnings Growth](docs/user/GLOSSARY.md#free-cash-flow--earnings-growth-strategy) does not establish a moat, forecast future growth, or determine fair value.

Nothing in this repository, its documentation, generated output, or related materials constitutes financial, investment, legal, or tax advice. Verify source data, assumptions, methods, and outputs independently before making investment decisions.

---

## License

Distributed under the [Apache License 2.0](LICENSE).
