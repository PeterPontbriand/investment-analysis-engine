# Financial Data Agents

> **Local-first AI agents for deterministic quantitative investment analysis, typed tool orchestration, and reproducible financial research.**

**Disclaimer:** Nothing in this repository, its documentation, generated reports, or related materials constitutes financial, investment, legal, or tax advice. The project is provided for educational, research, and software-engineering demonstration purposes only. You are responsible for verifying outputs and for any investment decisions you make.

Financial Data Agents is an AI-native Python project that performs quantitative investment analysis using **locally hosted LLMs**, structured tool execution, and deterministic analytical strategies.

The project emphasizes:

- 100% local LLM inference through Ollama;
- deterministic Python calculations rather than LLM arithmetic;
- typed tool/analyzer/data boundaries;
- reproducible evaluation;
- reliability and observability before autonomy;
- a Light Mode path suitable for modest local hardware.

Status: **Active development — pre-v1.0**

---

## Documentation authority

For implementation work, use the documentation in this order:

1. the explicit human task/request;
2. the active milestone implementation plan (currently `docs/milestones/v0.2/IMPLEMENTATION_PLAN.md`);
3. `docs/MASTER_PLAN.md`;
4. `docs/ARCHITECTURE.md` and `docs/DISCOVERY_WORKBOOK.md`;
5. specialized references such as `docs/FINANCE_MATH.md`;
6. this README and convenience command files.

Do not infer a new architecture from a lower-level convenience document when a current plan states otherwise.

---

## Hardware & Operating Modes

The project supports two modes. **Most users should start with Light Mode.**

| Mode | Typical Hardware | Purpose |
|---|---|---|
| **Light Mode** (recommended) | ~8–16 GB VRAM **or** 32–64 GB unified memory | Useful single-step analysis for most users |
| **Full Dual-Tier Mode** | ~24–28 GB VRAM or equivalent high unified memory | Optional deeper planning/synthesis |

Light Mode must be fully usable before external user validation begins.

See [docs/HARDWARE.md](docs/HARDWARE.md).

---

## Current / Near-Term Analytical Architecture

The project intentionally supports materially different deterministic strategies rather than treating all financial analysis as Momentum.

```text
                     existing analysis/tool path
                              │
                 ┌────────────┴────────────┐
                 ▼                         ▼
        MomentumAnalyzer          GrahamValueAnalyzer
        historical prices         EPS / growth / yields
        SMA crossover             intrinsic value / MOS
                 │                         │
                 └────────────┬────────────┘
                              ▼
                     existing BaseAnalyzer
                              │
                              ▼
                      BaseDataClient
                 historical data + quote
```

- **Momentum** is the existing deterministic analyzer and currently performs configurable SMA/crossover analysis.
- **Graham valuation** is the Step 2.3 second strategy and intentionally has different inputs/outputs.
- Step 2.3 adds the minimum current-quote capability to the market-data boundary and a minimal deterministic fixture adapter.
- Step 2.4 builds the heterogeneous Golden Suite on those stable contracts.
- Production SQLite/cache-backed data access remains Step 3.1.

No speculative strategy/plugin registry is required merely because the strategies differ.

---

## Current Features

- Local Ollama orchestration engine
- Structured command-line interface (CLI)
- Typed tool registration/dispatch
- Configurable SMA/crossover Momentum analysis
- Structured trajectory telemetry with JSONL persistence
- Native structured-output/schema enforcement with Pydantic validation/fallback safeguards
- Strict static typing (`mypy --strict`)
- Automated tests (`pytest`)
- Ruff linting/formatting

The empirical model-by-model validation of native schema enforcement for supported Light Mode model configurations remains a non-blocking follow-up before the Light Mode exit criterion.

---

## High-Level Roadmap

The detailed implementation numbering lives in the Master Plan and active milestone plan. At a high level:

- ✅ Core local orchestration and typed tool dispatch
- ✅ Trajectory telemetry foundation
- ✅ Native schema-enforcement implementation
- ⏭ **Heterogeneous strategy/data foundation:** Graham + shared historical/current-quote data contract
- ⏭ **Golden strategy evaluation:** deterministic fixtures, Momentum/Graham cases, separate strategy-selection and numerical scores
- ⏭ Circuit breakers and timeout limits
- ⏭ SQLite/Alembic persistence, repositories, and data quality
- ⏭ Light Mode completion and external-user validation
- Later: additional valuation/technical strategies, risk metrics, localization, autonomy, and reporting

The initial Graham and Momentum strategies are **not** deferred to the later analytics-expansion milestone; they are the heterogeneous exemplars used to establish and evaluate the architecture first.

---

## Installation & Prerequisites

### Prerequisites

- Python 3.12+
- `uv`
- Ollama running locally

Recommended first model for the documented Light Mode path:

```bash
ollama pull qwen2.5-coder:14b-instruct-q4_K_M
```

Setup:

```bash
git clone https://github.com/PeterPontbriand/financial-data-agents.git
cd financial-data-agents
uv sync
```

---

## Running the Application

```bash
# Existing Momentum analysis
uv run financial-agents momentum

uv run financial-agents momentum \
    --ticker AAPL \
    --short-window 10 \
    --long-window 30

uv run financial-agents --help
uv run financial-agents momentum --help
```

Do not assume a Graham CLI command exists until Step 2.3 lands and documents the supported invocation path.

---

## Development & Quality Gates

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy --strict src/
uv run pytest
```

Developers may use Ruff's mutating `--fix` / formatter commands locally, but CI verification should remain non-mutating.

---

## Documentation

- [Master Plan](docs/MASTER_PLAN.md)
- [Milestone v0.2 Implementation Plan](docs/milestones/v0.2/IMPLEMENTATION_PLAN.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Discovery Workbook](docs/DISCOVERY_WORKBOOK.md)
- [Financial Math](docs/FINANCE_MATH.md)
- [Glossary](docs/GLOSSARY.md)
- [Hardware Requirements](docs/HARDWARE.md)

`docs/EVALUATIONS.md`, `docs/TOOL_DEVELOPMENT.md`, and `docs/I18N_GUIDE.md` are roadmap-owned planned documents; do not assume they already exist.

---

## License

Distributed under the Apache 2.0 License. See `LICENSE`.
