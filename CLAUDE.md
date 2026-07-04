# CLAUDE.md – Financial Data Agents Project

This repository builds autonomous Python agents for investment analysis using yfinance and local LLMs (Ollama). Core goal: Pull live or historical data → compute momentum signals / backtests → generate reports/dashboards with zero manual coding after initial prompt.
High-level overview and index for project guidelines. For detailed information, see the guides in `.claude/`.

## 📋 Project Overview

This repository builds autonomous Python agents for  investment analysis using yfinance.

**Core Goal:** Pull live or historical data → compute signals / backtests → generate reports/dashboards with zero manual coding after initial prompt.

**Key Principles:**
- Production-ready patterns (strict type hints, async execution, standardized error handling, local centralized logging)
- Prefer adjusted close prices for all calculations
- Never hardcode API keys – use `src/config.py` and dotenv
- Portfolio-first, modular architecture
- Strict runtime validation constraints (e.g., Short window intervals must strictly be less than Long window intervals)

---

## 📚 Project Guides

All detailed requirements are organized in `.claude/` sub-guides:

### 🔧 Development & Code Quality
- **[Coding Conventions](./.claude/coding_conventions.md)** — Python 3.14+, Google-style docstrings, Ruff formatting, type hints, file naming, architecture patterns
- **[Testing Workflow](./.claude/testing_workflow.md)** — TDD approach, pytest usage, mocking APIs, coverage targets, edge case testing, and optimal local execution commands

### 📊 Financial & Data Rules
- **[Finance Math](./.claude/finance_math.md)** — Crossover indicators, adjusted tracking calculations, data sanitization patterns, and error constraints
- **[Logging Rules](./.claude/logging_rules.md)** — Centralized logging standards, asynchronous queue handlers, context tracking parameters, and process safety cleanups

---

## 🛠️ Quick Commands Reference

### Testing & Verification
- **Run local tests (Fast Iteration):** `uv run pytest tests/ --import-mode=importlib --cov=src --cov-report=html`
- **Run clean isolated tests (CI Pre-Check):** `uv run --isolated pytest tests/ --import-mode=importlib --cov=src --cov-report=html`
- **Lint Codebase:** `ruff format . && ruff check --fix .`
- **Static Type Check:** `uv run python -m mypy --config-file ./.mypyrc src`

### Application Command Interfaces
- **Execute Analysis Agent (Default Run):** `python -m src.main momentum`
- **Run Momentum Module with Explicit Flags:** `python -m src.main momentum --ticker BTC-USD --short-window 10 --long-window 30`

---

## 📁 Repository Map

```text
.claude/                        # Project guidelines (this index)
├── coding_conventions.md       # Code style, architecture, naming
├── testing_workflow.md         # Testing requirements and patterns
├── finance_math.md            # Financial calculations and data rules
├── logging_rules.md           # Centralized logging standards
├── agent_behavior.md          # Agent workflow and cost management
├── commands_reference.md      # Common CLI commands
└── forbidden_actions.md       # Strict do-not-do list

src/                           # Main source code
├── config.py                  # Configuration management
├── main.py                    # Entry point (routes to cli.py)
├── cli.py                     # Command line interface subcommands (momentum)
├── analysis/                  # Analysis logic (momentum indicators, SMA math)
├── data/                      # Data fetching clients
├── agents/                    # Agent workflows
└── utils/                     # Centralized logging utilities & handlers

tests/                         # Test suite
data/                          # Data directory (never commit real data)
notebooks/                     # Jupyter exploration notebooks
docs/                          # Documentation
```

---

## 📞 Support & Reference

- **Python Docs:** See `src/utils/logger_util.py` for logger setup and teardown contexts
- **Config:** See `src/config.py` for environment variables and TOML configurations
- **Examples:** Check `tests/` for mock patterns, patching strategies, and global state fixtures

---

**Last Updated:** July 2026  
**Maintained by:** AI Agent Architecture  
**Status:** Active Development
