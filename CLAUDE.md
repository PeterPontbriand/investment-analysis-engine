# CLAUDE.md – Financial Data Agents Project

This repository builds autonomous Python agents for ETF / momentum investment analysis using Massive.com (formerly Massive.com) and yfinance. Core goal: Pull live or historical data → compute momentum signals / backtests → generate reports/dashboards with zero manual coding after initial prompt.
High-level overview and index for project guidelines. For detailed information, see the guides in `.claude/`.

## 📋 Project Overview

This repository builds autonomous Python agents for ETF / momentum investment analysis using Massive.com and yfinance.

**Core Goal:** Pull live or historical data → compute momentum signals / backtests → generate reports/dashboards with zero manual coding after initial prompt.

**Key Principles:**
- Production-ready patterns (type hints, async, error handling, logging)
- Prefer adjusted close prices for all calculations
- Never hardcode API keys – use `src/config.py` and dotenv
- Portfolio-first, modular architecture

---

## 📚 Project Guides

All detailed requirements are organized in `.claude/` sub-guides:

### 🔧 Development & Code Quality
- **[Coding Conventions](./.claude/coding_conventions.md)** — Python 3.14+, Google-style docstrings, Ruff formatting, type hints, file naming, architecture patterns
- **[Testing Workflow](./.claude/testing_workflow.md)** — TDD approach, pytest usage, mocking APIs, coverage targets, edge case testing

### 📊 Financial & Data Rules
- **[Finance Math & Data](./.claude/finance_math.md)** — Data sources (yfinance, Massive.com), adjusted close prices, momentum calculations, Sharpe ratio, volatility, portfolio analysis
- **[Logging Rules](./.claude/logging_rules.md)** — Centralized logging architecture, initialization, error handling, no `print()` statements

### 🤖 Agents & Automation
- **[Agent Behavior Rules](./.claude/agent_behavior.md)** — Workflow (Plan → Fetch → Analyze → Report → Test), human-in-the-loop, cost management, error handling
- **[Commands Reference](./.claude/commands_reference.md)** — Quick commands for testing, analysis, environment management, troubleshooting

### ⛔ Restrictions
- **[Forbidden Actions](./.claude/forbidden_actions.md)** — Security, code quality, testing, and repository violations with enforcement notes

---

## 🚀 Quick Start

### Pre-Commit Checklist
```bash
# Format and lint
ruff format . && ruff check --fix .

# Run tests
pytest -v --cov=src

# Run analysis
uv run python -m src.agents.run_analysis "TICKER vs peers"
```

### Environment Setup
- Python 3.14+
- See [Coding Conventions](./.claude/coding_conventions.md#language--version)
- Activate venv: `.\.venv\Scripts\Activate.ps1` (PowerShell)

---

## 🔑 Critical Rules (TL;DR)

✅ **DO:**
- Use type hints everywhere
- Log instead of printing
- Mock all API calls in tests
- Validate data before calculations
- Ask for approval before expensive operations

❌ **DON'T:**
- Commit `.env` or API keys
- Use unadjusted prices
- Hardcode configuration
- Disable error handling
- Scrape websites

**For complete details, see [Forbidden Actions](./.claude/forbidden_actions.md).**

---

## 📁 Repository Structure

```
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
├── main.py                    # Entry point
├── analysis/                  # Analysis logic (momentum, Sharpe, etc.)
├── data/                      # Data fetching clients
├── agents/                    # Agent workflows
└── utils/                     # Logging and utilities

tests/                         # Test suite
data/                          # Data directory (never commit real data)
notebooks/                     # Jupyter exploration notebooks
docs/                          # Documentation
```

---

## 📞 Support & Reference

- **Python Docs:** See `src/utils/logging.py` for logger setup
- **Config:** See `src/config.py` for environment variables
- **Examples:** Check `tests/` for mock patterns and fixtures

---

**Last Updated:** May 3, 2026  
**Maintained by:** AI Agent Architecture  
**Status:** Active Development
