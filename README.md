# Financial Data Agents

> **Local-first AI agents for quantitative investment analysis, deterministic tool orchestration, and reproducible financial research.**

Financial Data Agents is an AI-native Python project exploring how autonomous agents can perform financial analysis using **locally hosted Large Language Models (LLMs)**, structured tool execution, and deterministic analytical pipelines.

Unlike many AI projects that rely heavily on cloud APIs and free-form prompting, this repository emphasizes:

* **100% local AI inference** using Ollama
* **Deterministic tool execution** rather than unrestricted agent behavior
* **Structured validation** using strongly typed Python models
* **Reproducible analysis** with measurable engineering quality
* **Production-oriented software architecture** built around reliability before autonomy

The long-term objective is to build a robust local AI platform capable of retrieving financial data, performing quantitative analysis, generating professional research reports, and demonstrating modern AI engineering best practices.

---

# Project Philosophy

This project is guided by several core principles:

* **Local-first AI** – All inference is performed using locally hosted language models.
* **Reliability before capability** – Engineering discipline takes priority over adding AI features.
* **Deterministic execution** – Mathematical calculations remain explicit, testable, and reproducible.
* **Structured AI integration** – LLMs orchestrate tools rather than replacing conventional software engineering.
* **Incremental architecture** – Core infrastructure is hardened before expanding analytical capabilities.

---

# Current Features

The repository currently provides:

* Local AI orchestration engine using Ollama
* Structured command-line interface (CLI)
* Momentum analysis (RSI, SMA calculations)
* Configurable analysis parameters
* Strict static typing (`mypy --strict`)
* Comprehensive test suite (`pytest`)
* Fast linting and formatting (`ruff`)
* Jupyter Notebook integration

---

# Project Roadmap

The repository is being developed through a structured, phase-driven implementation plan.

Current progress:

* ✅ Local orchestration engine & LLM client wrapper
* ✅ Structured tool definitions & JSON Schema parsing layer
* ✅ Asynchronous orchestration runtime & context management

Planned milestones include:

1. Agent reliability, evaluation harness & structured observability
2. SQLite persistence layer, Alembic migrations & data-quality pipeline
3. Quantitative financial analytics expansion (Graham formula, risk metrics)
4. Canadian localization framework (`en-CA` / `fr-CA`)
5. Autonomous multi-step tool orchestration & self-correction
6. Automated visualization, charting & executive PDF report generation

---

# Architecture Overview

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
│ (Qwen2.5-Coder / DeepSeek)   │   │ & Parser                │
└──────────────────────────┘   └───────────┬─────────────┘
                                           │
                                           ▼
                               ┌─────────────────────────┐
                               │ Financial Analytics     │
                               │ Engine (RSI / SMA)      │
                               └─────────────────────────┘
```

---

# Installation & Prerequisites

## Prerequisites

* **Python 3.12+**
* **`uv`** (fast Python package installer & runner)
* **Ollama** running locally

Pull the default local model:

```bash
ollama pull qwen2.5-coder:14b-instruct-q4_K_M
```

## Setup

Clone the repository and install dependencies:

```bash
git clone [https://github.com/PeterPontbriand/financial-data-agents.git](https://github.com/PeterPontbriand/financial-data-agents.git)
cd financial-data-agents
uv sync
```

---

# Running the Application

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

# Development & Quality Gates

## Testing & Coverage

Run the complete test suite with coverage:

```bash
uv run pytest tests/ --import-mode=importlib --cov=src --cov-report=html
```

Run core orchestration tests:

```bash
uv run pytest tests/orchestrator/
```

## Static Type Checking

```bash
uv run mypy --strict src/
```

## Linting & Formatting

```bash
uv run ruff check --fix .
uv run ruff format .
```

---

# License

Distributed under the **Apache 2.0 License**. See `LICENSE` for more information.