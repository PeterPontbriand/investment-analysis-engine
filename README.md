# Financial Data Agents

> **Local-first AI agents for quantitative investment analysis, deterministic tool orchestration, and reproducible financial research.**

**Disclaimer:** Nothing in this repository, its documentation, generated reports, or any related materials constitutes financial, investment, legal, or tax advice. The project is provided for educational, research, and software-engineering demonstration purposes only. You are solely responsible for any investment decisions you make. Past performance of any analytical method is not indicative of future results. Always do your own research and consult qualified professionals before making financial decisions.

---

Financial Data Agents is an AI-native Python project that performs quantitative investment analysis using **locally hosted Large Language Models (LLMs)**, structured tool execution, and deterministic analytical pipelines.

Unlike many AI projects that rely heavily on cloud APIs and free-form prompting, this repository emphasizes:

* **100% local LLM inference** using Ollama
* **Deterministic tool execution** rather than unrestricted agent behavior
* **Structured validation** using strongly typed Python models
* **Reproducible analysis** with measurable engineering quality
* **Production-oriented software architecture** built around reliability before autonomy

The primary goal is a tool that serious retail and professional investors can actually use for rapid quantitative checks (intrinsic value, momentum, risk metrics) and audit-ready research briefs. Strong local-AI systems engineering is a necessary means to that end, not the end itself.

Status: Active development — pre-v1.0

---

## Hardware & Operating Modes (Read This First)

The project supports two modes. **Most users should start with Light Mode.** The architecture and roadmap describe capabilities that are still under development; the "Current Features" section below lists what is available now.

| Mode | Typical Hardware | Purpose |
|------|------------------|---------|
| **Light Mode** (recommended) | ~8–16 GB VRAM **or** 32–64 GB unified memory (Apple Silicon / high-end mini-PC) | Useful single-step analysis for the majority of users |
| **Full Dual-Tier Mode** | ~24–28 GB VRAM (or high unified memory) | Deeper multi-step reasoning and report synthesis |

**Light Mode is required to be fully usable before external user validation begins.**  
Full Dual-Tier Mode remains available for users who have the hardware.

→ See **[docs/HARDWARE.md](docs/HARDWARE.md)** for detailed requirements, recommended consumer configurations (2026), and guidance on Apple Silicon, mini-PCs, and discrete GPUs.

---

## Project Philosophy

* **Local-first AI** – All LLM inference is performed locally using locally hosted language models.
* **Reliability before capability** – Engineering discipline takes priority over adding AI features.
* **Deterministic execution** – Mathematical calculations remain explicit, testable, and reproducible.
* **Structured AI integration** – LLMs orchestrate tools rather than replacing conventional software engineering.
* **Incremental architecture** – Core infrastructure is hardened before expanding analytical capabilities.
* **Usefulness first** – Portfolio/engineering showcase value is treated as a byproduct of building something genuinely useful to real investors.

---

## Current Features

* Local AI orchestration engine using Ollama
* Structured command-line interface (CLI)
* Momentum analysis (RSI, SMA calculations)
* Configurable analysis parameters
* Strict static typing (`mypy --strict`) in the development toolchain
* Automated test suite (`pytest`)
* Fast linting and formatting (`ruff`)
* Jupyter Notebook integration

---

## High-level Roadmap

**High-level roadmap only:** numbering here is intentionally independent of the detailed Master Plan milestone numbering.

Developed through a structured, phase-driven plan (see Master Plan and Discovery Workbook for full detail).

Current progress:

* ✅ Local orchestration engine & LLM client wrapper
* ✅ Structured tool definitions & JSON Schema parsing layer
* ✅ Asynchronous orchestration runtime & context management

Planned milestones include:

1. Agent reliability, evaluation harness & structured observability
2. SQLite persistence layer, Alembic migrations & data-quality pipeline
3. **Light Mode (single-tier) support** — usable before external validation
4. Real-user validation checkpoint (≥3 external testers)
5. Quantitative financial analytics expansion (Graham formula, risk metrics)
6. Canadian localization framework (`en-CA` / `fr-CA`) — timing confirmed by validation feedback
7. Autonomous multi-step tool orchestration & self-correction
8. Automated visualization, charting & executive PDF report generation

---

## Target Architecture

```text
┌────────────────────────────────────────────────────────┐
│               CLI (uv run financial-agents)           │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│        Local Agent Runtime & Context Manager          │
└──────────────┬───────────────────────────┬─────────────┘
               │                           │
               ▼                           ▼
┌──────────────────────────┐   ┌─────────────────────────┐
│ Ollama Local LLMs        │   │ Structured Tool Layer   │
│ (Light or Dual-Tier)     │   │ & Parser                │
└──────────────────────────┘   └───────────┬─────────────┘
                                           │
                                           ▼
                               ┌─────────────────────────┐
                               │ Financial Analytics     │
                               │ Engine                  │
                               └─────────────────────────┘
```

---

## Installation & Prerequisites

### Prerequisites

* **Python 3.12+**
* **`uv`** (fast Python package installer & runner)
* **Ollama** running locally

**Recommended first model (Light Mode):**

```bash
ollama pull qwen2.5-coder:14b-instruct-q4_K_M
```

For Full Dual-Tier Mode (only if you have ~24 GB+ VRAM or 32 GB+ unified memory), you may additionally pull a 32B-class model such as `qwen2.5-coder:32b-instruct-q4_K_M` or `deepseek-r1:32b`.

### Setup

```bash
git clone https://github.com/PeterPontbriand/financial-data-agents.git
cd financial-data-agents
uv sync
```

See [docs/HARDWARE.md](docs/HARDWARE.md) if you are unsure whether your machine can run Light Mode or Full Dual-Tier Mode.

---

## Running the Application

The CLI is organized around subcommands.

```bash
# Run momentum analysis using default settings
uv run financial-agents momentum

# Specify ticker and custom moving-average windows
uv run financial-agents momentum \
    --ticker AAPL \
    --short-window 10 \
    --long-window 30

# Specify custom worker allocation
uv run financial-agents momentum --threads 8

# Display CLI help
uv run financial-agents --help
uv run financial-agents momentum --help
```

Executing modules directly:

```bash
uv run python -m src.main momentum
```

---

## Development & Quality Gates

### Testing & Coverage

Run the complete test suite with coverage:

```bash
uv run pytest tests/ --import-mode=importlib --cov=src --cov-report=html
```

Run core orchestration tests:

```bash
uv run pytest tests/orchestrator/
```

### Static Type Checking

```bash
uv run mypy --strict src/
```

### Linting & Formatting

```bash
uv run ruff check --fix .
uv run ruff format .
```

---

## Documentation

* [Master Plan](docs/MASTER_PLAN.md) — execution roadmap, milestones, quality targets
* [Discovery Workbook](docs/DISCOVERY_WORKBOOK.md) — architectural rationale and decision log
* [Hardware Requirements](docs/HARDWARE.md) — Light Mode vs Full Dual-Tier, consumer hardware guidance

---

## License

Distributed under the **Apache 2.0 License**. See `LICENSE` for more information.
